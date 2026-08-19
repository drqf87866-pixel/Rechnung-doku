from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    stored_filename: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    bauvorhaben: Mapped[str] = mapped_column(String, nullable=False, index=True)
    rechnungsnummer: Mapped[str | None] = mapped_column(String, nullable=True)
    rechnungsbetrag: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    waehrung: Mapped[str] = mapped_column(String, nullable=False, default="EUR")
    konfidenz: Mapped[float | None] = mapped_column(Float, nullable=True)
    hinweise: Mapped[str | None] = mapped_column(String, nullable=True)
    upload_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
