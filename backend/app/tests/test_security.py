"""Unit tests for app.core.security — password hashing and JWT tokens."""

from datetime import timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_returns_bcrypt_string(self):
        hashed = hash_password("mysecret")
        assert hashed.startswith("$2b$")
        assert hashed != "mysecret"

    def test_verify_correct_password(self):
        hashed = hash_password("correct-horse")
        assert verify_password("correct-horse", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct-horse")
        assert verify_password("wrong-horse", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt


class TestAccessToken:
    def test_create_and_decode(self):
        token = create_access_token("42")
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_custom_expiry(self):
        token = create_access_token("1", expires_delta=timedelta(hours=2))
        payload = decode_token(token)
        assert payload["sub"] == "1"

    def test_expired_token_raises(self):
        token = create_access_token("1", expires_delta=timedelta(seconds=-1))
        with pytest.raises(Exception):  # jose.ExpiredSignatureError
            decode_token(token)


class TestRefreshToken:
    def test_create_and_decode(self):
        token = create_refresh_token("99")
        payload = decode_token(token)
        assert payload["sub"] == "99"
        assert payload["type"] == "refresh"

    def test_refresh_token_is_different_from_access(self):
        access = create_access_token("1")
        refresh = create_refresh_token("1")
        assert access != refresh

        ap = decode_token(access)
        rp = decode_token(refresh)
        assert ap["type"] == "access"
        assert rp["type"] == "refresh"


class TestDecodeToken:
    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_token("not-a-valid-token")

    def test_wrong_secret_raises(self):
        token = jwt.encode(
            {"sub": "1", "type": "access"},
            "wrong-secret",
            algorithm=settings.ALGORITHM,
        )
        with pytest.raises(Exception):
            decode_token(token)
