import importlib
import smtplib

import pytest


def _reload_config_and_secrets():
    import src.configs.config as config
    import src.security.secrets as secrets

    config = importlib.reload(config)
    secrets = importlib.reload(secrets)
    return config, secrets


def test_env_smtp_credentials_are_loaded(monkeypatch):
    monkeypatch.setenv("SECRETS_BACKEND", "env")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "smtp-user")
    monkeypatch.setenv("SMTP_PASS", "smtp-pass")
    monkeypatch.setenv("FROM_EMAIL", "sender@example.com")

    _, secrets = _reload_config_and_secrets()

    credentials = secrets.get_smtp_credentials(force_refresh=True)

    assert credentials.host == "smtp.example.com"
    assert credentials.port == 587
    assert credentials.username == "smtp-user"
    assert credentials.password == "smtp-pass"
    assert credentials.from_email == "sender@example.com"


def test_env_smtp_credentials_reject_username_without_password(monkeypatch):
    monkeypatch.setenv("SECRETS_BACKEND", "env")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "smtp-user")
    monkeypatch.delenv("SMTP_PASS", raising=False)
    monkeypatch.setenv("FROM_EMAIL", "sender@example.com")

    _, secrets = _reload_config_and_secrets()

    with pytest.raises(secrets.SecretConfigurationError, match="SMTP password is required"):
        secrets.get_smtp_credentials(force_refresh=True)


def test_aws_smtp_secret_json_is_loaded(monkeypatch):
    monkeypatch.setenv("SECRETS_BACKEND", "aws")
    monkeypatch.setenv("SMTP_SECRET_ID", "email-service/test/smtp")
    monkeypatch.setenv("AWS_REGION", "eu-central-1")

    _, secrets = _reload_config_and_secrets()

    class FakeSecretsManagerClient:
        def get_secret_value(self, SecretId):
            assert SecretId == "email-service/test/smtp"
            return {
                "SecretString": (
                    '{"host":"smtp.example.com","port":587,'
                    '"username":"smtp-user","password":"smtp-pass",'
                    '"from_email":"sender@example.com"}'
                )
            }

    monkeypatch.setattr(
        secrets.boto3,
        "client",
        lambda service_name, region_name: FakeSecretsManagerClient(),
    )

    credentials = secrets.get_smtp_credentials(force_refresh=True)

    assert credentials.host == "smtp.example.com"
    assert credentials.port == 587
    assert credentials.username == "smtp-user"
    assert credentials.password == "smtp-pass"
    assert credentials.from_email == "sender@example.com"


def test_aws_smtp_secret_accepts_env_style_keys(monkeypatch):
    monkeypatch.setenv("SECRETS_BACKEND", "aws")
    monkeypatch.setenv("SMTP_SECRET_ID", "email-service/test/smtp")
    monkeypatch.setenv("AWS_REGION", "eu-central-1")

    _, secrets = _reload_config_and_secrets()

    class FakeSecretsManagerClient:
        def get_secret_value(self, SecretId):
            assert SecretId == "email-service/test/smtp"
            return {
                "SecretString": (
                    '{"SMTP_HOST":"email-smtp.eu-central-1.amazonaws.com","SMTP_PORT":"587",'
                    '"SMTP_USER":"smtp-user","SMTP_PASS":"smtp-pass",'
                    '"FROM_EMAIL":"sender@example.com"}'
                )
            }

    monkeypatch.setattr(
        secrets.boto3,
        "client",
        lambda service_name, region_name: FakeSecretsManagerClient(),
    )

    credentials = secrets.get_smtp_credentials(force_refresh=True)

    assert credentials.host == "email-smtp.eu-central-1.amazonaws.com"
    assert credentials.port == 587
    assert credentials.username == "smtp-user"
    assert credentials.password == "smtp-pass"
    assert credentials.from_email == "sender@example.com"


def test_production_requires_unsubscribe_or_jwt_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("UNSUBSCRIBE_SECRET", "")
    monkeypatch.setenv("JWT_SECRET", "")

    import src.configs.config as config

    with pytest.raises(RuntimeError, match="UNSUBSCRIBE_SECRET or JWT_SECRET is required"):
        importlib.reload(config)


def test_database_url_placeholder_credentials_are_rejected(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://USER:PASSWORD@localhost:5432/email_service",
    )

    import src.configs.config as config

    with pytest.raises(RuntimeError, match="DATABASE_URL still contains placeholder credentials"):
        importlib.reload(config)


def test_smtp_connection_refreshes_credentials_after_auth_failure(monkeypatch):
    import src.services.smtp_connection_service as smtp_connection_service
    from src.security.secrets import SmtpCredentials

    credentials = [
        SmtpCredentials(
            host="smtp.example.com",
            port=587,
            username="old-user",
            password="old-pass",
            from_email="sender@example.com",
        ),
        SmtpCredentials(
            host="smtp.example.com",
            port=587,
            username="new-user",
            password="new-pass",
            from_email="sender@example.com",
        ),
    ]
    requested_force_refresh_values = []
    cache_clear_count = 0

    def fake_get_smtp_credentials(force_refresh=False):
        requested_force_refresh_values.append(force_refresh)
        return credentials[1] if force_refresh else credentials[0]

    def fake_clear_smtp_credentials_cache():
        nonlocal cache_clear_count
        cache_clear_count += 1

    class FakeSMTP:
        login_attempts = 0

        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.closed = False

        def starttls(self):
            return None

        def login(self, username, password):
            FakeSMTP.login_attempts += 1
            if FakeSMTP.login_attempts == 1:
                raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

        def quit(self):
            self.closed = True

        def close(self):
            self.closed = True

    monkeypatch.setattr(
        smtp_connection_service,
        "get_smtp_credentials",
        fake_get_smtp_credentials,
    )
    monkeypatch.setattr(
        smtp_connection_service,
        "clear_smtp_credentials_cache",
        fake_clear_smtp_credentials_cache,
    )
    monkeypatch.setattr(smtp_connection_service.smtplib, "SMTP", FakeSMTP)

    smtp, credentials_used = smtp_connection_service.open_smtp_connection(timeout=10)

    assert credentials_used.username == "new-user"
    assert smtp.host == "smtp.example.com"
    assert FakeSMTP.login_attempts == 2
    assert cache_clear_count == 1
    assert requested_force_refresh_values == [False, True]
