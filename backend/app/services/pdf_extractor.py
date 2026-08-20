from __future__ import annotations

from pathlib import Path

import fitz


def extract_text(source: str | Path | bytes) -> str:
    """Extrahiert den Text aus einem PDF.

    Akzeptiert einen Dateipfad (str/Path) oder die rohen PDF-Daten als bytes
    (für PDFs aus dem Supabase Storage).
    """
    try:
        if isinstance(source, bytes):
            document = fitz.open(stream=source, filetype="pdf")
        else:
            document = fitz.open(str(source))
    except Exception as exc:
        raise ValueError(f"PDF konnte nicht geöffnet werden: {exc}") from exc

    try:
        pages = [page.get_text() for page in document]
        text = "\n".join(pages)
    finally:
        document.close()

    if not text.strip():
        raise ValueError("Kein Text aus dem PDF extrahierbar (möglicherweise ein gescanntes Dokument).")

    return text