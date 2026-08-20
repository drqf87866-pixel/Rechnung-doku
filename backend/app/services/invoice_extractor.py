from __future__ import annotations

from app.services.llm_extractor import extract_invoice_data_via_llm
from app.services.pdf_extractor import extract_text
from app.services.regex_extractor import ExtractionResult, extract_invoice_data

_MIN_DIGITAL_TEXT = 20


def _has_both_fields(result: ExtractionResult) -> bool:
    return result.rechnungsnummer is not None and result.rechnungsbetrag is not None


def _has_any_field(result: ExtractionResult) -> bool:
    return result.rechnungsnummer is not None or result.rechnungsbetrag is not None


def extract_from_pdf(pdf_bytes: bytes) -> ExtractionResult:
    """Hybrid-Extraktion: PyMuPDF + Regex, Gemini bei Scans oder unvollständiger Regex."""
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

    if len(text.strip()) < _MIN_DIGITAL_TEXT:
        return extract_invoice_data_via_llm(pdf_bytes)

    regex_result = extract_invoice_data(text)
    if _has_both_fields(regex_result):
        return regex_result

    llm_result = extract_invoice_data_via_llm(pdf_bytes)
    if _has_any_field(llm_result):
        return llm_result

    # Gemini ohne Key / fehlgeschlagen: Regex-Teilergebnis behalten.
    if _has_any_field(regex_result):
        return regex_result
    return llm_result
