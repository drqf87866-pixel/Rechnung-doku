from __future__ import annotations

import re
from dataclasses import dataclass

# Label-Varianten für die Rechnungsnummer – mit Wortgrenzen, damit z. B.
# "Trennscheibe" nicht als "Re…n…" matcht. "Rechnung" allein reicht nicht
# (sonst Capture von "Datum"/"Nummer"); Nummer-Suffix oder Multiline-Blöcke.
_LABEL_LEAD = (
    r"(?:"
    r"Rechnungsnummer"
    r"|Rechnungs\s*[-–]?\s*Nr\.?"
    r"|Rechn\.?\s*[-–]?\s*Nr\.?"
    r"|Rechnung\s*[-–]?\s*Nr\.?"
    r"|\bRe\s*\.?\s*[-–]?\s*Nr\.?"
    r"|\bRg\s*\.?\s*[-–]?\s*Nr\.?"
    r"|\bRech\s*\.?\s*[-–]?\s*Nr\.?"
    r"|\bR\.?\s*Nr\.?"
    r"|Invoice\s*(?:number|no\.?|#)"
    r")"
)

# Wert direkt nach dem Label (gleiche oder nächste Zeile).
LABEL_RECHNUNGSNUMMER_RE = re.compile(
    _LABEL_LEAD + r"\s*[:#–—\-]?\s*([A-Za-z0-9][A-Za-z0-9_\-/\.]{0,})",
    re.IGNORECASE,
)

# Layout: "Rechnung" / "Nummer" / Wert (je eigene Zeile).
RECHNUNG_NUMMER_BLOCK_RE = re.compile(
    r"Rechnung\s*\n\s*Nummer\s*\n\s*([A-Za-z0-9][A-Za-z0-9_\-/\.]{1,})",
    re.IGNORECASE,
)

# Layout: Spaltenkopf "Rechnung / Datum / Seite", Wert in der nächsten Zeile.
RECHNUNG_DATUM_SEITE_RE = re.compile(
    r"Rechnung\s*\n\s*Datum\s*\n\s*Seite\s*\n\s*(\d{4,})",
    re.IGNORECASE,
)

# Tabellenkopf "KD-Nr. Rechn.Nr. Datum Blatt" → zweite Spalte = Rechnungsnummer.
RECHN_NR_TABELLE_RE = re.compile(
    r"KD-Nr\.\s+Rechn\.?\s*Nr\.?\s+Datum\s+Blatt\s*\n\s*"
    r"\S+\s+(\S+)",
    re.IGNORECASE,
)

CODE_RECHNUNGSNUMMER_RE = re.compile(r"\b(?:RG|RE|INV|RCH)[-\s]?\d{3,}\b", re.IGNORECASE)

_PLACEHOLDER_NUMMERN = frozenset(
    {
        "nr",
        "nr.",
        "nummer",
        "number",
        "no",
        "no.",
        "datum",
        "seite",
        "blatt",
        "ummer",
        "ung",
    }
)

# Betrag-Labels in absteigender Spezifität. Endbetrag vor Zahlbetrag, damit
# Skonto-Zeilen ("Zahlbetrag bis …") nicht den Endbetrag überschreiben.
_BETRAG_LABEL_PARTS = [
    "Gesamtbetrag",
    "Rechnungsbetrag",
    "Bruttobetrag",
    "Endbetrag",
    r"\bGesamt\b",
    r"Offener\s+Restbetrag",
    "Zahlbetrag",
    r"Zu\s*zahlen",
    r"Invoice\s*total",
    r"Total\s*amount",
    r"Amount\s*due",
    r"\bSumme\b",
    r"\bTotal\b",
    r"\bBetrag\b",
]

_BETRAG_LABEL_RES = [re.compile(part, re.IGNORECASE) for part in _BETRAG_LABEL_PARTS]

# Betrags-Token: vollständige Dezimalzahl bevorzugen; kein abgeschnittenes
# "24" aus "24,15" und kein Datum "02.09.2026".
_AMOUNT_TOKEN = (
    r"(?:"
    r"\d{1,3}(?:[.\s]\d{3})+,\d{2}"  # 1.234,56
    r"|\d{1,3}(?:[.\s]\d{3})+"  # 1.234
    r"|\d+,\d{2}"  # 24,15
    r"|\d+\.\d{2}(?!\.\d)"  # 24.15, aber nicht 02.09.2026
    r"|\d+(?![.,]\d)"  # ganze Zahl, nicht Präfix eines Dezimal-/Datumswerts
    r")"
)

_DATE_AHEAD = r"\d{1,2}\.\d{1,2}\.\d{2,4}"

# Nach dem Betrag: Währung oder Zeilenende (MULTILINE). Kein bloßes "." / ","
# als Terminator (sonst "24,15"→"24", "02.09.2026"→"2.09") und kein
# "30 Tage" nach "Zu zahlen".
_AMOUNT_AFTER_RE = re.compile(
    r"\s*[:#–—\-]?\s*"
    rf"(?!{_DATE_AHEAD})"
    rf"({_AMOUNT_TOKEN})"
    r"(?=\s*(?:(?:€|EUR|Euro|CHF|USD|\$)|[,;.]?\s*$))",
    re.IGNORECASE | re.MULTILINE,
)

# Generisches Muster ohne Label: Betrag mit Währung direkt davor oder dahinter.
BETRAG_GENERISCH_RE = re.compile(
    rf"(?:"
    rf"(?:€|EUR|Euro|CHF|USD|\$)\s*(?!{_DATE_AHEAD})({_AMOUNT_TOKEN})"
    rf"|"
    rf"(?!{_DATE_AHEAD})({_AMOUNT_TOKEN})\s*(?:€|EUR|Euro|CHF|USD|\$)"
    rf")",
    re.IGNORECASE,
)

# Fenster nach dem Label, in dem der Betrag stehen darf (nicht seitenweit suchen).
_AMOUNT_SEARCH_WINDOW = 120


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
    if value.lower() in _PLACEHOLDER_NUMMERN:
        return None
    # Eine echte Rechnungsnummer enthält mindestens eine Ziffer.
    if not re.search(r"\d", value):
        return None
    return value


def _extract_rechnungsnummer(text: str) -> str | None:
    for pattern in (
        RECHNUNG_NUMMER_BLOCK_RE,
        RECHNUNG_DATUM_SEITE_RE,
        RECHN_NR_TABELLE_RE,
    ):
        match = pattern.search(text)
        if match:
            value = _clean_rechnungsnummer(match.group(1))
            if value:
                return value

    for match in LABEL_RECHNUNGSNUMMER_RE.finditer(text):
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


def _is_skonto_zahlbetrag_context(label: str, after_slice: str) -> bool:
    """Zahlbetrag-Zeilen mit Skonto (ohne 'ohne Abzug') überspringen."""
    if not re.search(r"zahlbetrag", label, re.IGNORECASE):
        return False
    window = after_slice[:_AMOUNT_SEARCH_WINDOW]
    if re.search(r"ohne\s+abzug", window, re.IGNORECASE):
        return False
    return bool(re.search(r"skonto", window, re.IGNORECASE))


def _extract_betrag(text: str) -> tuple[float | None, str]:
    for label_re in _BETRAG_LABEL_RES:
        for match in label_re.finditer(text):
            after = text[match.end() : match.end() + _AMOUNT_SEARCH_WINDOW]
            if _is_skonto_zahlbetrag_context(match.group(0), after):
                continue
            amount_match = _AMOUNT_AFTER_RE.search(after)
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
