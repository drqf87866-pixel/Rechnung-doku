from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings


def save_upload(file: UploadFile) -> str:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix
    stored_filename = f"{uuid.uuid4().hex}{suffix}"
    destination = upload_dir / stored_filename
    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return stored_filename


def get_path(stored_filename: str) -> Path:
    return Path(settings.upload_dir) / stored_filename


def delete_file(stored_filename: str) -> None:
    try:
        path = get_path(stored_filename)
        if path.exists():
            path.unlink()
    except OSError:
        pass
