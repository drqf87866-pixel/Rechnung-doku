from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Allgemeiner Speicherfehler (z. B. Supabase nicht erreichbar)."""


class StorageNotFound(StorageError):
    """Die gespeicherte Datei existiert nicht (mehr)."""


def _classify_storage_read_error(stored_filename: str, exc: Exception) -> StorageError:
    """Ordnet einen Fehler beim Storage-Download korrekt zu.

    Nur ein fehlendes Objekt (Supabase-HTTP 400/404) ist ein StorageNotFound.
    Netzwerk-, Auth- oder 5xx-Fehler bleiben ein StorageError, damit z. B. der
    Download-Endpoint diese nicht faelschlich als 404 meldet.
    """
    status = getattr(exc, "status", None)
    try:
        status = int(status) if status is not None else None
    except (TypeError, ValueError):
        status = None
    if status in (400, 404) or "not found" in str(exc).lower():
        return StorageNotFound(stored_filename)
    return StorageError(f"Download aus dem Speicher fehlgeschlagen: {exc}")


class StorageBackend:
    """Basis-Interface für die PDF-Ablage (lokal oder Supabase Storage)."""

    def save_upload(self, file: UploadFile) -> tuple[str, bytes]:
        """Speichert die Datei und liefert (stored_filename, datei_bytes)."""
        raise NotImplementedError

    def read_bytes(self, stored_filename: str) -> bytes:
        raise NotImplementedError

    def delete_file(self, stored_filename: str) -> None:
        raise NotImplementedError

    def ensure_bucket(self) -> None:
        """Stellt sicher, dass der Ziel-Speicherort existiert (lokal: no-op)."""

    def get_local_path(self, stored_filename: str) -> Path | None:
        """Liefert einen lokalen Dateipfad, wenn das Backend lokal speichert, sonst None."""
        return None


class LocalStorage(StorageBackend):
    """Dateiablage im lokalen Dateisystem (Standard, kein Supabase)."""

    def __init__(self) -> None:
        self.upload_dir = Path(settings.upload_dir)

    def _path(self, stored_filename: str) -> Path:
        return self.upload_dir / stored_filename

    def save_upload(self, file: UploadFile) -> tuple[str, bytes]:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(file.filename or "").suffix
        stored_filename = f"{uuid.uuid4().hex}{suffix}"
        data = file.file.read()
        with self._path(stored_filename).open("wb") as buffer:
            buffer.write(data)
        return stored_filename, data

    def read_bytes(self, stored_filename: str) -> bytes:
        path = self._path(stored_filename)
        if not path.is_file():
            raise StorageNotFound(stored_filename)
        return path.read_bytes()

    def delete_file(self, stored_filename: str) -> None:
        try:
            path = self._path(stored_filename)
            if path.exists():
                path.unlink()
        except OSError as exc:
            logger.warning("Lokale PDF-Löschung fehlgeschlagen (%s): %s", stored_filename, exc)

    def ensure_bucket(self) -> None:
        # Lokaler Speicher: das Verzeichnis wird beim ersten Speichern angelegt.
        return None

    def get_local_path(self, stored_filename: str) -> Path | None:
        path = self._path(stored_filename)
        return path if path.is_file() else None


class SupabaseStorage(StorageBackend):
    """PDF-Ablage in Supabase Storage (privater Bucket, Service-Role-Key)."""

    def __init__(self) -> None:
        if not settings.supabase_url or not settings.supabase_service_key:
            raise StorageError(
                "SUPABASE_URL und SUPABASE_SERVICE_KEY sind für Supabase Storage erforderlich."
            )
        self.bucket_name = settings.supabase_storage_bucket
        self._client = None

    def _get_client(self):
        if self._client is None:
            from supabase import create_client

            self._client = create_client(
                settings.supabase_url, settings.supabase_service_key
            )
        return self._client

    def _get_bucket(self):
        return self._get_client().storage.from_(self.bucket_name)

    def ensure_bucket(self) -> None:
        client = self._get_client()
        try:
            buckets = client.storage.list_buckets()
        except Exception as exc:
            raise StorageError(
                f"Supabase Storage nicht erreichbar (URL/Service-Key prüfen): {exc}"
            ) from exc

        bucket = next((b for b in buckets if b.name == self.bucket_name), None)
        if bucket is None:
            try:
                client.storage.create_bucket(self.bucket_name, {"public": False})
            except Exception as exc:
                raise StorageError(
                    f"Bucket '{self.bucket_name}' konnte nicht angelegt werden: {exc}"
                ) from exc
            logger.info("Supabase-Storage-Bucket '%s' angelegt (privat).", self.bucket_name)
        elif bucket.public:
            # Private-by-default durchsetzen: Ein öffentlicher Bucket würde alle
            # Rechnungs-PDFs ohne Zugriffskontrolle über die Public-URL exponiert.
            try:
                client.storage.update_bucket(self.bucket_name, {"public": False})
            except Exception as exc:
                raise StorageError(
                    f"Bucket '{self.bucket_name}' ist öffentlich und konnte nicht "
                    f"auf privat gesetzt werden: {exc}"
                ) from exc
            logger.warning(
                "Bucket '%s' war öffentlich – wurde auf privat gesetzt.", self.bucket_name
            )

    def save_upload(self, file: UploadFile) -> tuple[str, bytes]:
        suffix = Path(file.filename or "").suffix
        stored_filename = f"{uuid.uuid4().hex}{suffix}"
        data = file.file.read()
        try:
            self._get_bucket().upload(
                stored_filename,
                data,
                {"content-type": file.content_type or "application/pdf"},
            )
        except Exception as exc:
            raise StorageError(f"Upload nach Supabase Storage fehlgeschlagen: {exc}") from exc
        return stored_filename, data

    def read_bytes(self, stored_filename: str) -> bytes:
        try:
            return self._get_bucket().download(stored_filename)
        except Exception as exc:
            raise _classify_storage_read_error(stored_filename, exc) from exc

    def delete_file(self, stored_filename: str) -> None:
        try:
            self._get_bucket().remove([stored_filename])
        except Exception as exc:
            logger.error("PDF-Löschung aus Supabase Storage fehlgeschlagen (%s): %s", stored_filename, exc)


# ---------------------------------------------------------------------------
# Backend-Auswahl und Fassade (gleiche Funktionssignaturen wie vorher)
# ---------------------------------------------------------------------------

_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Liefert das aktive Storage-Backend (Supabase, falls konfiguriert, sonst lokal)."""
    global _storage
    if _storage is None:
        if settings.supabase_url and settings.supabase_service_key:
            _storage = SupabaseStorage()
        else:
            _storage = LocalStorage()
    return _storage


def save_upload(file: UploadFile) -> tuple[str, bytes]:
    return get_storage().save_upload(file)


def read_bytes(stored_filename: str) -> bytes:
    return get_storage().read_bytes(stored_filename)


def delete_file(stored_filename: str) -> None:
    get_storage().delete_file(stored_filename)


def ensure_bucket() -> None:
    get_storage().ensure_bucket()


def get_local_path(stored_filename: str) -> Path | None:
    return get_storage().get_local_path(stored_filename)