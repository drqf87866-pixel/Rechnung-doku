from __future__ import annotations

import io

import fitz
from fastapi import UploadFile

from app import storage
from app.config import settings
from app.services.pdf_extractor import extract_text


def test_local_storage_roundtrip(tmp_path, monkeypatch):
    # Storage-Singleton zuruecksetzen, damit der tmp_path verwendet wird.
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(storage, "_storage", None)

    backend = storage.get_storage()
    assert isinstance(backend, storage.LocalStorage)

    file = UploadFile(
        file=io.BytesIO(b"%PDF-1.4 test content"),
        filename="Rechnung 2024.pdf",
    )
    stored, data = storage.save_upload(file)
    assert stored.endswith(".pdf")
    assert data == b"%PDF-1.4 test content"

    assert storage.read_bytes(stored) == b"%PDF-1.4 test content"
    assert (tmp_path / stored).is_file()

    # get_local_path liefert einen Pfad für vorhandene lokale Dateien.
    local_path = storage.get_local_path(stored)
    assert local_path is not None and local_path.is_file()

    storage.delete_file(stored)
    assert not (tmp_path / stored).exists()

    monkeypatch.setattr(storage, "_storage", None)


def test_extract_text_from_bytes():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Rechnungsnummer: RE-2024-0157")
    data = document.tobytes()
    document.close()

    text = extract_text(data)
    assert "RE-2024-0157" in text


def test_read_error_classification():
    from storage3.exceptions import StorageApiError

    not_found = StorageApiError(message="The resource was not found", code="404", status=404)
    assert isinstance(storage._classify_storage_read_error("x.pdf", not_found), storage.StorageNotFound)

    auth_error = StorageApiError(message="Invalid JWT", code="401", status=401)
    assert isinstance(storage._classify_storage_read_error("x.pdf", auth_error), storage.StorageError)

    network_error = RuntimeError("connection refused")
    assert isinstance(storage._classify_storage_read_error("x.pdf", network_error), storage.StorageError)