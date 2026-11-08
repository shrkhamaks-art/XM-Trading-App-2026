"""Phone verification state for the current, authenticated customer profile."""

import hashlib
import hmac
import json
import re
import secrets

PHONE_PATHS = {"/api/phone/code", "/api/phone/verify"}
LIFETIME = 300

SCHEMA = """
CREATE TABLE IF NOT EXISTS verified_phones (
    email TEXT PRIMARY KEY REFERENCES customer_profiles(email),
    phone TEXT NOT NULL, verified_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS phone_challenges (
    email TEXT PRIMARY KEY REFERENCES customer_profiles(email),
    id TEXT NOT NULL, phone TEXT NOT NULL, digest TEXT NOT NULL,
    created INTEGER NOT NULL, attempts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS phone_send_events (
    email TEXT NOT NULL, phone TEXT NOT NULL, source TEXT NOT NULL, created INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS phone_events_created ON phone_send_events(created);
"""


class PhoneVerification:
    def __init__(self, transaction, secret, deliver):
        self.transaction = transaction
        self.secret = secret
        self.deliver = deliver

    def _digest(self, email, phone, challenge, code):
        payload = json.dumps(["phone-v1", email, phone, challenge, code]).encode()
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def issue(self, db, email, source, now):
        if self.deliver is None:
            return "503 Service Unavailable", {"error": "مزوّد رسائل الجوال غير مهيأ"}, None
        profile = db.execute("SELECT phone FROM customer_profiles WHERE email = ?", (email,)).fetchone()
        if not profile:
            return "409 Conflict", {"error": "احفظ ملف العميل أولًا"}, None
        phone = profile[0]
        if db.execute("SELECT 1 FROM verified_phones WHERE email = ? AND phone = ?", (email, phone)).fetchone():
            return "200 OK", {"status": "already_verified"}, None
        db.execute("DELETE FROM phone_send_events WHERE created <= ?", (now - 3600,))
        db.execute("DELETE FROM phone_challenges WHERE created <= ?", (now - LIFETIME,))
        last, account_count, phone_count, source_count, total = db.execute("""
            SELECT MAX(CASE WHEN email = ? THEN created END),
                   SUM(CASE WHEN email = ? THEN 1 ELSE 0 END),
                   SUM(CASE WHEN phone = ? THEN 1 ELSE 0 END),
                   SUM(CASE WHEN source = ? THEN 1 ELSE 0 END), COUNT(*)
            FROM phone_send_events
        """, (email, email, phone, source)).fetchone()
        if ((last is not None and now - last < 60) or (account_count or 0) >= 5
                or (phone_count or 0) >= 5 or (source_count or 0) >= 10 or total >= 60):
            return "429 Too Many Requests", {"error": "انتظر قبل طلب رمز جديد"}, None
        challenge, code = secrets.token_urlsafe(24), f"{secrets.randbelow(1_000_000):06d}"
        db.execute("INSERT INTO phone_send_events VALUES (?, ?, ?, ?)", (email, phone, source, now))
        db.execute("INSERT OR REPLACE INTO phone_challenges VALUES (?, ?, ?, ?, ?, 0)",
                   (email, challenge, phone, self._digest(email, phone, challenge, code), now))
        return "200 OK", {"status": "sent"}, (email, challenge, phone, code)

    def send(self, pending):
        email, challenge, phone, code = pending
        try:
            self.deliver(phone, code)
        except (OSError, ValueError):
            with self.transaction() as db:
                db.execute("DELETE FROM phone_challenges WHERE email = ? AND id = ?", (email, challenge))
            return False
        return True

    def verify(self, db, email, code, now):
        if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
            return "400 Bad Request", {"error": "أدخل رمزًا من ستة أرقام"}
        row = db.execute("""
            SELECT c.id, c.phone, c.digest, c.created, c.attempts
            FROM phone_challenges c JOIN customer_profiles p ON p.email = c.email AND p.phone = c.phone
            WHERE c.email = ?
        """, (email,)).fetchone()
        if not row or now - row[3] >= LIFETIME or row[4] >= 5:
            return "401 Unauthorized", {"error": "الرمز منتهي أو غير صالح"}
        challenge, phone, expected, _, _ = row
        if not hmac.compare_digest(expected, self._digest(email, phone, challenge, code)):
            db.execute("UPDATE phone_challenges SET attempts = attempts + 1 WHERE email = ?", (email,))
            return "401 Unauthorized", {"error": "الرمز غير صحيح"}
        db.execute("DELETE FROM phone_challenges WHERE email = ?", (email,))
        db.execute("INSERT OR REPLACE INTO verified_phones VALUES (?, ?, ?)", (email, phone, now))
        return "200 OK", {"phone_verified": True}
