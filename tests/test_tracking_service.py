from src.services.tracking_service import append_open_tracking_pixel


def test_open_tracking_pixel_is_inserted_before_body_close():
    html = "<html><body><p>Hello</p></body></html>"

    tracked_html = append_open_tracking_pixel(
        html,
        campaign_id="campaign-1",
        recipient_id="recipient-1",
        user_id="user-1",
        email="person@example.com",
        attempt_id="attempt-1",
    )

    assert "/track/open/" in tracked_html
    assert ".gif" in tracked_html
    assert tracked_html.index("<img ") < tracked_html.index("</body>")


def test_open_tracking_pixel_is_not_display_none():
    tracked_html = append_open_tracking_pixel(
        "<p>Hello</p>",
        campaign_id="campaign-1",
        recipient_id="recipient-1",
        user_id="user-1",
        email="person@example.com",
    )

    assert 'width="1"' in tracked_html
    assert 'height="1"' in tracked_html
    assert "display:none" not in tracked_html
    assert "visibility:hidden" not in tracked_html
