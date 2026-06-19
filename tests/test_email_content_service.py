from src.services.email_content_service import build_email_message


def test_build_email_message_formats_from_name_and_reply_to():
    msg = build_email_message(
        to="recipient@example.com",
        subject="Hello",
        body="Body",
        from_email="sender@example.com",
        from_name="Sender Name",
        reply_to_email="replies@example.com",
    )

    assert msg["From"] == "Sender Name <sender@example.com>"
    assert msg["Reply-To"] == "replies@example.com"


def test_build_email_message_omits_empty_optional_headers():
    msg = build_email_message(
        to="recipient@example.com",
        subject="Hello",
        body="Body",
        from_email="sender@example.com",
        from_name=" ",
        reply_to_email="",
    )

    assert msg["From"] == "sender@example.com"
    assert msg["Reply-To"] is None
