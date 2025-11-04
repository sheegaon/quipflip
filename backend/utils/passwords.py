"""Password hashing utilities using bcrypt."""
from __future__ import annotations

import bcrypt
import secrets
import string


class PasswordValidationError(ValueError):
    """Raised when a password fails strength validation."""


def validate_password_strength(password: str) -> None:
    """Validate password complexity requirements.

    The policy requires:
    - Minimum length of 8 characters
    - At least one lowercase letter
    - At least one uppercase letter
    - At least one digit

    Raises:
        PasswordValidationError: If any requirement is not met.
    """

    if len(password) < 8:
        raise PasswordValidationError("Password must be at least 8 characters long.")

    if password.lower() == password or password.upper() == password:
        raise PasswordValidationError(
            "Password must include both uppercase and lowercase letters."
        )

    if not any(char.isdigit() for char in password):
        raise PasswordValidationError("Password must include at least one number.")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        password_bytes = password.encode('utf-8')
        hash_bytes = password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except (ValueError, TypeError, AttributeError):
        return False


def needs_update(password_hash: str) -> bool:
    """Check if a password hash needs to be upgraded to current algorithm.

    With bcrypt, hashes don't typically need updating unless you want to
    increase the cost factor. This function always returns False for now.
    """
    return False


def generate_temporary_password(length: int = 8) -> str:
    """Generate a temporary password for admin password resets.

    Args:
        length: Length of the password (default 8)

    Returns:
        A cryptographically secure random password containing only
        uppercase letters, lowercase letters, and digits (no special characters).
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
