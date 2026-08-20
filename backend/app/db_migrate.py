from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Spalten, die create_all bei bestehenden Tabellen nicht nachzieht.
_INVOICE_OPTIONAL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("nettobetrag", "NUMERIC(12, 2)"),
    ("steuerbetrag", "NUMERIC(12, 2)"),
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
