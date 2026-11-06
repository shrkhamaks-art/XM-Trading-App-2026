from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import new as hmac_new, compare_digest
from secrets import token_urlsafe
from jose import jwt
from passlib.context import CryptContext
from .config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except (ValueError, TypeError):
        return False

def otp_digest(code: str) -> str:
    key = (settings.otp_pepper or settings.jwt_secret).encode()
    return hmac_new(key, code.encode(), sha256).hexdigest()

def verify_otp(code: str, digest: str) -> bool:
    return compare_digest(otp_digest(code), digest)

def make_access_token(subject: str, role: str, token_id: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": subject, "role": role, "iat": now, "jti": token_id or token_urlsafe(16), "exp": expiry}, settings.jwt_secret, algorithm=ALGORITHM)

def read_access_token(token: str) -> dict:
    if len(settings.jwt_secret.encode()) < 32 and settings.app_env.lower() in {"production", "prod"}:
        raise ValueError("Production JWT secret is not configured")
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require_sub": True, "require_exp": True})
