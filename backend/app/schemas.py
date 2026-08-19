from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    bauvorhaben: str
    rechnungsnummer: Optional[str]
    rechnungsbetrag: Optional[float]
    waehrung: str
    konfidenz: Optional[float]
    hinweise: Optional[str]
    upload_time: datetime


class InvoicePatch(BaseModel):
    rechnungsnummer: Optional[str] = None
    rechnungsbetrag: Optional[float] = None
    bauvorhaben: Optional[str] = None
