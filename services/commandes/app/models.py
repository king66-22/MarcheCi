"""Modèles commandes : orders + order_items (snapshot des produits)."""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Statuts autorisés (exigence sujet)
STATUS_EN_ATTENTE = "EN_ATTENTE"
STATUS_CONFIRMEE = "CONFIRMEE"
STATUS_EN_PREPARATION = "EN_PREPARATION"
STATUS_EXPEDIEE = "EXPEDIEE"
STATUS_LIVREE = "LIVREE"
STATUS_ANNULEE = "ANNULEE"

VALID_STATUSES = [
    STATUS_EN_ATTENTE,
    STATUS_CONFIRMEE,
    STATUS_EN_PREPARATION,
    STATUS_EXPEDIEE,
    STATUS_LIVREE,
    STATUS_ANNULEE,
]

# Transitions autorisées (machine à états stricte)
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    STATUS_EN_ATTENTE: {STATUS_CONFIRMEE, STATUS_ANNULEE},
    STATUS_CONFIRMEE: {STATUS_EN_PREPARATION, STATUS_ANNULEE},
    STATUS_EN_PREPARATION: {STATUS_EXPEDIEE},
    STATUS_EXPEDIEE: {STATUS_LIVREE},
    STATUS_LIVREE: set(),
    STATUS_ANNULEE: set(),
}

STATUS_TERMINAL = {STATUS_LIVREE, STATUS_ANNULEE}


def utcnow() -> datetime:
    return datetime.now(UTC)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_EN_ATTENTE)
    total_xof: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="A_REGIER")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # Snapshots : nom + prix figés au moment de la commande (résistance aux changements du catalogue)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_price_xof: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")


class OutboxEvent(Base):
    """Événement à publier, enregistré dans la même transaction que la commande."""

    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_events_pending", "published_at", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
