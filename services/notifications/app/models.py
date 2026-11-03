"""Modèle notification (historique des envois, y c. simulation)."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

STATUS_SIMULATED = "SIMULE_ENVOYE"
STATUS_FAILED = "ECHEC"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)  # EMAIL | SMS
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    template: Mapped[str] = mapped_column(String(50), nullable=False)
    # SIMULE_ENVOYE : aucun fournisseur réel intégré — exigence : explicitement identifié
    status: Mapped[str] = mapped_column(String(15), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
