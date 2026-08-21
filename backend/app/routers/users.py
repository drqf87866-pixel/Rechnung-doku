from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.security import get_current_user, get_db, hash_password, require_admin

router = APIRouter(prefix="/api/users", tags=["users"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _validate_username(username: str) -> str:
    normalized = _normalize_username(username)
    if len(normalized) < 3:
        raise HTTPException(status_code=400, detail="Benutzername zu kurz")
    if not _USERNAME_RE.fullmatch(normalized):
        raise HTTPException(
            status_code=400,
            detail="Benutzername darf nur Buchstaben, Zahlen sowie . _ - enthalten",
        )
    return normalized


def _get_user_or_404(db: Session, user_id: int) -> models.User:
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    return user


def _count_active_admins(db: Session, exclude_id: int | None = None) -> int:
    stmt = select(models.User).where(
        models.User.role == "admin",
        models.User.is_active.is_(True),
    )
    users = list(db.execute(stmt).scalars().all())
    if exclude_id is not None:
        users = [u for u in users if u.id != exclude_id]
    return len(users)


@router.get("/directory", response_model=list[schemas.UserDirectoryItem])
def list_user_directory(
    db: Session = Depends(get_db),
    current: models.User = Depends(get_current_user),
) -> list[models.User]:
    """Aktive Benutzer für Freigabe-Auswahl (ohne Passwort/Rolle)."""
    stmt = (
        select(models.User)
        .where(
            models.User.is_active.is_(True),
            models.User.id != current.id,
        )
        .order_by(models.User.display_name.asc(), models.User.username.asc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get("", response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
) -> list[models.User]:
    stmt = select(models.User).order_by(models.User.username.asc())
    return list(db.execute(stmt).scalars().all())


@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
) -> models.User:
    username = _validate_username(payload.username)
    existing = db.execute(
        select(models.User).where(models.User.username == username)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Benutzername bereits vergeben")

    user = models.User(
        username=username,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=schemas.UserOut)
def patch_user(
    user_id: int,
    payload: schemas.UserPatch,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
) -> models.User:
    user = _get_user_or_404(db, user_id)
    data = payload.model_dump(exclude_unset=True)

    if "display_name" in data and data["display_name"] is not None:
        user.display_name = data["display_name"].strip()

    if "password" in data and data["password"]:
        user.password_hash = hash_password(data["password"])

    if "role" in data and data["role"] is not None:
        new_role = data["role"]
        if (
            user.role == "admin"
            and new_role != "admin"
            and _count_active_admins(db, exclude_id=user.id) == 0
            and user.is_active
        ):
            raise HTTPException(
                status_code=400,
                detail="Der letzte aktive Administrator kann nicht herabgestuft werden",
            )
        user.role = new_role

    if "is_active" in data and data["is_active"] is not None:
        new_active = data["is_active"]
        if (
            user.role == "admin"
            and user.is_active
            and not new_active
            and _count_active_admins(db, exclude_id=user.id) == 0
        ):
            raise HTTPException(
                status_code=400,
                detail="Der letzte aktive Administrator kann nicht deaktiviert werden",
            )
        if user.id == current_admin.id and not new_active:
            raise HTTPException(
                status_code=400,
                detail="Sie können sich nicht selbst deaktivieren",
            )
        user.is_active = new_active

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(require_admin),
) -> None:
    user = _get_user_or_404(db, user_id)
    if user.id == current_admin.id:
        raise HTTPException(
            status_code=400,
            detail="Sie können sich nicht selbst löschen",
        )
    if (
        user.role == "admin"
        and user.is_active
        and _count_active_admins(db, exclude_id=user.id) == 0
    ):
        raise HTTPException(
            status_code=400,
            detail="Der letzte aktive Administrator kann nicht gelöscht werden",
        )
    db.delete(user)
    db.commit()
