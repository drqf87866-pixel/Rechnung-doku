from __future__ import annotations

from app.services.llm_extractor import extract_invoice_data_via_llm
from app.services.pdf_extractor import extract_text
from app.services.regex_extractor import ExtractionResult, extract_invoice_data

_MIN_DIGITAL_TEXT = 20


def extract_from_pdf(pdf_bytes: bytes) -> ExtractionResult:
    """Hybrid-Extraktion: PyMuPDF + Regex für digitale PDFs, Gemini für Scans."""
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

    if len(text.strip()) >= _MIN_DIGITAL_TEXT:
        return extract_invoice_data(text)

    return extract_invoice_data_via_llm(pdf_bytes)
