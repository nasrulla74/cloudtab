"""Unit tests for app.core.encryption — Fernet encrypt/decrypt."""

import pytest

from app.core.encryption import decrypt_value, encrypt_value


class TestEncryption:
    def test_encrypt_returns_non_plaintext(self):
        cipher = encrypt_value("my-secret-key")
        assert cipher != "my-secret-key"
        assert len(cipher) > 0

    def test_decrypt_round_trip(self):
        plaintext = "ssh-rsa AAAA... user@host"
        cipher = encrypt_value(plaintext)
        result = decrypt_value(cipher)
        assert result == plaintext

    def test_different_ciphertexts_for_same_input(self):
        """Fernet uses a random IV, so two encryptions of the same input differ."""
        c1 = encrypt_value("same-value")
        c2 = encrypt_value("same-value")
        assert c1 != c2

    def test_decrypt_both_yield_same_plaintext(self):
        c1 = encrypt_value("hello")
        c2 = encrypt_value("hello")
        assert decrypt_value(c1) == decrypt_value(c2) == "hello"

    def test_empty_string(self):
        cipher = encrypt_value("")
        assert decrypt_value(cipher) == ""

    def test_unicode_content(self):
        text = "key with unicode: cafe\u0301 \u2603"
        cipher = encrypt_value(text)
        assert decrypt_value(cipher) == text

    def test_decrypt_invalid_ciphertext_raises(self):
        with pytest.raises(Exception):
            decrypt_value("not-valid-fernet-token")
