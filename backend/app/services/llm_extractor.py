from __future__ import annotations

import logging
import re

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import settings
from app.services.regex_extractor import ExtractionResult, derive_missing_amounts

logger = logging.getLogger(__name__)

_PROMPT = (
    "Extrahiere die Rechnungsdaten aus diesem PDF-Dokument.\n"
    "- kundennummer: nur die Kundennummer / Debitorennummer / Kd-Nr. "
    "(falls vorhanden). Nicht die Rechnungsnummer.\n"
    "- rechnungsnummer: nur die Rechnungsnummer (auch Rechn.Nr., Invoice No., "
    "Rechnung/Nummer). "
    "Niemals Kundennummer, Debitor, Auftragsnummer, Lieferschein oder Projekt. "
    "Wenn beide Nummern auf dem Beleg stehen, müssen sie in getrennte Felder.\n"
    "- rechnungsbetrag: der Endbetrag bzw. Zahlbetrag ohne Abzug / Bruttobetrag "
    "als Dezimalzahl (z. B. 1234.56). Nicht Positionssummen, Netto ohne Steuer "
    "oder Skonto-Zwischensummen.\n"
    "- nettobetrag: der Nettobetrag vor Steuer als Dezimalzahl, falls erkennbar.\n"
    "- steuerbetrag: der Steuerbetrag (MwSt./USt./VAT) als Dezimalzahl, falls erkennbar. "
    "Nicht den Steuersatz in Prozent.\n"
    "- waehrung: EUR, CHF, USD oder GBP."
)


class LlmInvoiceFields(BaseModel):
    kundennummer: str | None = Field(
        default=None,
        description=(
            "Kundennummer / Debitorennummer / Kd-Nr. / Customer No. "
            "Nicht die Rechnungsnummer."
        ),
    )
    rechnungsnummer: str | None = Field(
        default=None,
        description=(
            "Rechnungsnummer / Invoice number / Rechn.Nr. "
            "Nicht Kundennummer, Auftragsnummer oder Lieferscheinnummer. "
            "Muss von kundennummer verschieden sein, wenn beide existieren."
        ),
    )
    rechnungsbetrag: float | None = Field(
        default=None,
        description=(
            "Endbetrag / Bruttobetrag oder Zahlbetrag ohne Abzug als Dezimalzahl "
            "(deutsche 1.234,56 → 1234.56). Kein Skonto-Betrag, keine Position."
        ),
    )
    nettobetrag: float | None = Field(
        default=None,
        description=(
            "Nettobetrag vor Steuer als Dezimalzahl, falls auf der Rechnung ausgewiesen."
        ),
    )
    steuerbetrag: float | None = Field(
        default=None,
        description=(
            "Steuerbetrag (MwSt./USt./VAT) als Dezimalzahl, nicht der Prozentsatz."
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
    kundennummer = _clean_rechnungsnummer(fields.kundennummer)
    # Falls das Modell beide verwechselt hat: Kundennummer nicht als Rechnung übernehmen.
    if (
        rechnungsnummer is not None
        and kundennummer is not None
        and rechnungsnummer == kundennummer
    ):
        rechnungsnummer = None

    rechnungsbetrag = fields.rechnungsbetrag
    nettobetrag, steuerbetrag = derive_missing_amounts(
        rechnungsbetrag, fields.nettobetrag, fields.steuerbetrag
    )
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
        nettobetrag=nettobetrag,
        steuerbetrag=steuerbetrag,
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
