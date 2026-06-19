import smtplib

from src.security.secrets import (
    SmtpCredentials,
    clear_smtp_credentials_cache,
    get_smtp_credentials,
)


def open_smtp_connection(timeout: int = 30) -> tuple[smtplib.SMTP, SmtpCredentials]:
    credentials = get_smtp_credentials()

    try:
        return _open_smtp_connection(credentials, timeout)
    except smtplib.SMTPAuthenticationError:
        clear_smtp_credentials_cache()
        refreshed_credentials = get_smtp_credentials(force_refresh=True)
        return _open_smtp_connection(refreshed_credentials, timeout)


def _open_smtp_connection(
    credentials: SmtpCredentials,
    timeout: int,
) -> tuple[smtplib.SMTP, SmtpCredentials]:
    smtp = smtplib.SMTP(credentials.host, credentials.port, timeout=timeout)

    try:
        if credentials.port == 587:
            smtp.starttls()

        if credentials.username:
            smtp.login(credentials.username, credentials.password)
    except Exception:
        try:
            smtp.quit()
        except Exception:
            smtp.close()
        raise

    return smtp, credentials
