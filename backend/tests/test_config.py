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
