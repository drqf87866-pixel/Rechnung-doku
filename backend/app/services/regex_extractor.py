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

# Kunden-/Debitorennummer – darf nie als Rechnungsnummer landen.
_KUNDEN_LABEL = (
    r"(?:"
    r"Kunden(?:nummer|nr\.?|\s*[-–]?\s*Nr\.?)"
    r"|Kd\.?\s*[-–]?\s*Nr\.?"
    r"|Debitor(?:en)?(?:nummer|nr\.?|\s*[-–]?\s*Nr\.?)"
    r"|Customer\s*(?:no\.?|number|#)"
    r"|Cust\.?\s*[-–]?\s*(?:No\.?|Nr\.?)"
    r")"
)

LABEL_RECHNUNGSNUMMER_ONLY_RE = re.compile(_LABEL_LEAD, re.IGNORECASE)
KUNDEN_LABEL_RE = re.compile(_KUNDEN_LABEL, re.IGNORECASE)

# Wert direkt nach dem Label (gleiche oder nächste Zeile).
LABEL_RECHNUNGSNUMMER_RE = re.compile(
    _LABEL_LEAD + r"\s*[:#–—\-/]?\s*([A-Za-z0-9][A-Za-z0-9_\-/\.]{0,})",
    re.IGNORECASE,
)

LABEL_KUNDENNUMMER_RE = re.compile(
    _KUNDEN_LABEL + r"\s*[:#–—\-/]?\s*([A-Za-z0-9][A-Za-z0-9_\-/\.]{0,})",
    re.IGNORECASE,
)

_VALUE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-/\.]*")

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
        "kundennummer",
        "kundennr",
        "kundennr.",
        "debitor",
        "debitoren",
        "debitorennummer",
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

# Netto / Steuer – eigene Labels, damit sie nicht den Brutto-Endbetrag überschreiben.
_NETTO_LABEL_PARTS = [
    "Nettobetrag",
    "Nettosumme",
    "Nettowert",
    r"Netto\s*gesamt",
    r"Summe\s*netto",
    r"Zwischensumme\s*netto",
    r"Net\s*amount",
    r"Net\s*total",
    r"Subtotal",
    r"\bNetto\b",
]

_STEUER_LABEL_PARTS = [
    "Steuerbetrag",
    "Mehrwertsteuer",
    "Umsatzsteuer",
    r"MwSt\.?(?:\s*\d+[.,]?\d*\s*%)?",
    r"\bUSt\.?(?:\s*\d+[.,]?\d*\s*%)?",
    r"VAT(?:\s*\d+[.,]?\d*\s*%)?",
    r"Tax\s*amount",
    r"\bSteuer\b",
]

_NETTO_LABEL_RES = [re.compile(part, re.IGNORECASE) for part in _NETTO_LABEL_PARTS]
_STEUER_LABEL_RES = [re.compile(part, re.IGNORECASE) for part in _STEUER_LABEL_PARTS]

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
    nettobetrag: float | None = None
    steuerbetrag: float | None = None


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
    # Keine anderen Feld-Labels als Wert akzeptieren.
    if KUNDEN_LABEL_RE.fullmatch(value) or LABEL_RECHNUNGSNUMMER_ONLY_RE.fullmatch(value):
        return None
    # Eine echte Rechnungsnummer enthält mindestens eine Ziffer.
    if not re.search(r"\d", value):
        return None
    return value


def _line_value_tokens(line: str) -> list[str]:
    """Werte einer Datenzeile (Leerzeichen oder '/' getrennt), ohne reine Labels."""
    tokens: list[str] = []
    for raw in _VALUE_TOKEN_RE.findall(line):
        cleaned = _clean_rechnungsnummer(raw)
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _extract_from_kunden_rechnung_headers(text: str) -> str | None:
    """Spaltenköpfe Kundennummer + Rechnungsnummer → richtige Spalte wählen."""
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        kunden = list(KUNDEN_LABEL_RE.finditer(line))
        rechnung = list(LABEL_RECHNUNGSNUMMER_ONLY_RE.finditer(line))
        if not kunden or not rechnung:
            continue

        next_line = ""
        for candidate in lines[index + 1 :]:
            if candidate.strip():
                next_line = candidate
                break
        if not next_line:
            continue

        values = _line_value_tokens(next_line)
        if len(values) < 2:
            continue

        if kunden[0].start() < rechnung[0].start():
            return values[1]
        return values[0]
    return None


def _collect_kundennummern(text: str) -> set[str]:
    """Explizit gelabelte Kundennummern – als Rechnungsnummer verboten."""
    found: set[str] = set()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        # Header-Zeile mit beiden Labels: Werte der nächsten Zeile nach Spalte.
        kunden = list(KUNDEN_LABEL_RE.finditer(line))
        rechnung = list(LABEL_RECHNUNGSNUMMER_ONLY_RE.finditer(line))
        if kunden and rechnung and index + 1 < len(lines):
            next_line = ""
            for candidate in lines[index + 1 :]:
                if candidate.strip():
                    next_line = candidate
                    break
            values = _line_value_tokens(next_line) if next_line else []
            if len(values) >= 2:
                if kunden[0].start() < rechnung[0].start():
                    found.add(values[0])
                else:
                    found.add(values[1])
                continue

        for match in LABEL_KUNDENNUMMER_RE.finditer(line):
            value = _clean_rechnungsnummer(match.group(1))
            if value:
                found.add(value)
    return found


def _extract_rechnungsnummer(text: str) -> str | None:
    header_value = _extract_from_kunden_rechnung_headers(text)
    if header_value:
        return header_value

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

    kundennummern = _collect_kundennummern(text)

    for match in LABEL_RECHNUNGSNUMMER_RE.finditer(text):
        # Auf reinen Header-Zeilen (Label neben Kundennummer) nicht den
        # ersten Wert der Folgezeile greifen – das erledigt der Header-Pfad.
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end < 0:
            line_end = len(text)
        line = text[line_start:line_end]
        if KUNDEN_LABEL_RE.search(line) and LABEL_RECHNUNGSNUMMER_ONLY_RE.search(line):
            continue

        value = _clean_rechnungsnummer(match.group(1))
        if not value:
            continue
        if value in kundennummern:
            continue
        return value

    match = CODE_RECHNUNGSNUMMER_RE.search(text)
    if match:
        code = match.group(0).strip()
        if code not in kundennummern:
            return code

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


def _amount_after_label(text: str, match: re.Match[str]) -> float | None:
    after = text[match.end() : match.end() + _AMOUNT_SEARCH_WINDOW]
    if _is_skonto_zahlbetrag_context(match.group(0), after):
        return None
    amount_match = _AMOUNT_AFTER_RE.search(after)
    if not amount_match:
        return None
    try:
        return parse_german_number(amount_match.group(1))
    except ValueError:
        return None


def _extract_betrag(text: str) -> tuple[float | None, str]:
    for label_re in _BETRAG_LABEL_RES:
        for match in label_re.finditer(text):
            betrag = _amount_after_label(text, match)
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


def _extract_labeled_betrag(text: str, label_res: list[re.Pattern[str]]) -> float | None:
    for label_re in label_res:
        for match in label_re.finditer(text):
            betrag = _amount_after_label(text, match)
            if betrag is not None:
                return betrag
    return None


def derive_missing_amounts(
    brutto: float | None,
    netto: float | None,
    steuer: float | None,
) -> tuple[float | None, float | None]:
    """Ergänzt Netto oder Steuer aus Brutto, wenn genau eines fehlt."""
    if brutto is None:
        return netto, steuer
    if netto is not None and steuer is None:
        derived = round(brutto - netto, 2)
        if derived >= 0:
            return netto, derived
    if steuer is not None and netto is None:
        derived = round(brutto - steuer, 2)
        if derived >= 0:
            return derived, steuer
    return netto, steuer


def extract_invoice_data(text: str) -> ExtractionResult:
    rechnungsnummer = _extract_rechnungsnummer(text)
    rechnungsbetrag, waehrung = _extract_betrag(text)
    nettobetrag = _extract_labeled_betrag(text, _NETTO_LABEL_RES)
    steuerbetrag = _extract_labeled_betrag(text, _STEUER_LABEL_RES)
    nettobetrag, steuerbetrag = derive_missing_amounts(
        rechnungsbetrag, nettobetrag, steuerbetrag
    )

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
        nettobetrag=nettobetrag,
        steuerbetrag=steuerbetrag,
    )
