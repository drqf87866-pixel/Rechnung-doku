from __future__ import annotations

from pathlib import Path

import fitz


def extract_text(source: str | Path | bytes) -> str:
    """Extrahiert den Text aus einem PDF per PyMuPDF (nur digitale Textschicht).

    Für gescannte PDFs ohne Textschicht liefert diese Funktion wenig oder keinen
    Text. Der Hybrid-Extraktor (`invoice_extractor`) leitet solche Fälle an
    Gemini Flash weiter.
    """
    try:
        if isinstance(source, bytes):
            document = fitz.open(stream=source, filetype="pdf")
        else:
            document = fitz.open(str(source))
    except Exception as exc:
        raise ValueError(f"PDF konnte nicht geöffnet werden: {exc}") from exc

    try:
        return "\n".join(page.get_text() for page in document)
    finally:
        document.close()
