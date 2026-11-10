from pydantic import SecretStr

from fintect.config import Settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "FINTECT API"
    assert settings.app_env == "development"
    assert settings.debug is False
    assert settings.log_level == "INFO"


def test_settings_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "FINTECT Test")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)

    assert settings.app_name == "FINTECT Test"
    assert settings.app_env == "testing"
    assert settings.debug is True
    assert settings.log_level == "DEBUG"


def test_fineract_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.fineract_base_url.startswith("https://localhost:8443")
    assert settings.fineract_username == "mifos"
    assert settings.fineract_password == SecretStr("")
    assert settings.fineract_tenant_id == "default"
    assert settings.fineract_timeout_seconds == 10.0
    assert settings.fineract_verify_tls is True


def test_fineract_settings_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("FINERACT_BASE_URL", "http://example.com/api/v1")
    monkeypatch.setenv("FINERACT_USERNAME", "test-user")
    monkeypatch.setenv("FINERACT_PASSWORD", "test-secret")
    monkeypatch.setenv("FINERACT_TENANT_ID", "test-tenant")
    monkeypatch.setenv("FINERACT_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("FINERACT_VERIFY_TLS", "false")

    settings = Settings(_env_file=None)

    assert settings.fineract_base_url == "http://example.com/api/v1"
    assert settings.fineract_username == "test-user"
    assert settings.fineract_password.get_secret_value() == "test-secret"
    assert settings.fineract_tenant_id == "test-tenant"
    assert settings.fineract_timeout_seconds == 20.0
    assert settings.fineract_verify_tls is False
