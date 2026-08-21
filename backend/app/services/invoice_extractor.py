from __future__ import annotations

from app.config import settings
from app.services.llm_extractor import extract_invoice_data_via_llm
from app.services.pdf_extractor import extract_text
from app.services.regex_extractor import (
    ExtractionResult,
    _collect_kundennummern,
    extract_invoice_data,
    reconcile_amounts,
)

_MIN_DIGITAL_TEXT = 20


def _has_both_fields(result: ExtractionResult) -> bool:
    return result.rechnungsnummer is not None and result.rechnungsbetrag is not None


def _has_any_field(result: ExtractionResult) -> bool:
    return result.rechnungsnummer is not None or result.rechnungsbetrag is not None


def _reconcile_results(
    regex_result: ExtractionResult,
    llm_result: ExtractionResult,
    text: str,
) -> ExtractionResult:
    """Führt Regex- und LLM-Ergebnisse zusammen und löst Konflikte arithmetisch auf."""
    hinweise: list[str] = []
    kundennummern = _collect_kundennummern(text)

    # 1. Rechnungsnummer abgleichen
    regex_nr = regex_result.rechnungsnummer
    llm_nr = llm_result.rechnungsnummer
    nummer_conflict = False

    if regex_nr and llm_nr:
        if regex_nr == llm_nr:
            final_nummer = regex_nr
        else:
            nummer_conflict = True
            if llm_nr in kundennummern:
                final_nummer = regex_nr
                hinweise.append(
                    f"Rechnungsnummer: Regex '{regex_nr}' bevorzugt (Gemini '{llm_nr}' ist Kundennummer)"
                )
            else:
                final_nummer = llm_nr
                hinweise.append(
                    f"Rechnungsnummer: Gemini '{llm_nr}' gewählt (Regex war '{regex_nr}')"
                )
    elif regex_nr:
        final_nummer = regex_nr
    elif llm_nr:
        if llm_nr not in kundennummern:
            final_nummer = llm_nr
        else:
            final_nummer = None
    else:
        final_nummer = None

    # 2. Beträge & Arithmetik abgleichen
    regex_betrag = regex_result.rechnungsbetrag
    llm_betrag = llm_result.rechnungsbetrag
    betrag_conflict = False

    cand_netto = (
        llm_result.nettobetrag
        if llm_result.nettobetrag is not None
        else regex_result.nettobetrag
    )
    cand_steuer = (
        llm_result.steuerbetrag
        if llm_result.steuerbetrag is not None
        else regex_result.steuerbetrag
    )

    if regex_betrag is not None and llm_betrag is not None:
        if abs(regex_betrag - llm_betrag) <= 0.01:
            final_betrag = regex_betrag
        else:
            betrag_conflict = True

            def _matches_arithmetic(b: float) -> bool:
                if cand_netto is not None and cand_steuer is not None:
                    return abs((cand_netto + cand_steuer) - b) <= max(0.05, 0.01 * b)
                return False

            regex_valid = _matches_arithmetic(regex_betrag)
            llm_valid = _matches_arithmetic(llm_betrag)

            if llm_valid and not regex_valid:
                final_betrag = llm_betrag
                hinweise.append(
                    f"Rechnungsbetrag: Gemini {llm_betrag:.2f} gewählt "
                    f"(passt zu Netto/Steuer, Regex war {regex_betrag:.2f})"
                )
            elif regex_valid and not llm_valid:
                final_betrag = regex_betrag
                hinweise.append(
                    f"Rechnungsbetrag: Regex {regex_betrag:.2f} gewählt "
                    f"(passt zu Netto/Steuer, Gemini war {llm_betrag:.2f})"
                )
            else:
                if cand_netto is not None and abs(regex_betrag - cand_netto) <= 0.02:
                    final_betrag = llm_betrag
                    hinweise.append(
                        f"Rechnungsbetrag: Gemini {llm_betrag:.2f} gewählt "
                        f"(Regex {regex_betrag:.2f} war Nettobetrag)"
                    )
                elif cand_netto is not None and abs(llm_betrag - cand_netto) <= 0.02:
                    final_betrag = regex_betrag
                    hinweise.append(
                        f"Rechnungsbetrag: Regex {regex_betrag:.2f} gewählt "
                        f"(Gemini {llm_betrag:.2f} war Nettobetrag)"
                    )
                else:
                    final_betrag = llm_betrag
                    hinweise.append(
                        f"Rechnungsbetrag-Konflikt: Gemini {llm_betrag:.2f} vs. Regex {regex_betrag:.2f}"
                    )
    elif regex_betrag is not None:
        final_betrag = regex_betrag
    elif llm_betrag is not None:
        final_betrag = llm_betrag
    else:
        final_betrag = None

    final_netto, final_steuer = reconcile_amounts(final_betrag, cand_netto, cand_steuer)
    final_waehrung = (
        llm_result.waehrung if llm_result.waehrung != "EUR" else regex_result.waehrung
    )

    if final_nummer is None and final_betrag is None:
        konfidenz = 0.0
    elif nummer_conflict or betrag_conflict:
        konfidenz = (
            0.6 if (final_nummer is not None and final_betrag is not None) else 0.4
        )
    else:
        both_found = final_nummer is not None and final_betrag is not None
        if (
            regex_result.rechnungsnummer
            and regex_result.rechnungsbetrag
            and llm_result.rechnungsnummer
            and llm_result.rechnungsbetrag
        ):
            konfidenz = 1.0
        elif both_found:
            konfidenz = 0.9
        else:
            konfidenz = 0.6

    if final_nummer is None:
        hinweise.append("Keine Rechnungsnummer gefunden")
    if final_betrag is None:
        hinweise.append("Kein Rechnungsbetrag gefunden")

    return ExtractionResult(
        rechnungsnummer=final_nummer,
        rechnungsbetrag=final_betrag,
        waehrung=final_waehrung,
        konfidenz=konfidenz,
        hinweise="; ".join(hinweise) if hinweise else None,
        nettobetrag=final_netto,
        steuerbetrag=final_steuer,
    )


def extract_from_pdf(pdf_bytes: bytes) -> ExtractionResult:
    """Hybrid-Extraktion: PyMuPDF + Regex, immer mit Gemini abgeglichen wenn Key vorhanden."""
    try:
        text = extract_text(pdf_bytes)
    except ValueError as exc:
        return ExtractionResult(
            rechnungsnummer=None,
            rechnungsbetrag=None,
            waehrung="EUR",
            konfidenz=0.0,
            hinweise=str(exc),
        )

    is_scan = len(text.strip()) < _MIN_DIGITAL_TEXT

    if is_scan:
        return extract_invoice_data_via_llm(pdf_bytes, text=text)

    regex_result = extract_invoice_data(text)

    if not settings.gemini_api_key:
        return regex_result

    llm_result = extract_invoice_data_via_llm(pdf_bytes, text=text)

    if not _has_any_field(llm_result):
        if llm_result.hinweise and "fehlgeschlagen" in llm_result.hinweise:
            combined_hinweise = [
                h for h in [regex_result.hinweise, llm_result.hinweise] if h
            ]
            regex_result.hinweise = (
                "; ".join(combined_hinweise) if combined_hinweise else None
            )
        return regex_result

    return _reconcile_results(regex_result, llm_result, text)
