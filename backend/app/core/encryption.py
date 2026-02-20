from cryptography.fernet import Fernet

from app.core.config import settings

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns a Fernet token as a UTF-8 string."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a Fernet token back to the original string."""
    return _fernet.decrypt(ciphertext.encode()).decode()
