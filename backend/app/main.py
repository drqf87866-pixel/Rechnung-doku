from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app import storage
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.db_migrate import backfill_invoice_owners, ensure_invoice_columns
from app.models import User
from app.routers import auth, invoices, shares, users
from app.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _bootstrap_admin_if_needed() -> None:
    """Legt optional den ersten Admin aus Env-Variablen an."""
    username = (settings.bootstrap_admin_username or "").strip().lower()
    password = settings.bootstrap_admin_password
    if not username or not password:
        return

    db = SessionLocal()
    try:
        existing = db.execute(select(User).limit(1)).scalar_one_or_none()
        if existing is not None:
            return
        user = User(
            username=username,
            display_name=settings.bootstrap_admin_display_name.strip() or "Administrator",
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        logger.info("Bootstrap-Admin angelegt: %s", username)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_invoice_columns(engine)
    _bootstrap_admin_if_needed()
    db = SessionLocal()
    try:
        backfill_invoice_owners(db)
    finally:
        db.close()
    storage.ensure_bucket()
    if settings.jwt_secret == "dev-only-change-me":
        logger.warning(
            "JWT_SECRET nutzt den Entwicklungs-Default – in Produktion setzen!"
        )
    yield


app = FastAPI(
    title="Doku-Agent Rechnungsplattform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(shares.router)
app.include_router(invoices.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"app": "Doku-Agent Rechnungsplattform", "docs": "/docs"}
