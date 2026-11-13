"""Unit tests for auth service."""
from services.auth import get_current_user

def test_legacy_get_current_user():
    # Only tests legacy get_current_user
    assert get_current_user("dummy") is None

