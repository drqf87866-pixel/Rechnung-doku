from __future__ import annotations

from pathlib import Path

import fitz


def extract_text(file_path: str | Path) -> str:
    try:
        document = fitz.open(str(file_path))
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
