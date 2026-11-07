import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import time
from contextlib import closing, contextmanager
from email.message import EmailMessage
from http.cookies import SimpleCookie
from pathlib import Path

if __package__:
    from .market import CoinbaseTicker, QuoteUnavailable
else:
    from market import CoinbaseTicker, QuoteUnavailable

PAGE = Path(__file__).with_name("index.html").read_bytes()
EMAIL = re.compile(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+")
OTP_LIFETIME = 300
SESSION_LIFETIME = 86400


def send_code(address, code):
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = address
    message["Subject"] = "Trade Studio | رمز الدخول"
    message.set_content(f"رمز الدخول: {code}\nالرمز صالح لمدة خمس دقائق.")
    with smtplib.SMTP_SSL(
        os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "465")),
        timeout=10, context=ssl.create_default_context(),
    ) as smtp:
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)


def create_app(db_path, otp_secret, deliver=send_code, quote=None):
    if len(otp_secret) < 32:
        raise ValueError("OTP_SECRET must contain at least 32 bytes")

    quote = CoinbaseTicker() if quote is None else quote
    admins = {item.strip().lower() for item in os.getenv("ADMIN_EMAILS", "").split(",") if item.strip()}
    trusted_proxies = {
        ipaddress.ip_address(value.strip())
        for value in os.getenv("TRUSTED_PROXY_IPS", "").split(",")
        if value.strip()
    }

    def request_source(env):
        try:
            peer = ipaddress.ip_address(env.get("REMOTE_ADDR", ""))
            if peer in trusted_proxies:
                # The trusted edge must append the address it actually observed.
                peer = ipaddress.ip_address(env.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip())
            if isinstance(peer, ipaddress.IPv6Address):
                if peer.ipv4_mapped:
                    return str(peer.ipv4_mapped)
                return str(ipaddress.ip_network((peer, 64), strict=False))
            return str(peer)
        except ValueError:
            return "unknown"

    @contextmanager
    def transaction():
        with closing(sqlite3.connect(db_path, timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    with transaction() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS challenges (
                email TEXT PRIMARY KEY, id TEXT NOT NULL, digest TEXT NOT NULL,
                created INTEGER NOT NULL, attempts INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY, created INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, email TEXT NOT NULL, expires INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_email ON sessions(email);
            CREATE TABLE IF NOT EXISTS send_events (email TEXT NOT NULL, created INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS send_events_created ON send_events(created);
            CREATE TABLE IF NOT EXISTS otp_sources (source TEXT NOT NULL, created INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS otp_sources_created ON otp_sources(created);
            CREATE INDEX IF NOT EXISTS otp_sources_source ON otp_sources(source, created);
        """)

    def digest(email, challenge, code):
        return hmac.new(otp_secret, f"{email}:{challenge}:{code}".encode(), hashlib.sha256).hexdigest()

    def request_code(email, source, now):
        challenge = secrets.token_urlsafe(24)
        code = f"{secrets.randbelow(1_000_000):06d}"
        with transaction() as db:
            db.execute("DELETE FROM send_events WHERE created <= ?", (now - 3600,))
            db.execute("DELETE FROM challenges WHERE created <= ?", (now - OTP_LIFETIME,))
            last_sent, recent = db.execute(
                "SELECT MAX(created), COUNT(*) FROM send_events WHERE email = ?", (email,)
            ).fetchone()
            db.execute("DELETE FROM otp_sources WHERE created <= ?", (now - 3600,))
            source_count = db.execute("SELECT COUNT(*) FROM otp_sources WHERE source = ?", (source,)).fetchone()[0]
            count = db.execute("SELECT COUNT(*) FROM send_events").fetchone()[0]
            if (last_sent is not None and now - last_sent < 60) or recent >= 5 or source_count >= 10 or count >= 60:
                return "429 Too Many Requests", {"error": "انتظر قليلًا قبل طلب رمز آخر"}, []
            db.execute("INSERT INTO send_events VALUES (?, ?)", (email, now))
            db.execute("INSERT INTO otp_sources VALUES (?, ?)", (source, now))
            db.execute("INSERT OR REPLACE INTO challenges VALUES (?, ?, ?, ?, 0)",
                       (email, challenge, digest(email, challenge, code), now))
        try:
            deliver(email, code)
        except (OSError, smtplib.SMTPException, KeyError, ValueError):
            return "503 Service Unavailable", {"error": "خدمة البريد غير متاحة حاليًا"}, []
        return "200 OK", {"status": "sent"}, []

    def verify(email, code, now):
        with transaction() as db:
            row = db.execute("SELECT id, digest, created, attempts FROM challenges WHERE email = ?",
                             (email,)).fetchone()
            if not row or now - row[2] >= OTP_LIFETIME or row[3] >= 5:
                return "401 Unauthorized", {"error": "الرمز منتهي أو غير صالح"}, []
            if not hmac.compare_digest(row[1], digest(email, row[0], code)):
                db.execute("UPDATE challenges SET attempts = attempts + 1 WHERE email = ?", (email,))
                return "401 Unauthorized", {"error": "الرمز غير صحيح"}, []
            db.execute("DELETE FROM challenges WHERE email = ?", (email,))
            db.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", (email, now))
            db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (hash_token(token), email, now + SESSION_LIFETIME))
        return "200 OK", {"email": email}, [session_cookie(token, SESSION_LIFETIME)]

    def hash_token(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def session_cookie(token, age):
        return "Set-Cookie", f"__Host-session={token}; Max-Age={age}; Path=/; Secure; HttpOnly; SameSite=Strict"

    def route(env):
        method, path = env["REQUEST_METHOD"], env["PATH_INFO"]
        now = int(time.time())
        if method == "GET" and path == "/health":
            return "200 OK", {"status": "ok"}, []
        if method == "GET" and path == "/api/markets/btc-usd":
            try:
                return "200 OK", quote(), []
            except QuoteUnavailable:
                return "503 Service Unavailable", {"error": "سعر السوق غير متاح حاليًا"}, []
        if method == "GET" and path == "/":
            return "200 OK", PAGE, []
        if method == "POST" and path in {"/api/code", "/api/verify", "/api/logout", "/api/logout-all"}:
            if env.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
                return "415 Unsupported Media Type", {"error": "نوع الطلب غير مدعوم"}, []
            size = int(env.get("CONTENT_LENGTH") or 0)
            if not 0 < size <= 2048:
                raise ValueError
            body = json.loads(env["wsgi.input"].read(size))
            if not isinstance(body, dict):
                raise ValueError
            if path in {"/api/code", "/api/verify"}:
                email = body.get("email", "")
                if not isinstance(email, str):
                    raise ValueError
                email = email.strip().lower()
                if len(email) > 254 or not EMAIL.fullmatch(email):
                    return "400 Bad Request", {"error": "أدخل بريدًا صالحًا"}, []
                if path == "/api/code":
                    return request_code(email, request_source(env), now)
                code = body.get("code", "")
                if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
                    raise ValueError
                return verify(email, code, now)
        elif method != "GET" or path not in {"/api/me", "/api/admin/summary"}:
            return "404 Not Found", {"error": "المسار غير موجود"}, []

        cookie = SimpleCookie(env.get("HTTP_COOKIE", ""))
        session = cookie.get("__Host-session")
        token_hash = hash_token(session.value) if session else ""
        with transaction() as db:
            if path == "/api/logout":
                db.execute("DELETE FROM sessions WHERE token = ?", (token_hash,))
                return "200 OK", {"status": "ok"}, [session_cookie("", 0)]
            row = db.execute("SELECT email FROM sessions WHERE token = ? AND expires > ?",
                             (token_hash, now)).fetchone()
            if row and path == "/api/admin/summary":
                if row[0] not in admins:
                    return "403 Forbidden", {"error": "الوصول مقصور على الإدارة"}, []
                users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                sessions = db.execute("SELECT COUNT(*) FROM sessions WHERE expires > ?", (now,)).fetchone()[0]
                return "200 OK", {"users": users, "active_sessions": sessions}, []
            if row and path == "/api/logout-all":
                db.execute("DELETE FROM sessions WHERE email = ?", (row[0],))
                db.execute("DELETE FROM challenges WHERE email = ?", (row[0],))
                return "200 OK", {"status": "ok"}, [session_cookie("", 0)]
        if row:
            return "200 OK", {"email": row[0]}, []
        return "401 Unauthorized", {"error": "سجّل الدخول أولًا"}, []

    def app(env, start_response):
        try:
            status, data, headers = route(env)
        except (ValueError, TypeError, UnicodeError):
            status, data, headers = "400 Bad Request", {"error": "الطلب غير صالح"}, []
        is_page = isinstance(data, bytes)
        payload = data if is_page else json.dumps(data, ensure_ascii=False).encode()
        start_response(status, headers + [
            ("Content-Type", ("text/html" if is_page else "application/json") + "; charset=utf-8"),
            ("Content-Length", str(len(payload))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
        ])
        return [payload]

    return app
