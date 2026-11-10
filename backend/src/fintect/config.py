from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    app_name: str = "FINTECT API"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    fineract_base_url: str = "https://localhost:8443/fineract-provider/api/v1"
    fineract_username: str = "mifos"
    fineract_password: SecretStr = SecretStr("")
    fineract_tenant_id: str = "default"
    fineract_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
