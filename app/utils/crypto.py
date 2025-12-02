"""Encryption utilities for sensitive data like API keys"""
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_logger():
    """Lazy import logger to avoid circular import"""
    from app.logger import logger
    return logger


def _get_encryption_key() -> bytes:
    """Get or generate encryption key for Fernet
    
    Uses a fixed key derived from a secret (for consistency across restarts).
    In production, this should use a proper key management system.
    """
    # Use a fixed secret for key derivation (in production, use environment variable)
    secret = os.getenv("NEOCHAT_ENCRYPTION_SECRET", "neochat-default-secret-key-change-in-production")
    salt = b'neochat_salt_2024'  # Fixed salt for consistency
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return key


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key
    
    Args:
        api_key: Plain text API key
        
    Returns:
        Encrypted API key (base64 encoded)
    """
    if not api_key:
        return ""
    
    try:
        key = _get_encryption_key()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(api_key.encode())
        return encrypted.decode()
    except Exception as e:
        _get_logger().error(f"Failed to encrypt API key: {e}")
        raise


def decrypt_api_key(encrypted_api_key: str) -> str:
    """Decrypt an API key
    
    Args:
        encrypted_api_key: Encrypted API key (base64 encoded)
        
    Returns:
        Plain text API key
    """
    if not encrypted_api_key:
        return ""
    
    try:
        key = _get_encryption_key()
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_api_key.encode())
        return decrypted.decode()
    except Exception as e:
        _get_logger().error(f"Failed to decrypt API key: {e}")
        raise

