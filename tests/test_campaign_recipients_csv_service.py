import pytest

from src.services.campaign_recipients_csv_service import parse_campaign_recipients_csv


def test_campaign_recipients_csv_keeps_variables_and_dedupes():
    content = (
        "email,name,coupon_code\n"
        "one@example.com,Alice,SAVE20\n"
        "ONE@example.com,Duplicate,DUP\n"
        "two@example.com,Bob,SAVE30\n"
    ).encode()

    parsed = parse_campaign_recipients_csv(content)

    assert parsed["duplicate_count"] == 1
    assert parsed["invalid_emails"] == []
    assert parsed["columns"] == ["email", "name", "coupon_code"]
    assert parsed["recipients"] == [
        {
            "email": "one@example.com",
            "variables": {"name": "Alice", "coupon_code": "SAVE20"},
        },
        {
            "email": "two@example.com",
            "variables": {"name": "Bob", "coupon_code": "SAVE30"},
        },
    ]


def test_campaign_recipients_csv_can_preview_invalid_rows():
    content = "email,name\nvalid@example.com,Alice\nbad-email,Bad\n".encode()

    parsed = parse_campaign_recipients_csv(
        content,
        allow_empty=True,
        reject_invalid=False,
    )

    assert parsed["invalid_emails"] == ["bad-email"]
    assert parsed["recipients"][0]["email"] == "valid@example.com"


def test_campaign_recipients_csv_requires_email_column():
    with pytest.raises(ValueError, match="email column"):
        parse_campaign_recipients_csv("name\nAlice\n".encode())
