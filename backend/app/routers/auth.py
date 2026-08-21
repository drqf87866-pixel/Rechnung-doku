from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.security import (
    create_access_token,
    get_current_user,
    get_db,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _validate_username(username: str) -> str:
    normalized = _normalize_username(username)
    if not _USERNAME_RE.fullmatch(normalized):
        raise HTTPException(
            status_code=400,
            detail="Benutzername darf nur Buchstaben, Zahlen sowie . _ - enthalten",
        )
    return normalized


def count_users(db: Session) -> int:
    return int(db.execute(select(func.count()).select_from(models.User)).scalar_one())


@router.get("/setup-status", response_model=schemas.SetupStatus)
def setup_status(db: Session = Depends(get_db)) -> schemas.SetupStatus:
    return schemas.SetupStatus(needs_setup=count_users(db) == 0)


@router.post("/setup", response_model=schemas.TokenResponse, status_code=201)
def setup_admin(
    payload: schemas.SetupAdmin,
    db: Session = Depends(get_db),
) -> schemas.TokenResponse:
    if count_users(db) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setup bereits abgeschlossen",
        )

    username = _validate_username(payload.username)
    user = models.User(
        username=username,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Erster Admin-Benutzer angelegt: %s", user.username)
    token = create_access_token(user)
    return schemas.TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=schemas.TokenResponse)
def login(
    payload: schemas.LoginRequest,
    db: Session = Depends(get_db),
) -> schemas.TokenResponse:
    username = _normalize_username(payload.username)
    user = db.execute(
        select(models.User).where(models.User.username == username)
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzername oder Passwort ungültig",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Benutzer ist deaktiviert",
        )
    token = create_access_token(user)
    return schemas.TokenResponse(access_token=token, user=user)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)) -> models.User:
    return user
