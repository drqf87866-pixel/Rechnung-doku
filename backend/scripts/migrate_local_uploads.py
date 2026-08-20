"""Einmaliges Migrationsskript: kopiert lokale PDFs (./uploads) in den Supabase-Bucket.

Hintergrund: Vor dem Umstieg auf Supabase Storage lagen die PDFs im lokalen
Dateisystem (UPLOAD_DIR, Standard ./uploads). Auf dem Render-Free-Tier ist dieses
Dateisystem ephemer – die Dateien können bei einem Deploy verloren sein. Dieses
Skript lädt alle noch lokal vorhandenen Dateien in den Bucket hoch, damit die
DB-Einträge wieder herunterladbar sind. Der stored_filename bleibt unverändert,
sodass die Verweise in der Datenbank weiter passen.

Voraussetzungen (wie beim Backend):
  - SUPABASE_URL und SUPABASE_SERVICE_KEY sind gesetzt (oder in backend/.env)
  - Der Bucket existiert oder wird vom Skript angelegt (privat)

Ausführung (aus dem Verzeichnis backend/):
  .venv\\Scripts\\python scripts/migrate_local_uploads.py

Optional die lokalen Dateien nach erfolgreichem Upload löschen:
  .venv\\Scripts\\python scripts/migrate_local_uploads.py --delete-local

Das Skript ist idempotent (Upload mit Upsert) – mehrfaches Ausführen ist unkritisch.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

# Ermöglicht `python scripts/migrate_local_uploads.py` aus backend/ heraus.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models, storage  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delete-local",
        action="store_true",
        help="Lokale Dateien nach erfolgreichem Upload entfernen.",
    )
    args = parser.parse_args()

    backend = storage.get_storage()
    if not isinstance(backend, storage.SupabaseStorage):
        print("SUPABASE_URL/SUPABASE_SERVICE_KEY sind nicht gesetzt – kein Supabase-Storage aktiv. Abbruch.")
        return 1

    local_dir = Path(settings.upload_dir)
    if not local_dir.is_dir():
        print(f"Kein lokales Upload-Verzeichnis vorhanden: {local_dir}")
        return 0

    backend.ensure_bucket()
    bucket = backend._get_bucket()

    db = SessionLocal()
    try:
        invoices = db.execute(select(models.Invoice)).scalars().all()
    finally:
        db.close()

    print(f"Prüfe {len(invoices)} Rechnungen gegen {local_dir} …")
    migrated = missing = 0
    for invoice in invoices:
        path = local_dir / invoice.stored_filename
        if not path.is_file():
            print(f"  ÜBERSPRUNGEN (lokal nicht vorhanden): ID {invoice.id} / {invoice.stored_filename}")
            missing += 1
            continue
        bucket.upload(
            invoice.stored_filename,
            path.read_bytes(),
            {"content-type": "application/pdf", "upsert": "true"},
        )
        print(f"  MIGRIERT: ID {invoice.id} / {invoice.stored_filename}")
        migrated += 1
        if args.delete_local:
            path.unlink(missing_ok=True)

    print(f"Fertig: {migrated} migriert, {missing} lokal nicht vorhanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())