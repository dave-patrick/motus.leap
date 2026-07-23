"""Test helper functions from conftest."""

from tests.conftest import (
    assert_response_error,
    assert_response_success,
    assert_csp_headers,
    assert_security_headers,
)


def test_assert_response_success(test_client):
    """Test assert_response_success helper."""
    response = test_client.get("/health")
    assert_response_success(response, 200)


def test_assert_security_headers(test_client):
    """Test assert_security_headers helper."""
    response = test_client.get("/dashboard")
    assert_security_headers(response)


def test_assert_csp_headers(test_client):
    """Test assert_csp_headers helper."""
    response = test_client.get("/dashboard")
    assert_csp_headers(response)