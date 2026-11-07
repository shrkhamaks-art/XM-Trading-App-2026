import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.server import create_app


class SessionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.codes = {}
        self.app = create_app(Path(directory.name) / "accounts.sqlite", b"x" * 32, self.codes.__setitem__)

    def request(self, path, body=None, cookie="", *, source="192.0.2.10", forwarded=""):
        payload = json.dumps(body).encode()
        result = []
        env = {
            "PATH_INFO": path, "REQUEST_METHOD": "GET" if body is None else "POST",
            "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(payload)),
            "HTTP_COOKIE": cookie, "wsgi.input": io.BytesIO(payload),
            "REMOTE_ADDR": source, "HTTP_X_FORWARDED_FOR": forwarded,
        }
        b"".join(self.app(env, lambda status, headers: result.extend((int(status.split()[0]), dict(headers)))))
        return result

    def login(self, email):
        self.assertEqual(self.request("/api/code", {"email": email})[0], 200)
        status, headers = self.request("/api/verify", {"email": email, "code": self.codes[email]})
        self.assertEqual(status, 200)
        return headers["Set-Cookie"].split(";", 1)[0]

    def test_logout_all_cancels_sessions_and_pending_code_only_for_caller(self):
        first = "first@example.org"
        other = "other@example.org"
        with patch("backend.server.time.time", return_value=1000):
            device_one = self.login(first)
            another_account = self.login(other)
            self.assertEqual(self.request("/api/code", {"email": first})[0], 429)
        with patch("backend.server.time.time", return_value=1060):
            device_two = self.login(first)
        with patch("backend.server.time.time", return_value=1120):
            self.assertEqual(self.request("/api/code", {"email": first})[0], 200)
            self.assertEqual(self.request("/api/logout-all", {})[0], 401)
            self.assertEqual(self.request("/api/me", cookie=device_two)[0], 200)
            status, headers = self.request("/api/logout-all", {}, device_one)
            self.assertEqual(status, 200)
            self.assertIn("Max-Age=0", headers["Set-Cookie"])
            for cookie in (device_one, device_two):
                self.assertEqual(self.request("/api/me", cookie=cookie)[0], 401)
            self.assertEqual(self.request("/api/me", cookie=another_account)[0], 200)
            self.assertEqual(self.request("/api/verify", {"email": first, "code": self.codes[first]})[0], 401)

    def test_regular_logout_leaves_other_device_signed_in(self):
        email = "first@example.org"
        with patch("backend.server.time.time", return_value=1000):
            first = self.login(email)
        with patch("backend.server.time.time", return_value=1060):
            second = self.login(email)
            self.assertEqual(self.request("/api/logout", {}, first)[0], 200)
            self.assertEqual(self.request("/api/me", cookie=first)[0], 401)
            self.assertEqual(self.request("/api/me", cookie=second)[0], 200)

    def test_one_source_cannot_exhaust_mail_quota_by_spoofing_forwarded_addresses(self):
        for i in range(60):
            result = self.request("/api/code", {"email": f"test{i}@example.org"}, forwarded=f"198.51.100.{i+1}")
            self.assertEqual(result[0], 200 if i < 10 else 429)
        self.assertEqual(len(self.codes), 10)
        self.assertEqual(self.request("/api/code", {"email": "other@example.org"}, source="192.0.2.11")[0], 200)
