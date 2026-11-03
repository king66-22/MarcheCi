"""Endpoints Commandes : création, historique, détail, statuts, annulation. /health inclus."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Order, STATUS_ANNULEE, STATUS_EN_ATTENTE, STATUS_CONFIRMEE
from ..schemas import OrderCreate, OrderPage, OrderOut, StatusUpdate
from .. import services as svc

router = APIRouter()
security = HTTPBearer(auto_error=False)


def decode_access_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(
            token,
            s.jwt_secret,
            algorithms=[s.jwt_algorithm],
            issuer=s.jwt_issuer,
            audience=s.jwt_audience,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expirée, reconnectez-vous") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide") from exc


class Identity:
    def __init__(self, user_id: int, role: str, email: str | None = None):
        self.user_id = user_id
        self.role = role
        self.email = email


def get_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> Identity:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise")
    payload = decode_access_token(credentials.credentials)
    role = payload.get("role", "")
    if role not in ("CLIENT", "ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Rôle non autorisé")
    return Identity(user_id=int(payload["sub"]), role=role, email=payload.get("email"))


DB = Annotated[Session, Depends(get_db)]


def _order_to_out(order: Order) -> OrderOut:
    return svc.order_to_out(order)


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order_route(
    data: OrderCreate,
    db: DB,
    identity: Annotated[Identity, Depends(get_identity)],
):
    """Passer commande : les prix et le stock sont vérifiés auprès du service Catalogue."""
    result: OrderOut | Response = svc.create_order(
        user_id=identity.user_id,
        data=data,
        db=db,
    )
    if isinstance(result, Response):
        return result
    return result


@router.get("/orders", response_model=OrderPage)
def list_orders(
    db: DB,
    identity: Annotated[Identity, Depends(get_identity)],
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Historique : le client voit SES commandes ; l'ADMIN voit toutes les commandes."""
    stmt = select(Order).order_by(Order.created_at.desc(), Order.id.desc())
    count_stmt = select(func.count(Order.id))
    if identity.role != "ADMIN":
        stmt = stmt.where(Order.user_id == identity.user_id)
        count_stmt = count_stmt.where(Order.user_id == identity.user_id)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
        count_stmt = count_stmt.where(Order.status == status_filter)

    total = db.scalar(count_stmt) or 0
    orders = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return OrderPage(
        items=[_order_to_out(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: DB, identity: Annotated[Identity, Depends(get_identity)]):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    if identity.role != "ADMIN" and order.user_id != identity.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès refusé à cette commande")
    return _order_to_out(order)


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
def update_status(
    order_id: int,
    data: StatusUpdate,
    db: DB,
    identity: Annotated[Identity, Depends(get_identity)],
):
    if identity.role != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs")
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    prev = order.status
    order = svc.transition_status(order, data.status)
    db.commit()
    db.refresh(order)
    svc.logger.info(
        "event",
        extra={"event": "order_status_changed", "order_id": order_id, "detail": f"{prev}→{data.status}"},
    )
    return _order_to_out(order)


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, db: DB, identity: Annotated[Identity, Depends(get_identity)]):
    """Le client annule si EN_ATTENTE/CONFIRMEE ; l'ADMIN peut annuler avant expédition."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commande introuvable")
    if identity.role != "ADMIN":
        if order.user_id != identity.user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès refusé à cette commande")
        if order.status not in (STATUS_EN_ATTENTE, STATUS_CONFIRMEE):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Un client ne peut annuler que les commandes EN_ATTENTE ou CONFIRMEE (actuel : {order.status})",
            )
    svc.transition_status(order, STATUS_ANNULEE)
    db.commit()
    db.refresh(order)
    svc.logger.info("event", extra={"event": "order_cancelled", "order_id": order.id})
    svc.restock_on_cancellation(order, db)
    return _order_to_out(order)
