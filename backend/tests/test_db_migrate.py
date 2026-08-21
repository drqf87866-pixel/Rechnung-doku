from __future__ import annotations

from sqlalchemy import create_engine, text

from app.db_migrate import ensure_invoice_columns
from app.models import Base


def test_ensure_invoice_columns_adds_missing(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE invoices (
                    id INTEGER PRIMARY KEY,
                    filename VARCHAR NOT NULL,
                    stored_filename VARCHAR NOT NULL UNIQUE,
                    bauvorhaben VARCHAR NOT NULL,
                    rechnungsnummer VARCHAR,
                    rechnungsbetrag NUMERIC(12, 2),
                    waehrung VARCHAR NOT NULL,
                    konfidenz FLOAT,
                    hinweise VARCHAR,
                    upload_time DATETIME NOT NULL
                )
                """
            )
        )

    ensure_invoice_columns(engine)

    with engine.connect() as connection:
        rows = connection.execute(text("PRAGMA table_info(invoices)")).fetchall()
    names = {row[1] for row in rows}
    assert "nettobetrag" in names
    assert "steuerbetrag" in names
    assert "owner_id" in names

    # Idempotent: zweiter Aufruf darf nicht scheitern.
    ensure_invoice_columns(engine)


def test_ensure_invoice_columns_noop_on_fresh_schema(tmp_path):
    db_path = tmp_path / "fresh.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    ensure_invoice_columns(engine)
