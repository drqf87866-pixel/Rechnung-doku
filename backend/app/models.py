from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class BauvorhabenShare(Base):
    """Freigabe eines Bauvorhabens vom Eigentümer an einen anderen Benutzer.

    Sichtbarkeit ist wechselseitig für Rechnungen mit gleichem Bauvorhaben-Namen
    zwischen Owner und Empfänger.
    """

    __tablename__ = "bauvorhaben_shares"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "bauvorhaben",
            "shared_with_user_id",
            name="uq_bauvorhaben_share",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bauvorhaben: Mapped[str] = mapped_column(String, nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    shared_with_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    stored_filename: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    bauvorhaben: Mapped[str] = mapped_column(String, nullable=False, index=True)
    rechnungsnummer: Mapped[str | None] = mapped_column(String, nullable=True)
    rechnungsbetrag: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    nettobetrag: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    steuerbetrag: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    waehrung: Mapped[str] = mapped_column(String, nullable=False, default="EUR")
    konfidenz: Mapped[float | None] = mapped_column(Float, nullable=True)
    hinweise: Mapped[str | None] = mapped_column(String, nullable=True)
    upload_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
