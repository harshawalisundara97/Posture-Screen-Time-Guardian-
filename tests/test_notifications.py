from posture_guardian.notifications import _applescript_quote, build_summary_message


def test_build_summary_message_no_previous():
    msg = build_summary_message("2026-07-04", 82.0, None)
    assert "82%" in msg
    assert "vs previous day" not in msg


def test_build_summary_message_improved():
    msg = build_summary_message("2026-07-04", 82.0, 70.0)
    assert "up 12 pts" in msg


def test_build_summary_message_declined():
    msg = build_summary_message("2026-07-04", 60.0, 75.0)
    assert "down 15 pts" in msg


def test_build_summary_message_same():
    msg = build_summary_message("2026-07-04", 70.0, 70.2)
    assert "same as previous day" in msg


def test_applescript_quote_escapes_quotes_and_backslashes():
    quoted = _applescript_quote('say "hi" \\ ok')
    assert quoted == '"say \\"hi\\" \\\\ ok"'
