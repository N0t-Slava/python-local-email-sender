import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.configs.config import (
    AWS_REGION,
    SECRETS_BACKEND,
    SMTP_SECRET_CACHE_SECONDS,
    SMTP_SECRET_ID,
)


class SecretConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SmtpCredentials:
    host: str
    port: int
    username: str | None
    password: str | None
    from_email: str


_smtp_credentials_cache: SmtpCredentials | None = None
_smtp_credentials_cache_expires_at = 0.0


def clear_smtp_credentials_cache() -> None:
    global _smtp_credentials_cache, _smtp_credentials_cache_expires_at

    _smtp_credentials_cache = None
    _smtp_credentials_cache_expires_at = 0.0


def get_smtp_credentials(force_refresh: bool = False) -> SmtpCredentials:
    global _smtp_credentials_cache, _smtp_credentials_cache_expires_at

    now = time.time()
    if (
        not force_refresh
        and _smtp_credentials_cache is not None
        and now < _smtp_credentials_cache_expires_at
    ):
        return _smtp_credentials_cache

    if SECRETS_BACKEND == "aws":
        credentials = _load_smtp_credentials_from_aws()
    elif SECRETS_BACKEND == "env":
        credentials = _load_smtp_credentials_from_env()
    else:
        raise SecretConfigurationError(
            "SECRETS_BACKEND must be either 'env' or 'aws'"
        )

    _smtp_credentials_cache = credentials
    _smtp_credentials_cache_expires_at = now + max(SMTP_SECRET_CACHE_SECONDS, 0)
    return credentials


def _load_smtp_credentials_from_env() -> SmtpCredentials:
    return _build_smtp_credentials(
        {
            "host": os.getenv("SMTP_HOST", "localhost"),
            "port": os.getenv("SMTP_PORT", "1025"),
            "username": os.getenv("SMTP_USER") or None,
            "password": os.getenv("SMTP_PASS") or None,
            "from_email": os.getenv("FROM_EMAIL", "test@example.com"),
        },
        source="environment",
    )


def _load_smtp_credentials_from_aws() -> SmtpCredentials:
    if not SMTP_SECRET_ID:
        raise SecretConfigurationError(
            "SMTP_SECRET_ID is required when SECRETS_BACKEND=aws"
        )

    client = boto3.client("secretsmanager", region_name=AWS_REGION)

    try:
        response = client.get_secret_value(SecretId=SMTP_SECRET_ID)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "unknown")
        raise SecretConfigurationError(
            f"Could not load SMTP secret '{SMTP_SECRET_ID}' from AWS Secrets Manager: {error_code}"
        ) from exc

    secret_payload = response.get("SecretString")
    if secret_payload is None and response.get("SecretBinary") is not None:
        secret_payload = base64.b64decode(response["SecretBinary"]).decode("utf-8")

    if not secret_payload:
        raise SecretConfigurationError(
            f"SMTP secret '{SMTP_SECRET_ID}' is empty"
        )

    try:
        secret_data = json.loads(secret_payload)
    except json.JSONDecodeError as exc:
        raise SecretConfigurationError(
            f"SMTP secret '{SMTP_SECRET_ID}' must contain JSON"
        ) from exc

    if not isinstance(secret_data, dict):
        raise SecretConfigurationError(
            f"SMTP secret '{SMTP_SECRET_ID}' must contain a JSON object"
        )

    return _build_smtp_credentials(secret_data, source=f"secret '{SMTP_SECRET_ID}'")


def _build_smtp_credentials(data: dict[str, Any], source: str) -> SmtpCredentials:
    host = _required_text(data, ("host", "SMTP_HOST"), source)
    from_email = _required_text(data, ("from_email", "FROM_EMAIL"), source)
    username = _optional_text(data, ("username", "SMTP_USER", "SMTP_USERNAME"))
    password = _optional_text(data, ("password", "SMTP_PASS", "SMTP_PASSWORD"))
    port = _required_port(data, source)

    if username and not password:
        raise SecretConfigurationError(
            f"SMTP password is required when username is set in {source}"
        )

    return SmtpCredentials(
        host=host,
        port=port,
        username=username,
        password=password,
        from_email=from_email,
    )


def _find_value(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _format_keys(keys: tuple[str, ...]) -> str:
    return "' or '".join(keys)


def _required_text(data: dict[str, Any], keys: tuple[str, ...], source: str) -> str:
    value = _find_value(data, keys)
    if value is None or str(value).strip() == "":
        raise SecretConfigurationError(
            f"SMTP field '{_format_keys(keys)}' is required in {source}"
        )
    return str(value).strip()


def _optional_text(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    value = _find_value(data, keys)
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


def _required_port(data: dict[str, Any], source: str) -> int:
    port_keys = ("port", "SMTP_PORT")
    raw_port = _find_value(data, port_keys)
    if raw_port is None or str(raw_port).strip() == "":
        raise SecretConfigurationError(
            f"SMTP field '{_format_keys(port_keys)}' is required in {source}"
        )

    try:
        port = int(raw_port)
    except (TypeError, ValueError) as exc:
        raise SecretConfigurationError(
            f"SMTP field 'port' must be an integer in {source}"
        ) from exc

    if port < 1 or port > 65535:
        raise SecretConfigurationError(
            f"SMTP field 'port' must be between 1 and 65535 in {source}"
        )

    return port
