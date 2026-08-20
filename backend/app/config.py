from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./invoices.db"
    upload_dir: str = "./uploads"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Supabase Storage (optional): Ohne URL/Key wird lokal in upload_dir gespeichert.
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    supabase_storage_bucket: str = "invoices"
    # Max. Seitenkantenlänge (px) fürs OCR-Rendering. Begrenzt die Bitmap-Größe
    # (und damit den Speicher) bei Scanner-PDFs mit übergroßer Seitenbox.
    # 1000 = sicher unter dem Render-Free-Limit (512 MB), 1500+ = bessere
    # Erkennung kleiner Schrift auf größeren Instanzen.
    ocr_max_side: int = 1000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
