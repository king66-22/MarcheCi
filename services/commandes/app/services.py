"""Logique métier Commandes : création de commande (prix serveur), stock, transitions."""

import logging
from typing import Any

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from .catalogue_client import CatalogueClient, CatalogueUnavailable
from .config import get_settings
from .database import get_db
from .events import OrderEventPublisher
from .models import (
    ALLOWED_TRANSITIONS,
    Order,
    OrderItem,
    OutboxEvent,
    STATUS_ANNULEE,
    STATUS_EN_ATTENTE,
    STATUS_TERMINAL,
)
from .schemas import OrderCreate, OrderOut
from .service_auth import ServiceAuth

logger = logging.getLogger(__name__)


class StockAcquisitionError(Exception):
    """Le stock n'a pas pu être entièrement réduit (déjà pris par un autre client)."""


# --------------------------- Providers (DI) ---------------------------

_catalogue_client: CatalogueClient | None = None
_publisher: OrderEventPublisher | None = None
_service_auth: ServiceAuth | None = None


def get_catalogue_client() -> CatalogueClient:
    global _catalogue_client
    if _catalogue_client is None:
        s = get_settings()
        _catalogue_client = CatalogueClient(s.catalogue_url, timeout=s.request_timeout_seconds)
    return _catalogue_client


def get_publisher() -> OrderEventPublisher:
    global _publisher
    if _publisher is None:
        s = get_settings()
        _publisher = OrderEventPublisher(
            host=s.rabbitmq_host,
            port=s.rabbitmq_port,
            user=s.rabbitmq_user,
            password=s.rabbitmq_password,
            exchange=s.rabbitmq_exchange,
            queue=s.orders_queue,
            dlq=s.orders_dlq,
            max_retries=s.consumer_max_retries,
            retry_backoff_seconds=s.consumer_retry_backoff_seconds,
        )
        _publisher.enabled = s.events_enabled
    return _publisher


def get_service_auth() -> ServiceAuth:
    global _service_auth
    if _service_auth is None:
        s = get_settings()
        _service_auth = ServiceAuth(s.utilisateurs_url, s.svc_commandes_email, s.svc_commandes_password)
    return _service_auth


def set_catalogue_client_for_tests(client: CatalogueClient) -> None:
    global _catalogue_client
    _catalogue_client = client


def set_publisher_for_tests(pub: OrderEventPublisher) -> None:
    global _publisher
    _publisher = pub


def set_service_auth_for_tests(auth: ServiceAuth | None) -> None:
    global _service_auth
    _service_auth = auth


# --------------------------- Helpers ---------------------------


def order_to_out(order: Order) -> OrderOut:
    from datetime import datetime

    return OrderOut(
        id=order.id,
        user_id=order.user_id,
        status=order.status,
        total_xof=order.total_xof,
        delivery_address=order.delivery_address,
        delivery_phone=order.delivery_phone,
        payment_status=order.payment_status,
        created_at=order.created_at.isoformat(),
        items=[
            {
                "product_id": it.product_id,
                "product_name": it.product_name,
                "unit_price_xof": it.unit_price_xof,
                "quantity": it.quantity,
            }
            for it in order.items
        ],
    )


# --------------------------- Création de commande ---------------------------


def create_order(
    user_id: int,
    data: OrderCreate,
    db: Session = Depends(get_db),
    catalogue: CatalogueClient | None = None,
    publisher: OrderEventPublisher | None = None,
    service_auth: ServiceAuth | None = None,
) -> OrderOut | dict[str, Any]:
    """Création validée serveur : les prix viennent TOUJOURS du catalogue.

    Séquence :
    1. récupération produits de référence (prix/stock réels) ;
    2. contrôle du stock et calcul des totaux à partir des données catalogue ;
    3. décrément des stocks (avec compensation en cas d'échec partiel) ;
    4. environnement persistant de la commande (EN_ATTENTE) ;
    5. publication ordre de l'événement order.created (meilleur effort).
    """
    catalogue = catalogue or get_catalogue_client()
    publisher = publisher or get_publisher()
    service_auth = service_auth or get_service_auth()

    product_ids = [it.product_id for it in data.items]
    try:
      products = {p.id: p for p in catalogue.fetch_products(product_ids)}
    except CatalogueUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Catalogue indisponible : impossible de valider la commande",
        ) from exc

    # Contrôles : produit connu + actif, quantité disponible, prix pris côté serveur
    line_items: list[OrderItem] = []
    total = 0
    for it in data.items:
        ref = products.get(it.product_id)
        if ref is None or not ref.is_active:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Produit {it.product_id} introuvable ou indisponible",
            )
        if ref.stock < it.quantity:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Stock insuffisant pour le produit '{ref.name}' (disponible : {ref.stock})",
            )
        line_items.append(
            OrderItem(
                product_id=ref.id,
                product_name=ref.name,
                unit_price_xof=ref.price_xof,
                quantity=it.quantity,
            )
        )
        total += ref.price_xof * it.quantity

    # Décrément du stock AVEC compensation en cas d'échec (2e contrôle concurrent ou indisponibilité)
    restored: list[tuple[int, int]] = []
    try:
        sys_token = service_auth.get_token()
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Service d'authentification système indisponible") from exc

    compensation_note = None
    try:
        for item in line_items:
            ok = catalogue.adjust_stock(item.product_id, -item.quantity, sys_token)
            if not ok:
                raise StockAcquisitionError(f"Stock épuisé pour le produit {item.product_id} (contrôle concurrent)")
            restored.append((item.product_id, item.quantity))
    except (StockAcquisitionError, CatalogueUnavailable) as stock_exc:
        # Restituer le stock déjà réduit
        compensation_note = []
        try:
            for pid_r, qty_r in restored:
                catalogue.adjust_stock(pid_r, +qty_r, sys_token)
        except CatalogueUnavailable:
            logger.error("event", extra={"event": "stock_compensation_failed", "restored": restored})
        logger.info("event", extra={"event": "stock_compensated", "order_desc": compensation_note})

        if isinstance(stock_exc, CatalogueUnavailable):
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Réduction du stock impossible : catalogue indisponible, commande annulée",
            ) from stock_exc
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            str(stock_exc),
        ) from stock_exc

    # Environnement persistant de la commande (BASE000 IMPÉRATIF : transaction unique)
    order = Order(
        user_id=user_id,
        status=STATUS_EN_ATTENTE,
        total_xof=total,
        delivery_address=data.delivery_address,
        delivery_phone=data.delivery_phone,
    )
    db.add(order)
    for item in line_items:
        order.items.append(item)
    try:
        db.flush()
        event_payload = {
            "event": "order.created",
            "order_id": order.id,
            "user_id": order.user_id,
            "total_xof": order.total_xof,
            "status": order.status,
            "items": [
                {"product_id": it.product_id, "quantity": it.quantity,
                 "unit_price_xof": it.unit_price_xof, "product_name": it.product_name}
                for it in order.items
            ],
        }
        db.add(OutboxEvent(event_type="order.created", payload=event_payload))
        db.commit()
    except Exception as exc:
        db.rollback()
        # La commande n'a pas été persistée : restituer les stocks décrémentés
        try:
            for pid_r, qty_r in restored:
                catalogue.adjust_stock(pid_r, +qty_r, sys_token)
        except CatalogueUnavailable:
            logger.error(
                "event",
                extra={"event": "stock_compensation_after_db_failure", "restored": restored},
            )
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Commande non enregistrée") from exc

    logger.info(
        "event",
        extra={"event": "order_created", "order_id": order.id, "user_id": user_id, "total_xof": total},
    )
    return order_to_out(order)


def restock_on_cancellation(order: Order, db: Session) -> None:
    """Restitution du stock (compensation) — appelée best effort sur annulation."""
    try:
        auth = get_service_auth()
        sys_token = auth.get_token()
        catalogue = get_catalogue_client()
        for item in order.items:
            catalogue.adjust_stock(item.product_id, +item.quantity, sys_token)
        logger.info("event", extra={"event": "stock_restocked", "order_id": order.id})
    except (RuntimeError, CatalogueUnavailable) as exc:
        logger.error(
            "event",
            extra={"event": "stock_restock_failed", "order_id": order.id, "detail": str(exc)},
        )


def transition_status(order: Order, new_status: str) -> Order:
    """Applique la machine à états des statuts."""
    if new_status not in ALLOWED_TRANSITIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Statut invalide : {new_status!r}")
    if order.status in STATUS_TERMINAL:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Commande terminée ({order.status}), transition impossible")
    if new_status not in ALLOWED_TRANSITIONS[order.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Transition interdite : {order.status!r} → {new_status!r}",
        )
    order.status = new_status
    return order
