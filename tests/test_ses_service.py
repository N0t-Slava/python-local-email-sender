from src.integrations import ses_service


def test_sender_is_verified_when_exact_email_identity_is_verified(monkeypatch):
    monkeypatch.setattr(ses_service, "is_from_email_verified", lambda from_email: True)

    assert ses_service.is_sender_verified("hello@example.com") is True


def test_sender_is_verified_when_domain_identity_is_verified(monkeypatch):
    monkeypatch.setattr(ses_service, "is_from_email_verified", lambda from_email: False)
    monkeypatch.setattr(
        ses_service,
        "get_ses_domain_identity",
        lambda domain: {"VerifiedForSendingStatus": domain == "example.com"},
    )

    assert ses_service.is_sender_verified("hello@example.com") is True


def test_sender_is_not_verified_without_email_or_domain_identity(monkeypatch):
    monkeypatch.setattr(ses_service, "is_from_email_verified", lambda from_email: False)
    monkeypatch.setattr(ses_service, "get_ses_domain_identity", lambda domain: None)

    assert ses_service.is_sender_verified("hello@example.com") is False


def test_sender_is_not_verified_for_invalid_email(monkeypatch):
    monkeypatch.setattr(ses_service, "is_from_email_verified", lambda from_email: False)

    assert ses_service.is_sender_verified("not-an-email") is False
