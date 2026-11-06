from datetime import datetime, timedelta, timezone
from secrets import randbelow, token_urlsafe
from sqlalchemy import text, func
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from jose import JWTError
from .db import get_db
from .models import User, OtpChallenge, AuditEvent, KycCase, AuthSession, LedgerAccount, LedgerEntry, LedgerTransaction
from .security import hash_password, verify_password, make_access_token, read_access_token, otp_digest, verify_otp
from .config import settings
from .providers import DemoOtpProvider, UnconfiguredKycProvider
from .rate_limit import enforce_rate_limit

app = FastAPI(title="XM TRADING API", version="0.8.0")
otp_provider = DemoOtpProvider()
kyc_provider = UnconfiguredKycProvider()


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.app_env.lower() in {"production", "prod"}:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class VerifyOtpIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


def request_identity(request: Request) -> str:
    # Do not trust X-Forwarded-For unless a trusted proxy is explicitly configured.
    return request.client.host if request.client else "unknown"


def audit(db: Session, actor: str, event: str, detail: str = ""):
    db.add(AuditEvent(actor_email=actor, event=event, detail=detail[:500]))
    db.flush()


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable")
    return {"status": "ok", "database": "ok", "environment": settings.app_env,
            "real_money_enabled": False, "trading_enabled": False}


@app.post("/auth/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit(db, scope="register-ip", identity=request_identity(request), limit=5, window_seconds=3600)
    email = str(body.email).strip().lower()
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        audit(db, email, "register")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Account already exists")
    return {"status": "registered", "next": "request OTP"}


@app.post("/auth/request-otp")
def request_otp(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = str(body.email).strip().lower()
    enforce_rate_limit(db, scope="otp-ip", identity=request_identity(request), limit=10, window_seconds=900)
    enforce_rate_limit(db, scope="otp-email", identity=email, limit=5, window_seconds=900)
    user = db.query(User).filter_by(email=email, is_active=True).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    if settings.app_env.lower() in {"production", "prod"} or not settings.allow_dev_otp:
        raise HTTPException(503, "OTP delivery provider is not configured; local demo requires ALLOW_DEV_OTP=true")
    db.query(OtpChallenge).filter_by(email=email, consumed=False).update({"consumed": True}, synchronize_session=False)
    code = f"{randbelow(1_000_000):06d}"
    challenge = OtpChallenge(email=email, code_hash=otp_digest(code),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.otp_ttl_seconds), attempts=0)
    db.add(challenge)
    audit(db, email, "otp_requested")
    db.commit()
    otp_provider.send_code(email, code)
    return {"status": "otp_requested", "delivery": "development_only", "development_code": code}


@app.post("/auth/verify-otp")
def verify_otp_endpoint(body: VerifyOtpIn, request: Request, db: Session = Depends(get_db)):
    email = str(body.email).strip().lower()
    enforce_rate_limit(db, scope="otp-verify-ip", identity=request_identity(request), limit=20, window_seconds=900)
    enforce_rate_limit(db, scope="otp-verify-email", identity=email, limit=10, window_seconds=900)
    user = db.query(User).filter_by(email=email, is_active=True).first()
    challenge = (db.query(OtpChallenge).filter_by(email=email, consumed=False)
                 .order_by(OtpChallenge.id.desc()).with_for_update().first())
    now = datetime.now(timezone.utc)
    if not user or not challenge:
        raise HTTPException(401, "Invalid or expired OTP")
    expiry = challenge.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= now or challenge.attempts >= settings.otp_max_attempts:
        challenge.consumed = True
        db.commit()
        raise HTTPException(401, "Invalid or expired OTP")
    if not verify_otp(body.code, challenge.code_hash):
        challenge.attempts += 1
        if challenge.attempts >= settings.otp_max_attempts:
            challenge.consumed = True
        db.commit()
        raise HTTPException(401, "Invalid or expired OTP")
    challenge.consumed = True
    audit(db, email, "otp_verified")
    db.commit()
    token_id = token_urlsafe(24)
    db.add(AuthSession(token_id=token_id, user_id=user.id, expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)))
    db.commit()
    token = make_access_token(user.email, user.role, token_id)
    return {"access_token": token, "token_type": "bearer", "expires_in": settings.access_token_minutes * 60}


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required")
    try:
        claims = read_access_token(authorization[7:])
        user = db.query(User).filter_by(email=claims["sub"], is_active=True).first()
        if not user:
            raise HTTPException(401, "Inactive user")
        session = db.get(AuthSession, claims.get("jti"))
        if not session or session.user_id != user.id or session.revoked_at is not None:
            raise HTTPException(401, "Session revoked or unknown")
        expiry = session.expires_at
        if (expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry) <= datetime.now(timezone.utc):
            raise HTTPException(401, "Session expired")
        return user
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid token")


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"email": user.email, "role": user.role}


@app.post("/kyc/start")
def start_kyc(user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = KycCase(user_id=user.id, status="provider_not_configured")
    db.add(case)
    audit(db, user.email, "kyc_start_requested", "No identity documents collected in demo")
    db.commit()
    return {"status": case.status, "message": "Connect an approved KYC provider before collecting documents."}


@app.get("/admin/summary")
def admin_summary(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    return {"users": db.query(User).count(), "kyc_cases": db.query(KycCase).count(),
            "real_money_enabled": False, "trading_enabled": False}


@app.post("/auth/logout")
def logout(authorization: str | None = Header(default=None), user: User = Depends(current_user), db: Session = Depends(get_db)):
    claims = read_access_token(authorization[7:])
    session = db.get(AuthSession, claims["jti"])
    session.revoked_at = datetime.now(timezone.utc)
    audit(db, user.email, "logout")
    db.commit()
    return {"status": "logged_out"}


@app.post("/auth/logout-all")
def logout_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).update({"revoked_at": datetime.now(timezone.utc)}, synchronize_session=False)
    audit(db, user.email, "logout_all")
    db.commit()
    return {"status": "all_sessions_revoked"}


@app.get("/accounts")
def list_accounts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Read-only ledger account view. No fabricated balances."""
    accounts = db.query(LedgerAccount).filter(LedgerAccount.owner_user_id == user.id).order_by(LedgerAccount.id).all()
    result = []
    for account in accounts:
        debit, credit = db.query(func.coalesce(func.sum(LedgerEntry.debit), 0), func.coalesce(func.sum(LedgerEntry.credit), 0)).filter(LedgerEntry.account_id == account.id).one()
        result.append({"id": account.id, "code": account.code, "currency": account.currency,
                       "total_debits": str(debit), "total_credits": str(credit),
                       "net_debit_balance": str(debit - credit), "balance_type": "debit_minus_credit"})
    return {"accounts": result, "sandbox": True, "note": "Ledger amounts are not verified cash or trading equity."}


@app.get("/transactions")
def list_transactions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Read-only transactions linked through accounts owned by the authenticated user."""
    txs = (db.query(LedgerTransaction).join(LedgerEntry, LedgerEntry.transaction_id == LedgerTransaction.id)
           .join(LedgerAccount, LedgerAccount.id == LedgerEntry.account_id)
           .filter(LedgerAccount.owner_user_id == user.id).distinct()
           .order_by(LedgerTransaction.id.desc()).limit(100).all())
    result = []
    for tx in txs:
        entries = (db.query(LedgerEntry, LedgerAccount).join(LedgerAccount, LedgerAccount.id == LedgerEntry.account_id)
                   .filter(LedgerEntry.transaction_id == tx.id, LedgerAccount.owner_user_id == user.id).all())
        result.append({"id": tx.id, "reference": tx.reference, "currency": tx.currency,
                       "created_at": tx.created_at.isoformat() if tx.created_at else None,
                       "entries": [{"account_id": a.id, "debit": str(e.debit), "credit": str(e.credit)} for e, a in entries]})
    return {"transactions": result, "sandbox": True}
