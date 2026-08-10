"""Configuration applicative, chargée depuis l'environnement."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")
    openai_text_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_TEXT_MODEL")
    openai_image_model: str = Field(default="gpt-image-2", alias="OPENAI_IMAGE_MODEL")
    # 3:4 vertical, 1200×1600 : le format exact réclamé par le « Lisez-moi » du
    # modèle pour la photo principale.
    openai_image_size: str = Field(default="1200x1600", alias="OPENAI_IMAGE_SIZE")
    openai_image_style: str = Field(default="photo", alias="OPENAI_IMAGE_STYLE")

    profile_batch_size: int = Field(default=10, alias="PROFILE_BATCH_SIZE")
    image_concurrency: int = Field(default=3, alias="IMAGE_CONCURRENCY")
    max_retries: int = Field(default=4, alias="MAX_RETRIES")
    request_timeout: float = Field(default=180.0, alias="REQUEST_TIMEOUT")

    max_upload_bytes: int = Field(default=15 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    uploads_dir: Path = ROOT_DIR / "uploads"
    outputs_dir: Path = ROOT_DIR / "outputs"
    temp_dir: Path = ROOT_DIR / "temp"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def ensure_directories(self) -> None:
        for directory in (self.uploads_dir, self.outputs_dir, self.temp_dir):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
