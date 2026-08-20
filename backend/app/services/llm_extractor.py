from __future__ import annotations

import logging
import re

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import settings
from app.services.regex_extractor import ExtractionResult

logger = logging.getLogger(__name__)

_PROMPT = (
    "Extrahiere die Rechnungsdaten aus diesem PDF-Dokument.\n"
    "- rechnungsnummer: die Rechnungsnummer (auch Rechn.Nr., Invoice No.). "
    "Nicht Kundennummer, Debitor, Auftragsnummer, Lieferschein oder Projekt.\n"
    "- rechnungsbetrag: der Endbetrag bzw. Zahlbetrag ohne Abzug / Gesamtbetrag "
    "als Dezimalzahl (z. B. 1234.56). Nicht Positionssummen, Netto ohne Steuer "
    "oder Skonto-Zwischensummen.\n"
    "- waehrung: EUR, CHF, USD oder GBP."
)


class LlmInvoiceFields(BaseModel):
    rechnungsnummer: str | None = Field(
        default=None,
        description=(
            "Rechnungsnummer / Invoice number / Rechn.Nr. "
            "Nicht Kundennummer, Auftragsnummer oder Lieferscheinnummer."
        ),
    )
    rechnungsbetrag: float | None = Field(
        default=None,
        description=(
            "Endbetrag oder Zahlbetrag ohne Abzug als Dezimalzahl "
            "(deutsche 1.234,56 → 1234.56). Kein Skonto-Betrag, keine Position."
        ),
    )
    waehrung: str = Field(
        default="EUR",
        description="Währungscode: EUR, CHF, USD oder GBP",
    )


def _clean_rechnungsnummer(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().rstrip(".,;:")
    if not value or not re.search(r"\d", value):
        return None
    return value


def _normalize_waehrung(value: str | None) -> str:
    if not value:
        return "EUR"
    upper = value.strip().upper()
    if upper in {"EUR", "CHF", "USD", "GBP"}:
        return upper
    return "EUR"


def _result_from_fields(fields: LlmInvoiceFields, hinweise_prefix: str | None = None) -> ExtractionResult:
    rechnungsnummer = _clean_rechnungsnummer(fields.rechnungsnummer)
    rechnungsbetrag = fields.rechnungsbetrag
    waehrung = _normalize_waehrung(fields.waehrung)

    hinweise: list[str] = []
    if hinweise_prefix:
        hinweise.append(hinweise_prefix)
    if rechnungsnummer is None:
        hinweise.append("Keine Rechnungsnummer gefunden")
    if rechnungsbetrag is None:
        hinweise.append("Kein Rechnungsbetrag gefunden")

    if rechnungsnummer is not None and rechnungsbetrag is not None:
        konfidenz = 0.9
    elif rechnungsnummer is not None or rechnungsbetrag is not None:
        konfidenz = 0.6
    else:
        konfidenz = 0.0

    return ExtractionResult(
        rechnungsnummer=rechnungsnummer,
        rechnungsbetrag=rechnungsbetrag,
        waehrung=waehrung,
        konfidenz=konfidenz,
        hinweise="; ".join(hinweise) if hinweise else None,
    )


def extract_invoice_data_via_llm(pdf_bytes: bytes) -> ExtractionResult:
    """Extrahiert Rechnungsfelder aus Scan-PDFs per Gemini Flash."""
    if not settings.gemini_api_key:
        return ExtractionResult(
            rechnungsnummer=None,
            rechnungsbetrag=None,
            waehrung="EUR",
            konfidenz=0.0,
            hinweise="Gemini-Extraktion nötig, aber GEMINI_API_KEY ist nicht konfiguriert",
        )

    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                _PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LlmInvoiceFields,
                # Structured Output braucht kein AFC; ohne disable=True loggt das
                # SDK eine Warnung (AFC ist im Default aktiv, auch ohne Tools).
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
    except Exception as exc:
        logger.exception("Gemini-Extraktion fehlgeschlagen")
        return ExtractionResult(
            rechnungsnummer=None,
            rechnungsbetrag=None,
            waehrung="EUR",
            konfidenz=0.0,
            hinweise=f"LLM-Extraktion fehlgeschlagen: {exc}",
        )

    parsed = response.parsed
    if not isinstance(parsed, LlmInvoiceFields):
        return ExtractionResult(
            rechnungsnummer=None,
            rechnungsbetrag=None,
            waehrung="EUR",
            konfidenz=0.0,
            hinweise="LLM lieferte keine gültigen Rechnungsdaten",
        )

    return _result_from_fields(parsed, hinweise_prefix="Per Gemini extrahiert")
