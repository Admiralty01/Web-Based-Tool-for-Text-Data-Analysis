from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against its bcrypt hashed version, with a fallback to hashlib."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Fallback to local sha256 hashing if passlib has conflicts
        if hashed_password.startswith("sha256$"):
            parts = hashed_password.split("$")
            if len(parts) == 3:
                _, salt, h = parts
                calc = hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest()
                return calc == h
        return False


def get_password_hash(password: str) -> str:
    """Generate a bcrypt password hash from a plain text password, with a fallback to hashlib."""
    try:
        return pwd_context.hash(password)
    except Exception:
        # Fallback to local sha256 hashing if passlib has conflicts
        salt = "offline_salt_value"
        h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return f"sha256${salt}${h}"


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create an OAuth2 JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
    return encoded_jwt
