from core.oauth_error_page import oauth_error_page


def test_callback_failure_is_readable_recoverable_and_escapes_remote_text():
    response = oauth_error_page("Sign-in failed", '<script>alert("remote")</script>', 502)
    text = response.body.decode()
    assert response.status_code == 502
    assert '<meta name="viewport"' in text
    assert 'href="/auth"' in text
    assert 'href="/settings"' in text
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
