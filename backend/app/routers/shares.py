from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.access import user_can_share_bauvorhaben
from app.security import get_current_user, get_db

router = APIRouter(prefix="/api/shares", tags=["shares"])


def _share_out(db: Session, share: models.BauvorhabenShare) -> schemas.ShareOut:
    owner = db.get(models.User, share.owner_id)
    shared_user = db.get(models.User, share.shared_with_user_id)
    return schemas.ShareOut(
        id=share.id,
        bauvorhaben=share.bauvorhaben,
        owner_id=share.owner_id,
        owner_username=owner.username if owner else "?",
        owner_display_name=owner.display_name if owner else "?",
        shared_with_user_id=share.shared_with_user_id,
        shared_with_username=shared_user.username if shared_user else "?",
        shared_with_display_name=shared_user.display_name if shared_user else "?",
        created_at=share.created_at,
    )


@router.get("", response_model=list[schemas.ShareOut])
def list_shares(
    bauvorhaben: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[schemas.ShareOut]:
    name = bauvorhaben.strip()
    # Sichtbar für Owner der Freigabe oder Empfänger
    stmt = select(models.BauvorhabenShare).where(
        models.BauvorhabenShare.bauvorhaben == name,
        (models.BauvorhabenShare.owner_id == user.id)
        | (models.BauvorhabenShare.shared_with_user_id == user.id),
    )
    shares = list(db.execute(stmt).scalars().all())
    return [_share_out(db, share) for share in shares]


@router.post("", response_model=schemas.ShareOut, status_code=201)
def create_share(
    payload: schemas.ShareCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.ShareOut:
    name = payload.bauvorhaben.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Bauvorhaben ist erforderlich")
    if not user_can_share_bauvorhaben(db, user.id, name):
        raise HTTPException(
            status_code=403,
            detail="Sie können dieses Bauvorhaben nicht freigeben "
            "(eigene Rechnungen erforderlich)",
        )
    if payload.user_id == user.id:
        raise HTTPException(
            status_code=400,
            detail="Sie können ein Bauvorhaben nicht mit sich selbst teilen",
        )

    target = db.get(models.User, payload.user_id)
    if target is None or not target.is_active:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")

    existing = db.execute(
        select(models.BauvorhabenShare).where(
            models.BauvorhabenShare.owner_id == user.id,
            models.BauvorhabenShare.bauvorhaben == name,
            models.BauvorhabenShare.shared_with_user_id == payload.user_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _share_out(db, existing)

    # Gegenrichtung schon vorhanden? Dann reicht die bestehende wechselseitige Sicht.
    reverse = db.execute(
        select(models.BauvorhabenShare).where(
            models.BauvorhabenShare.owner_id == payload.user_id,
            models.BauvorhabenShare.bauvorhaben == name,
            models.BauvorhabenShare.shared_with_user_id == user.id,
        )
    ).scalar_one_or_none()
    if reverse is not None:
        return _share_out(db, reverse)

    share = models.BauvorhabenShare(
        bauvorhaben=name,
        owner_id=user.id,
        shared_with_user_id=payload.user_id,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return _share_out(db, share)


@router.delete("/{share_id}", status_code=204)
def delete_share(
    share_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> None:
    share = db.get(models.BauvorhabenShare, share_id)
    if share is None:
        raise HTTPException(status_code=404, detail="Freigabe nicht gefunden")
    # Owner kann zurückziehen, Empfänger kann die Freigabe verlassen.
    if share.owner_id != user.id and share.shared_with_user_id != user.id:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    db.delete(share)
    db.commit()
