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
    # Gemini Flash für Scan-PDFs ohne Textschicht (Hybrid-Extraktion).
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    # JWT-Auth für Benutzerverwaltung (in Produktion zwingend setzen).
    jwt_secret: str = "dev-only-change-me"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 Tage
    # Optionaler Bootstrap des ersten Admins beim Start (nur wenn users leer).
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_display_name: str = "Administrator"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
