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

# Datum in Tabellenzeilen (tt.mm.jjjj) – Anker für Spalten KD-Nr. / Rechn.Nr.
_DATE_TOKEN_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{2,4}$")

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

# Betrag-Labels in absteigender Spezifität, gruppiert in Tiers für Scoring.
_BETRAG_LABEL_TIERS: list[tuple[list[str], float]] = [
    (
        [
            "Gesamtbetrag",
            "Rechnungsbetrag",
            "Bruttobetrag",
            "Endbetrag",
            r"Offener\s+Restbetrag",
            r"Invoice\s*total",
            r"Total\s*amount",
            r"Amount\s*due",
        ],
        100.0,
    ),
    (
        [
            "Zahlbetrag",
            r"Zu\s*zahlen",
        ],
        75.0,
    ),
    (
        [
            r"\bGesamt\b",
            r"\bTotal\b",
        ],
        50.0,
    ),
    (
        [
            r"\bSumme\b",
            r"\bBetrag\b",
        ],
        25.0,
    ),
]

_COMPILED_LABEL_TIERS: list[tuple[list[tuple[re.Pattern[str], str]], float]] = [
    ([(re.compile(part, re.IGNORECASE), part) for part in parts], weight)
    for parts, weight in _BETRAG_LABEL_TIERS
]

_BETRAG_LABEL_PARTS = [
    part for parts, _ in _BETRAG_LABEL_TIERS for part in parts
]

_BETRAG_LABEL_RES = [re.compile(part, re.IGNORECASE) for part in _BETRAG_LABEL_PARTS]

# Netto / Steuer – eigene Labels, damit sie nicht den Brutto-Endbetrag überschreiben.
_NETTO_LABEL_PARTS = [
    "Nettobetrag",
    "Nettosumme",
    "Nettowert",
    "Warenwert",
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

# Starke Folgelabels: Suche nach dem Betrag nicht über den nächsten Block hinaus.
_STOP_LABEL_RE = re.compile(
    r"(?:"
    r"Gesamtbetrag|Rechnungsbetrag|Bruttobetrag|Endbetrag"
    r"|Nettobetrag|Nettosumme|Nettowert|Warenwert"
    r"|Steuerbetrag|Mehrwertsteuer|Umsatzsteuer"
    r"|Offener\s+Restbetrag|Zahlbetrag"
    r")",
    re.IGNORECASE,
)

# Spaltenköpfe vor "Nettowert" in Positionstabellen (nicht die Rechnungssumme).
_COLUMN_HEADER_HINT_RE = re.compile(
    r"\b(?:menge|e-?preis|einzelpreis|position|bezeichnung|"
    r"lv-?nummer|material|werksnummer|bestellnummer|einheit)\b",
    re.IGNORECASE,
)

# Betrags-Token: vollständige Dezimalzahl bevorzugen; kein abgeschnittenes
# "24" aus "24,15" und kein Datum "02.09.2026" (Jahr nicht als eigene Zahl).
_AMOUNT_TOKEN = (
    r"(?:"
    r"\d{1,3}(?:[.\s]\d{3})+,\d{2}"  # 1.234,56
    r"|\d{1,3}(?:[.\s]\d{3})+"  # 1.234
    r"|\d+,\d{2}"  # 24,15
    r"|\d+\.\d{2}(?!\.\d)"  # 24.15, aber nicht 02.09.2026
    r"|(?<!\.)\d+(?![.,]\d)"  # ganze Zahl, nicht Jahr von 17.08.2026
    r")"
)

_CURRENCY_TOKEN_RE = re.compile(r"€|EUR|Euro|CHF|USD|\$", re.IGNORECASE)
_DATE_YEAR_PREFIX_RE = re.compile(r"\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*$")
_ISO_DATE_SUFFIX_RE = re.compile(r"\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,2}\b")
_AUS_BASE_PREFIX_RE = re.compile(r"\baus\s*$", re.IGNORECASE)
_YEAR_MIN = 1900
_YEAR_MAX = 2099
_MAX_VAT_RATIO = 0.30

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
class AmountCandidate:
    value: float
    currency: str
    label: str
    tier_weight: float
    pos: int
    score: float = 0.0


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


def _is_date_token(token: str) -> bool:
    return bool(_DATE_TOKEN_RE.fullmatch(token.strip()))


def _parse_header_line_tokens(line: str) -> list[str]:
    tokens: list[str] = []
    for raw in _VALUE_TOKEN_RE.findall(line):
        if _is_date_token(raw):
            tokens.append(raw)
            continue
        cleaned = _clean_rechnungsnummer(raw)
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _collect_header_value_tokens(
    lines: list[str], start_index: int
) -> tuple[list[str], int | None]:
    """Sammelt ID-Werte (+ optional Datum) nach Spaltenkopf, nicht Betragszeilen."""
    content_lines: list[str] = []
    for candidate in lines[start_index : start_index + 4]:
        if candidate.strip():
            content_lines.append(candidate)
        if len(content_lines) >= 2:
            break
    if not content_lines:
        return [], None

    first = _parse_header_line_tokens(content_lines[0])
    for index, token in enumerate(first):
        if _is_date_token(token):
            return first, index

    tokens = list(first)
    # Zweite Zeile nur mitziehen, wenn sie mit dem Datum beginnt (Split-Layout).
    if len(content_lines) > 1:
        second = _parse_header_line_tokens(content_lines[1])
        if second and _is_date_token(second[0]):
            date_at = len(tokens)
            tokens.extend(second)
            return tokens, date_at

    return tokens, None


def _rechnungsnummer_from_header_tokens(
    tokens: list[str],
    date_at: int | None,
    kunden_first: bool,
) -> str | None:
    """
    Bei Spalten KD-Nr. | Rechn.Nr. [| Datum | Blatt]:
    Rechnungsnummer = Token direkt vor dem Datum, sonst letzte ID-Spalte
    (Kundennummer kann mehrteilig sein, z. B. '926 L02634').
    """
    if date_at is not None and date_at >= 1:
        return tokens[date_at - 1]

    id_tokens = [token for token in tokens if not _is_date_token(token)]
    if len(id_tokens) < 2:
        return None
    if kunden_first:
        return id_tokens[-1]
    return id_tokens[0]


def _kundennummern_from_header_tokens(
    tokens: list[str],
    date_at: int | None,
    kunden_first: bool,
) -> set[str]:
    found: set[str] = set()
    if date_at is not None and date_at >= 1:
        rechnung = tokens[date_at - 1]
        for token in tokens[:date_at]:
            if token != rechnung and not _is_date_token(token):
                found.add(token)
        return found

    id_tokens = [token for token in tokens if not _is_date_token(token)]
    if len(id_tokens) < 2:
        return found
    if kunden_first:
        found.update(id_tokens[:-1])
    else:
        found.update(id_tokens[1:])
    return found


def _extract_from_kunden_rechnung_headers(text: str) -> str | None:
    """Spaltenköpfe Kundennummer + Rechnungsnummer → richtige Spalte wählen."""
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        kunden = list(KUNDEN_LABEL_RE.finditer(line))
        rechnung = list(LABEL_RECHNUNGSNUMMER_ONLY_RE.finditer(line))
        if not kunden or not rechnung:
            continue

        tokens, date_at = _collect_header_value_tokens(lines, index + 1)
        value = _rechnungsnummer_from_header_tokens(
            tokens, date_at, kunden_first=kunden[0].start() < rechnung[0].start()
        )
        if value:
            return value
    return None


def _collect_kundennummern(text: str) -> set[str]:
    """Explizit gelabelte Kundennummern – als Rechnungsnummer verboten."""
    found: set[str] = set()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        kunden = list(KUNDEN_LABEL_RE.finditer(line))
        rechnung = list(LABEL_RECHNUNGSNUMMER_ONLY_RE.finditer(line))
        if kunden and rechnung and index + 1 < len(lines):
            tokens, date_at = _collect_header_value_tokens(lines, index + 1)
            found.update(
                _kundennummern_from_header_tokens(
                    tokens,
                    date_at,
                    kunden_first=kunden[0].start() < rechnung[0].start(),
                )
            )
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


def _is_positionssumme_context(label: str, after_slice: str) -> bool:
    """'Summe Positionen' ist eine Zwischensumme, nicht der Rechnungsbetrag."""
    return bool(re.search(r"summe\s+position", label + after_slice[:40], re.IGNORECASE))


def _truncate_at_next_label(after: str) -> str:
    """Nicht über den nächsten Betragsblock (Endbetrag, MwSt, …) hinaus suchen."""
    stop = _STOP_LABEL_RE.search(after)
    if stop and stop.start() > 0:
        return after[: stop.start()]
    return after


def _is_column_header_match(text: str, match: re.Match[str]) -> bool:
    """True, wenn das Label in einer Positionstabelle steht, nicht bei der Summe."""
    before = text[max(0, match.start() - 160) : match.start()]
    return len(_COLUMN_HEADER_HINT_RE.findall(before)) >= 2


def _is_date_year_token(haystack: str, token_start: int, token_end: int) -> bool:
    """Jahresanteil von 17.08.2026 / 2026-08-17 nicht als Betrag werten."""
    prefix = haystack[max(0, token_start - 12) : token_start]
    if _DATE_YEAR_PREFIX_RE.search(prefix):
        return True
    suffix = haystack[token_end : token_end + 8]
    return bool(_ISO_DATE_SUFFIX_RE.match(suffix))


def _is_year_like_without_currency(
    raw: str, value: float, haystack: str, token_start: int, token_end: int
) -> bool:
    """Vierstellige Jahreszahl ohne Währung (z. B. 2026) ist kein Betrag."""
    if not re.fullmatch(r"\d{4}", raw.strip()):
        return False
    if value != int(value) or not (_YEAR_MIN <= int(value) <= _YEAR_MAX):
        return False
    around = haystack[max(0, token_start - 8) : token_end + 8]
    return not _CURRENCY_TOKEN_RE.search(around)


def _is_aus_bemessungsgrundlage(haystack: str, token_start: int) -> bool:
    """MwSt-Zeile: Betrag nach 'aus' ist die Netto-Bemessungsgrundlage, nicht die Steuer."""
    prefix = haystack[max(0, token_start - 12) : token_start]
    return bool(_AUS_BASE_PREFIX_RE.search(prefix))


def _is_plausible_amount(
    raw: str, value: float, haystack: str, token_start: int, token_end: int
) -> bool:
    if value < 0:
        return False
    if _is_date_year_token(haystack, token_start, token_end):
        return False
    if _is_year_like_without_currency(raw, value, haystack, token_start, token_end):
        return False
    return True


def _amount_after_label(
    text: str,
    match: re.Match[str],
    *,
    skip_aus_base: bool = False,
) -> float | None:
    after = text[match.end() : match.end() + _AMOUNT_SEARCH_WINDOW]
    after = _truncate_at_next_label(after)
    if _is_skonto_zahlbetrag_context(match.group(0), after):
        return None
    if _is_positionssumme_context(match.group(0), after):
        return None
    for amount_match in _AMOUNT_AFTER_RE.finditer(after):
        raw = amount_match.group(1)
        token_start = amount_match.start(1)
        token_end = amount_match.end(1)
        if skip_aus_base and _is_aus_bemessungsgrundlage(after, token_start):
            continue
        try:
            value = parse_german_number(raw)
        except ValueError:
            continue
        if _is_plausible_amount(raw, value, after, token_start, token_end):
            return value
    return None


def _collect_betrag_candidates(text: str) -> list[AmountCandidate]:
    candidates: list[AmountCandidate] = []
    seen_positions: set[tuple[int, float]] = set()

    for patterns, tier_weight in _COMPILED_LABEL_TIERS:
        for pattern, label_name in patterns:
            for match in pattern.finditer(text):
                betrag = _amount_after_label(text, match)
                if betrag is not None:
                    key = (match.start(), betrag)
                    if key not in seen_positions:
                        seen_positions.add(key)
                        context = text[max(0, match.start() - 30) : match.end() + 50]
                        candidates.append(
                            AmountCandidate(
                                value=betrag,
                                currency=_detect_currency(context),
                                label=label_name,
                                tier_weight=tier_weight,
                                pos=match.start(),
                            )
                        )

    for generic in BETRAG_GENERISCH_RE.finditer(text):
        raw = generic.group(1) or generic.group(2)
        if raw:
            try:
                betrag = parse_german_number(raw, force_german=True)
            except ValueError:
                betrag = None
            if betrag is not None:
                token_start = generic.start(1) if generic.group(1) else generic.start(2)
                token_end = generic.end(1) if generic.group(1) else generic.end(2)
                if _is_plausible_amount(raw, betrag, generic.string, token_start, token_end):
                    key = (generic.start(), betrag)
                    if key not in seen_positions:
                        seen_positions.add(key)
                        candidates.append(
                            AmountCandidate(
                                value=betrag,
                                currency=_detect_currency(generic.group(0)),
                                label="generisch",
                                tier_weight=10.0,
                                pos=generic.start(),
                            )
                        )

    return candidates


def _score_betrag_candidates(
    candidates: list[AmountCandidate],
    text_len: int,
    netto: float | None,
    steuer: float | None,
) -> list[AmountCandidate]:
    doc_len = max(text_len, 1)
    for c in candidates:
        score = c.tier_weight
        pos_ratio = c.pos / doc_len
        score += pos_ratio * 20.0

        if netto is not None and steuer is not None:
            sum_ns = round(netto + steuer, 2)
            if abs(sum_ns - c.value) <= max(0.05, 0.01 * c.value):
                score += 60.0
            elif abs(c.value - netto) <= 0.02:
                score -= 40.0
            elif c.value < netto - 0.02:
                score -= 50.0
            elif abs(c.value - steuer) <= 0.02:
                score -= 50.0
        elif netto is not None:
            if c.value > netto + 0.02:
                vat_19 = round(netto * 1.19, 2)
                vat_7 = round(netto * 1.07, 2)
                if abs(c.value - vat_19) <= max(0.05, 0.01 * c.value) or abs(c.value - vat_7) <= max(0.05, 0.01 * c.value):
                    score += 30.0
                else:
                    score += 10.0
            elif abs(c.value - netto) <= 0.02:
                score -= 30.0
            elif c.value < netto - 0.02:
                score -= 50.0
        elif steuer is not None:
            if c.value > steuer + 0.02:
                vat_ratio = steuer / c.value if c.value > 0 else 0
                if 0.05 <= vat_ratio <= _MAX_VAT_RATIO:
                    score += 15.0
                else:
                    score += 5.0
            else:
                score -= 50.0

        c.score = score

    return sorted(candidates, key=lambda x: (x.score, x.pos), reverse=True)


def _extract_betrag(
    text: str,
    netto: float | None = None,
    steuer: float | None = None,
) -> tuple[float | None, str]:
    if netto is None and steuer is None:
        netto = _extract_labeled_betrag(text, _NETTO_LABEL_RES, skip_column_headers=True)
        steuer = _extract_labeled_betrag(text, _STEUER_LABEL_RES, skip_aus_base=True)

    candidates = _collect_betrag_candidates(text)
    if not candidates:
        return None, "EUR"

    scored = _score_betrag_candidates(candidates, len(text), netto, steuer)
    best = scored[0]
    return best.value, best.currency


def _extract_labeled_betrag(
    text: str,
    label_res: list[re.Pattern[str]],
    *,
    skip_aus_base: bool = False,
    skip_column_headers: bool = False,
) -> float | None:
    for label_re in label_res:
        for match in label_re.finditer(text):
            if skip_column_headers and _is_column_header_match(text, match):
                continue
            betrag = _amount_after_label(text, match, skip_aus_base=skip_aus_base)
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


def reconcile_amounts(
    brutto: float | None,
    netto: float | None,
    steuer: float | None,
) -> tuple[float | None, float | None]:
    """Verwirft unplausible Netto-/Steuerwerte und ergänzt die fehlende Größe."""
    if brutto is not None:
        if netto is not None and netto > brutto + 0.02:
            netto = None
        if steuer is not None:
            too_large = steuer >= brutto - 0.02
            vat_ratio = steuer / brutto if brutto else 0
            if too_large or vat_ratio > _MAX_VAT_RATIO:
                steuer = None

    netto, steuer = derive_missing_amounts(brutto, netto, steuer)

    if (
        brutto is not None
        and netto is not None
        and steuer is not None
        and abs((netto + steuer) - brutto) > max(0.05, 0.01 * abs(brutto))
    ):
        if netto <= brutto + 0.02:
            return derive_missing_amounts(brutto, netto, None)
        if steuer < brutto and (steuer / brutto) <= _MAX_VAT_RATIO:
            return derive_missing_amounts(brutto, None, steuer)
        return None, None

    return netto, steuer


def extract_invoice_data(text: str) -> ExtractionResult:
    rechnungsnummer = _extract_rechnungsnummer(text)
    nettobetrag = _extract_labeled_betrag(
        text, _NETTO_LABEL_RES, skip_column_headers=True
    )
    steuerbetrag = _extract_labeled_betrag(
        text, _STEUER_LABEL_RES, skip_aus_base=True
    )
    rechnungsbetrag, waehrung = _extract_betrag(
        text, netto=nettobetrag, steuer=steuerbetrag
    )
    nettobetrag, steuerbetrag = reconcile_amounts(
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
