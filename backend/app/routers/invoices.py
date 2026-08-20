from __future__ import annotations

from typing import Generator, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas, storage
from app.database import SessionLocal
from app.services.pdf_extractor import extract_text
from app.services.regex_extractor import extract_invoice_data, parse_german_number

router = APIRouter(prefix="/api")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _attachment_header(filename: str) -> str:
    """Content-Disposition für den Download, mit RFC-5987-Kodierung für Umlaute.

    Entspricht der Kodierung, die Starlette in FileResponse verwendet.
    """
    encoded = quote(filename)
    if encoded != filename:
        return f"attachment; filename*=utf-8''{encoded}"
    return f'attachment; filename="{filename}"'


def _is_pdf(file: UploadFile) -> bool:
    if file.content_type and file.content_type.lower() == "application/pdf":
        return True
    filename = file.filename or ""
    return filename.lower().endswith(".pdf")


def _get_or_404(db: Session, invoice_id: int) -> models.Invoice:
    invoice = db.get(models.Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    return invoice


@router.post("/invoices", response_model=schemas.InvoiceOut, status_code=201)
def upload_invoice(
    file: UploadFile = File(...),
    bauvorhaben: str = Form(...),
    rechnungsnummer: Optional[str] = Form(default=None),
    rechnungsbetrag: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
) -> models.Invoice:
    if not _is_pdf(file):
        raise HTTPException(status_code=400, detail="Nur PDF-Dateien sind erlaubt")

    bauvorhaben = bauvorhaben.strip()
    if not bauvorhaben:
        raise HTTPException(status_code=400, detail="Bauvorhaben ist erforderlich")

    # save_upload liefert die Datei-Bytes mit zurück – so wird die Textextraktion
    # ohne zweiten Netzwerk-Round-Trip und ohne Orphan-Risiko ausgeführt.
    try:
        stored_filename, data = storage.save_upload(file)
    except storage.StorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    hinweise: list[str] = []
    extracted_nummer: Optional[str] = None
    extracted_betrag: Optional[float] = None
    waehrung = "EUR"

    try:
        text = extract_text(data)
    except ValueError as exc:
        hinweise.append(str(exc))
    else:
        result = extract_invoice_data(text)
        extracted_nummer = result.rechnungsnummer
        extracted_betrag = result.rechnungsbetrag
        waehrung = result.waehrung
        if result.hinweise:
            hinweise.append(result.hinweise)

    final_nummer = extracted_nummer
    final_betrag = extracted_betrag
    manual_override = False

    if rechnungsnummer is not None and rechnungsnummer.strip():
        final_nummer = rechnungsnummer.strip()
        manual_override = True

    if rechnungsbetrag is not None and rechnungsbetrag.strip():
        try:
            final_betrag = parse_german_number(rechnungsbetrag.strip())
            manual_override = True
        except ValueError:
            hinweise.append("Ungültiger manueller Rechnungsbetrag")

    if manual_override:
        konfidenz = 1.0
    elif final_nummer is not None and final_betrag is not None:
        konfidenz = 1.0
    elif final_nummer is not None or final_betrag is not None:
        konfidenz = 0.6
    else:
        konfidenz = 0.0

    invoice = models.Invoice(
        filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        bauvorhaben=bauvorhaben,
        rechnungsnummer=final_nummer,
        rechnungsbetrag=final_betrag,
        waehrung=waehrung,
        konfidenz=konfidenz,
        hinweise="; ".join(hinweise) if hinweise else None,
    )

    try:
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
    except Exception:
        db.rollback()
        storage.delete_file(stored_filename)
        raise HTTPException(status_code=500, detail="Fehler beim Speichern der Rechnung")

    return invoice


@router.get("/invoices", response_model=list[schemas.InvoiceOut])
def list_invoices(
    bauvorhaben: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> list[models.Invoice]:
    stmt = select(models.Invoice).order_by(models.Invoice.id.desc())
    if bauvorhaben:
        stmt = stmt.where(models.Invoice.bauvorhaben == bauvorhaben)
    return list(db.execute(stmt).scalars().all())


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)) -> models.Invoice:
    return _get_or_404(db, invoice_id)


@router.patch("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def patch_invoice(
    invoice_id: int,
    payload: schemas.InvoicePatch,
    db: Session = Depends(get_db),
) -> models.Invoice:
    invoice = _get_or_404(db, invoice_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if isinstance(value, str) and not value.strip():
            value = None
        setattr(invoice, key, value)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.delete("/invoices/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)) -> None:
    invoice = _get_or_404(db, invoice_id)
    db.delete(invoice)
    db.commit()
    # Fehler beim Storage-Löschen werden in storage.delete_file geloggt und
    # schlucken nicht länger still – ein evtl. verbleibendes Orphan ist so
    # in den Logs auffindbar.
    storage.delete_file(invoice.stored_filename)


@router.get("/invoices/{invoice_id}/file")
def get_invoice_file(invoice_id: int, db: Session = Depends(get_db)) -> Response:
    invoice = _get_or_404(db, invoice_id)

    # Lokaler Fallback: wie bisher streamen (Range-/Caching-Support).
    local_path = storage.get_local_path(invoice.stored_filename)
    if local_path is not None:
        return FileResponse(
            local_path,
            media_type="application/pdf",
            filename=invoice.filename,
        )

    try:
        data = storage.read_bytes(invoice.stored_filename)
    except storage.StorageNotFound as exc:
        raise HTTPException(status_code=404, detail="PDF-Datei nicht gefunden") from exc
    except storage.StorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": _attachment_header(invoice.filename)},
    )


@router.get("/bauvorhaben")
def list_bauvorhaben(db: Session = Depends(get_db)) -> list[str]:
    rows = db.execute(
        select(models.Invoice.bauvorhaben).distinct().order_by(models.Invoice.bauvorhaben)
    ).scalars().all()
    return list(rows)