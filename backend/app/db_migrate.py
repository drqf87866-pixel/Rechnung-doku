from __future__ import annotations

import logging

from sqlalchemy import inspect, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Spalten, die create_all bei bestehenden Tabellen nicht nachzieht.
_INVOICE_OPTIONAL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("nettobetrag", "NUMERIC(12, 2)"),
    ("steuerbetrag", "NUMERIC(12, 2)"),
    ("owner_id", "INTEGER"),
)


def ensure_invoice_columns(engine: Engine) -> None:
    """Fügt fehlende Invoice-Spalten hinzu (SQLite und Postgres)."""
    inspector = inspect(engine)
    if "invoices" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("invoices")}
    missing = [
        (name, sql_type)
        for name, sql_type in _INVOICE_OPTIONAL_COLUMNS
        if name not in existing
    ]
    if not missing:
        return

    with engine.begin() as connection:
        for name, sql_type in missing:
            logger.info("Füge Spalte invoices.%s hinzu", name)
            connection.execute(
                text(f"ALTER TABLE invoices ADD COLUMN {name} {sql_type}")
            )


def backfill_invoice_owners(db: Session) -> None:
    """Weist Rechnungen ohne owner_id dem ersten Admin (sonst ersten User) zu."""
    from app import models

    orphan_exists = db.execute(
        select(models.Invoice.id)
        .where(models.Invoice.owner_id.is_(None))
        .limit(1)
    ).scalar_one_or_none()
    if orphan_exists is None:
        return

    admin = db.execute(
        select(models.User)
        .where(models.User.role == "admin", models.User.is_active.is_(True))
        .order_by(models.User.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    owner = admin or db.execute(
        select(models.User).order_by(models.User.id.asc()).limit(1)
    ).scalar_one_or_none()
    if owner is None:
        logger.warning(
            "Rechnungen ohne owner_id vorhanden, aber kein Benutzer zum Backfill"
        )
        return

    result = db.execute(
        update(models.Invoice)
        .where(models.Invoice.owner_id.is_(None))
        .values(owner_id=owner.id)
    )
    db.commit()
    logger.info(
        "owner_id-Backfill: %s Rechnung(en) → User %s",
        result.rowcount,
        owner.username,
    )
