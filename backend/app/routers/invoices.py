from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas, storage
from app.access import (
    invoice_visibility_filter,
    user_can_access_invoice,
    user_can_manage_invoice,
    user_can_share_bauvorhaben,
)
from app.security import get_current_user, get_db
from app.services.invoice_extractor import extract_from_pdf
from app.services.regex_extractor import parse_german_number

router = APIRouter(prefix="/api")


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


def _get_visible_or_404(
    db: Session, user: models.User, invoice_id: int
) -> models.Invoice:
    invoice = db.get(models.Invoice, invoice_id)
    if invoice is None or not user_can_access_invoice(db, user, invoice):
        raise HTTPException(status_code=404, detail="Rechnung nicht gefunden")
    return invoice


@router.post("/invoices", response_model=schemas.InvoiceOut, status_code=201)
def upload_invoice(
    file: UploadFile = File(...),
    bauvorhaben: str = Form(...),
    rechnungsnummer: Optional[str] = Form(default=None),
    rechnungsbetrag: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
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

    result = extract_from_pdf(data)
    hinweise: list[str] = []
    extracted_nummer = result.rechnungsnummer
    extracted_betrag = result.rechnungsbetrag
    extracted_netto = result.nettobetrag
    extracted_steuer = result.steuerbetrag
    waehrung = result.waehrung
    if result.hinweise:
        hinweise.append(result.hinweise)

    final_nummer = extracted_nummer
    final_betrag = extracted_betrag
    final_netto = extracted_netto
    final_steuer = extracted_steuer
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
        owner_id=user.id,
        filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        bauvorhaben=bauvorhaben,
        rechnungsnummer=final_nummer,
        rechnungsbetrag=final_betrag,
        nettobetrag=final_netto,
        steuerbetrag=final_steuer,
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
    user: models.User = Depends(get_current_user),
) -> list[models.Invoice]:
    stmt = (
        select(models.Invoice)
        .where(invoice_visibility_filter(db, user.id))
        .order_by(models.Invoice.id.desc())
    )
    if bauvorhaben:
        stmt = stmt.where(models.Invoice.bauvorhaben == bauvorhaben)
    return list(db.execute(stmt).scalars().all())


@router.get("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.Invoice:
    return _get_visible_or_404(db, user, invoice_id)


@router.patch("/invoices/{invoice_id}", response_model=schemas.InvoiceOut)
def patch_invoice(
    invoice_id: int,
    payload: schemas.InvoicePatch,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.Invoice:
    invoice = _get_visible_or_404(db, user, invoice_id)
    if not user_can_manage_invoice(user, invoice):
        raise HTTPException(
            status_code=403,
            detail="Nur der Eigentümer darf diese Rechnung bearbeiten",
        )
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if isinstance(value, str) and not value.strip():
            value = None
        setattr(invoice, key, value)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.delete("/invoices/{invoice_id}", status_code=204)
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> None:
    invoice = _get_visible_or_404(db, user, invoice_id)
    if not user_can_manage_invoice(user, invoice):
        raise HTTPException(
            status_code=403,
            detail="Nur der Eigentümer darf diese Rechnung löschen",
        )
    stored = invoice.stored_filename
    db.delete(invoice)
    db.commit()
    storage.delete_file(stored)


@router.get("/invoices/{invoice_id}/file")
def get_invoice_file(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> Response:
    invoice = _get_visible_or_404(db, user, invoice_id)

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


@router.get("/bauvorhaben", response_model=list[schemas.BauvorhabenInfo])
def list_bauvorhaben(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[schemas.BauvorhabenInfo]:
    names = list(
        db.execute(
            select(models.Invoice.bauvorhaben)
            .where(invoice_visibility_filter(db, user.id))
            .distinct()
            .order_by(models.Invoice.bauvorhaben)
        ).scalars().all()
    )
    # Auch Bauvorhaben ohne Rechnungen, für die ich nur Freigaben halte
    share_names = list(
        db.execute(
            select(models.BauvorhabenShare.bauvorhaben)
            .where(
                (models.BauvorhabenShare.owner_id == user.id)
                | (models.BauvorhabenShare.shared_with_user_id == user.id)
            )
            .distinct()
        ).scalars().all()
    )
    all_names = sorted(set(names) | set(share_names), key=lambda n: n.lower())

    result: list[schemas.BauvorhabenInfo] = []
    for name in all_names:
        share_hit = db.execute(
            select(models.BauvorhabenShare.id)
            .where(
                models.BauvorhabenShare.bauvorhaben == name,
                (models.BauvorhabenShare.owner_id == user.id)
                | (models.BauvorhabenShare.shared_with_user_id == user.id),
            )
            .limit(1)
        ).scalar_one_or_none()
        result.append(
            schemas.BauvorhabenInfo(
                name=name,
                is_shared=share_hit is not None,
                can_manage_shares=user_can_share_bauvorhaben(db, user.id, name),
            )
        )
    return result
