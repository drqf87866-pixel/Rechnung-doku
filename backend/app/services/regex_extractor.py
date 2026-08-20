from __future__ import annotations

import re
from dataclasses import dataclass

# Label-Varianten für die Rechnungsnummer – tolerant gegenüber OCR-Artefakten
# und typischen Schreibweisen wie "Rechnungs-Nr.", "Re. - Nr.", "Rg.-Nr.",
# "Invoice No." (getrennte Wörter, Bindestriche, Punkte, Abstände).
_LABEL_LEAD = (
    r"(?:"
    r"Rechnungsnummer"
    r"|Rechnungs\s*[-–]?\s*[Nn][Rr]?\.?"
    r"|Rechnung\s*[-–]?\s*[Nn][Rr]?\.?"
    r"|Re\s*\.?\s*[-–]?\s*[Nn][Rr]?\.?"
    r"|Rg\s*\.?\s*[-–]?\s*[Nn][Rr]?\.?"
    r"|Rech\s*\.?\s*[-–]?\s*[Nn][Rr]?\.?"
    r"|R\.?\s*Nr\.?"
    r"|Invoice\s*(?:number|no\.?|#)"
    r")"
)

LABEL_RECHNUNGSNUMMER_RE = re.compile(
    _LABEL_LEAD + r"\s*[:#–—\-]?\s*([A-Za-z0-9][A-Za-z0-9_\-/\.]{1,})",
    re.IGNORECASE,
)

CODE_RECHNUNGSNUMMER_RE = re.compile(r"\b(?:RG|RE|INV|RCH)[-\s]?\d{3,}\b", re.IGNORECASE)

# Betrag-Labels in absteigender Spezifität: zuerst die eindeutigen Summenfelder,
# zuletzt die mehrdeutigen ("Summe", "Betrag"). Es gewinnt das erste Label,
# nach dem ein gültiger Betrag folgt.
_BETRAG_LABEL_PARTS = [
    "Gesamtbetrag",
    "Rechnungsbetrag",
    "Bruttobetrag",
    "Zahlbetrag",
    "Endbetrag",
    r"Offener\s+Restbetrag",
    r"Zu\s*zahlen",
    r"Invoice\s*total",
    r"Total\s*amount",
    r"Amount\s*due",
    r"\bSumme\b",
    r"\bTotal\b",
    r"\bBetrag\b",
]

_BETRAG_LABEL_RES = [re.compile(part, re.IGNORECASE) for part in _BETRAG_LABEL_PARTS]

# Betrag direkt nach einem Label (Wert darf auch in der nächsten Zeile stehen).
# Der Lookahead verhindert Fehltreffer wie "Zu zahlen 30 Tage": nach dem Betrag
# muss eine Währung, ein Satzzeichen oder das Zeilenende folgen.
_AMOUNT_AFTER_RE = re.compile(
    r"\s*[:#–—\-]?\s*"
    r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})?|\d{1,12}(?:[.,]\d{1,2})?)"
    r"(?=\s*(?:(?:€|EUR|Euro|CHF|USD|\$)|[,;.]|$))",
    re.IGNORECASE,
)

# Generisches Muster ohne Label: Betrag mit Währung direkt davor oder dahinter.
BETRAG_GENERISCH_RE = re.compile(
    r"(?:"
    r"(?:€|EUR|Euro|CHF|USD|\$)\s*(\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})?|\d{1,12}(?:[.,]\d{1,2})?)"
    r"|"
    r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})?|\d{1,12}(?:[.,]\d{1,2})?)\s*(?:€|EUR|Euro|CHF|USD|\$)"
    r")",
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
    cleaned = re.sub(r"\s|€|EUR|Euro|CHF|USD|\$", "", raw, flags=re.IGNORECASE)

    has_dot = "." in cleaned
    has_comma = "," in cleaned

    if has_dot and has_comma:
        if force_german or cleaned.rfind(",") > cleaned.rfind("."):
            number_str = cleaned.replace(".", "").replace(",", ".")
        else:
            number_str = cleaned.replace(",", "")
    elif has_comma:
        number_str = cleaned.replace(",", ".")
    elif has_dot:
        # Punkt ist Tausendertrenner ("1.234"), wenn er Dreiergruppen trennt,
        # sonst Dezimaltrenner ("1234.56").
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", cleaned):
            number_str = cleaned.replace(".", "")
        else:
            number_str = cleaned
    else:
        number_str = cleaned

    return float(number_str)


def _clean_rechnungsnummer(value: str) -> str | None:
    value = value.strip().rstrip(".,;:")
    if not value:
        return None
    # Eine echte Rechnungsnummer enthält mindestens eine Ziffer.
    if not re.search(r"\d", value):
        return None
    return value


def _extract_rechnungsnummer(text: str) -> str | None:
    match = LABEL_RECHNUNGSNUMMER_RE.search(text)
    if match:
        value = _clean_rechnungsnummer(match.group(1))
        if value:
            return value

    match = CODE_RECHNUNGSNUMMER_RE.search(text)
    if match:
        return match.group(0).strip()

    return None


def _detect_currency(context: str) -> str:
    if re.search(r"CHF", context, re.IGNORECASE):
        return "CHF"
    if re.search(r"USD|\$", context, re.IGNORECASE):
        return "USD"
    if re.search(r"GBP|£", context, re.IGNORECASE):
        return "GBP"
    return "EUR"


def _extract_betrag(text: str) -> tuple[float | None, str]:
    for label_re in _BETRAG_LABEL_RES:
        for match in label_re.finditer(text):
            amount_match = _AMOUNT_AFTER_RE.search(text[match.end() :])
            if not amount_match:
                continue
            try:
                betrag = parse_german_number(amount_match.group(1))
            except ValueError:
                continue
            if betrag is not None:
                context = text[max(0, match.start() - 30) : match.end() + 50]
                return betrag, _detect_currency(context)

    generic = BETRAG_GENERISCH_RE.search(text)
    if generic:
        raw = generic.group(1) or generic.group(2)
        if raw:
            try:
                betrag = parse_german_number(raw, force_german=True)
            except ValueError:
                betrag = None
            if betrag is not None:
                return betrag, _detect_currency(generic.group(0))

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
