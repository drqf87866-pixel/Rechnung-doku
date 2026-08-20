from __future__ import annotations

import threading
from pathlib import Path

import fitz

from app.config import settings

_MAX_RENDER_SIDE = settings.ocr_max_side
_DOTS_PER_POINT = 200.0 / 72.0
_MIN_DIGITAL_TEXT = 20

_engine = None
_engine_lock = threading.Lock()


def _get_ocr_engine():
    """Lazy-Singleton für den RapidOCR-Engine (Modell-Laden dauert ~1s)."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from rapidocr import RapidOCR

                _engine = RapidOCR()
    return _engine


def _text_via_pymupdf(document: fitz.Document) -> str:
    return "\n".join(page.get_text() for page in document)


def _text_via_ocr(document: fitz.Document) -> str:
    """OCR-Fallback für gescannte PDFs ohne Textschicht.

    Rendert jede Seite per PyMuPDF und liest den Text mit RapidOCR
    (pip-installierbar, keine System-Binaries nötig).

    Die Rastergröße wird über eine Zoom-Matrix begrenzt statt über eine fixe
    DPI: Scanner-PDFs setzen die Seitenbox oft in Punkten gleich der
    Pixelgröße (z. B. 2480x3508 pt), wodurch get_pixmap(dpi=300) eine enorme
    Bitmap liefert. RapidOCR skaliert intern ohnehin auf max. 2000 px, daher
    kostet die Begrenzung keine Erkennungsqualität, spart aber massiv Speicher.
    """
    import numpy as np

    engine = _get_ocr_engine()
    pages: list[str] = []

    for page in document:
        rect = page.rect
        zoom = min(_DOTS_PER_POINT, _MAX_RENDER_SIDE / max(rect.width, rect.height))
        pix = page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csRGB, alpha=False
        )
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        output = engine(image)
        if not output or not output.txts:
            continue
        # RapidOCR liefert die Zeilen bereits in Lesereihenfolge.
        pages.append("\n".join(output.txts))

    return "\n".join(pages)


def extract_text(source: str | Path | bytes) -> str:
    """Extrahiert den Text aus einem PDF.

    Akzeptiert einen Dateipfad (str/Path) oder die rohen PDF-Daten als bytes
    (für PDFs aus dem Supabase Storage). Digitalen PDFs wird der Text direkt
    entnommen; gescannte PDFs (ohne Textschicht) werden per OCR gelesen.
    """
    try:
        if isinstance(source, bytes):
            document = fitz.open(stream=source, filetype="pdf")
        else:
            document = fitz.open(str(source))
    except Exception as exc:
        raise ValueError(f"PDF konnte nicht geöffnet werden: {exc}") from exc

    try:
        text = _text_via_pymupdf(document)
        if len(text.strip()) >= _MIN_DIGITAL_TEXT:
            return text

        try:
            text = _text_via_ocr(document)
        except ImportError as exc:
            raise ValueError(
                "Das PDF enthält keine Textschicht (Scan) und die OCR-Abhängigkeit "
                "'rapidocr' ist nicht installiert."
            ) from exc

        if not text.strip():
            raise ValueError(
                "Kein Text aus dem PDF extrahierbar (OCR lieferte keine Ergebnisse)."
            )
        return text
    finally:
        document.close()
