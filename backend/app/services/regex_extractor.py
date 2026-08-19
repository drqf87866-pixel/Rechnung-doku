from __future__ import annotations

import re
from dataclasses import dataclass

LABEL_RECHNUNGSNUMMER_RE = re.compile(
    r"(?:Rechnungsnummer|Rechnungsnr\.?|Rechnung\s*[-N]r\.?\s*|Invoice\s*(?:number|no\.?|#)\s*|Rech\.?\s*Nr\.?)\s*[:#\-]?\s*([A-Za-z0-9][A-Za-z0-9_\-/\.]{2,})",
    re.IGNORECASE,
)

CODE_RECHNUNGSNUMMER_RE = re.compile(r"\b(?:RG|RE|INV|RCH)[-\s]?\d{3,}\b", re.IGNORECASE)

BETRAG_LABEL_RE = re.compile(
    r"(?:Gesamtbetrag|Rechnungsbetrag|Bruttobetrag|Zahlbetrag|Zu\s*zahlen|Summe|Invoice\s*total|Total|Amount\s*due)\s*[:#]?\s*([\d\s.,]{1,15}[.,]\d{1,2})\s*(?:€|EUR|Euro|CHF)?",
    re.IGNORECASE,
)

BETRAG_GENERISCH_RE = re.compile(
    r"([\d]{1,3}(?:[.\s]\d{3})+(?:,\d{2})?|\d{1,10}[.,]\d{2})\s*(?:€|EUR|Euro|CHF)",
    re.IGNORECASE,
)


@dataclass
class ExtractionResult:
    rechnungsnummer: str | None
    rechnungsbetrag: float | None
    waehrung: str
    konfidenz: float
    hinweise: str | None


def parse_german_number(raw: str, force_german: bool = False) -> float:
    cleaned = re.sub(r"\s|€|EUR|Euro|CHF", "", raw, flags=re.IGNORECASE)

    has_dot = "." in cleaned
    has_comma = "," in cleaned

    if has_dot and has_comma:
        if force_german or cleaned.rfind(",") > cleaned.rfind("."):
            number_str = cleaned.replace(".", "").replace(",", ".")
        else:
            number_str = cleaned.replace(",", "")
    elif has_comma:
        number_str = cleaned.replace(",", ".")
    else:
        number_str = cleaned

    return float(number_str)


def _extract_rechnungsnummer(text: str) -> str | None:
    match = LABEL_RECHNUNGSNUMMER_RE.search(text)
    if match:
        return match.group(1).strip()

    match = CODE_RECHNUNGSNUMMER_RE.search(text)
    if match:
        return match.group(0).strip()

    return None


def _detect_currency(context: str) -> str:
    if re.search(r"CHF", context, re.IGNORECASE):
        return "CHF"
    return "EUR"


def _extract_betrag(text: str) -> tuple[float | None, str]:
    match = BETRAG_LABEL_RE.search(text)
    if match:
        try:
            betrag = parse_german_number(match.group(1))
        except ValueError:
            betrag = None
        if betrag is not None:
            return betrag, _detect_currency(match.group(0))

    match = BETRAG_GENERISCH_RE.search(text)
    if match:
        try:
            betrag = parse_german_number(match.group(1), force_german=True)
        except ValueError:
            betrag = None
        if betrag is not None:
            return betrag, _detect_currency(match.group(0))

    return None, "EUR"


def extract_invoice_data(text: str) -> ExtractionResult:
    rechnungsnummer = _extract_rechnungsnummer(text)
    rechnungsbetrag, waehrung = _extract_betrag(text)

    hinweise: list[str] = []
    if rechnungsnummer is None:
        hinweise.append("Keine Rechnungsnummer gefunden")
    if rechnungsbetrag is None:
        hinweise.append("Kein Rechnungsbetrag gefunden")

    if rechnungsnummer is not None and rechnungsbetrag is not None:
        konfidenz = 1.0
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
