"""Smoke tests + security-critical helper checks (stdlib only).

Usage (from backend/):
    python tests/test_smoke.py

DB-dependent endpoint tests are skipped gracefully when PostgreSQL is unavailable.
"""
import os
import sys
import unittest

# Ensure backend/spp is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --------------- 1. Import checks ---------------

class TestImports(unittest.TestCase):
    """Every module imports without side-effect crashes."""

    def test_import_app(self):
        from app import app  # noqa

    def test_import_spp(self):
        from spp import create_app, money  # noqa

    def test_import_db(self):
        from spp import db  # noqa

    def test_import_core(self):
        from spp import core  # noqa

    def test_import_auth(self):
        from spp import auth  # noqa

    def test_import_finance(self):
        from spp import finance  # noqa

    def test_import_ops(self):
        from spp import ops  # noqa

    def test_import_accounting(self):
        from spp import accounting  # noqa

    def test_import_rfid(self):
        from spp import rfid  # noqa

    def test_import_audit(self):
        from spp import audit  # noqa

    def test_import_apk(self):
        from spp import apk  # noqa


# --------------- 2. Security-critical helpers (no DB) ---------------

class TestMoney(unittest.TestCase):
    """Currency formatter edge cases."""

    def test_normal(self):
        from spp import money
        self.assertEqual(money(250000), "Rp 250.000")

    def test_zero(self):
        from spp import money
        self.assertEqual(money(0), "Rp 0")

    def test_large(self):
        from spp import money
        self.assertEqual(money(1234567890), "Rp 1.234.567.890")

    def test_none(self):
        from spp import money
        self.assertEqual(money(None), "Rp 0")

    def test_string(self):
        from spp import money
        self.assertEqual(money("999"), "Rp 999")


class TestToBigint(unittest.TestCase):
    """Finance input validation – rejects negatives and non-numeric."""

    @staticmethod
    def fn(value):
        from spp.db import to_bigint
        return to_bigint(value)

    def test_int(self):
        self.assertEqual(self.fn(50000), 50000)

    def test_string(self):
        self.assertEqual(self.fn("125000"), 125000)

    def test_decimal_string(self):
        """Rounds to nearest rupiah."""
        self.assertEqual(self.fn("250000.4"), 250000)
        self.assertEqual(self.fn("250000.6"), 250001)

    def test_reject_negative(self):
        with self.assertRaises(ValueError):
            self.fn(-100)

    def test_reject_garbage(self):
        with self.assertRaises(ValueError):
            self.fn("abc")

    def test_reject_none_str(self):
        with self.assertRaises(ValueError):
            self.fn(None)  # str(None) => "None" -> invalid decimal


class TestPassword(unittest.TestCase):
    """Hash + verify round-trip."""

    def test_roundtrip(self):
        from spp.core import hash_password, verify_password
        h = hash_password("TestPass123!")
        self.assertTrue(verify_password(h, "TestPass123!"))
        self.assertFalse(verify_password(h, "WrongPass"))

    def test_hash_differs(self):
        from spp.core import hash_password
        h1, h2 = hash_password("x"), hash_password("x")
        self.assertNotEqual(h1, h2)  # salted


class TestJWT(unittest.TestCase):
    """Token create/decode without DB."""

    def test_roundtrip(self):
        from spp.core import make_tokens, decode_token
        user = {"id": 1, "email": "a@b.com", "role": "admin", "name": "A"}
        access, refresh = make_tokens(user)
        payload = decode_token(access, "access")
        self.assertIsNotNone(payload)
        self.assertEqual(payload["email"], "a@b.com")
        self.assertEqual(payload["typ"], "access")

    def test_wrong_type(self):
        from spp.core import make_tokens, decode_token
        user = {"id": 1, "email": "a@b.com", "role": "admin", "name": "A"}
        access, _ = make_tokens(user)
        # decoding access as refresh should return None
        self.assertIsNone(decode_token(access, "refresh"))

    def test_tampered(self):
        from spp.core import decode_token
        self.assertIsNone(decode_token("invalid.token.here"))


class TestRateLimit(unittest.TestCase):
    """In-memory rate limiter."""

    def test_allows_within_limit(self):
        from spp.core import rate_limit
        key = "test:rl:1"
        for _ in range(3):
            self.assertTrue(rate_limit(key, 5, 60))

    def test_blocks_after_limit(self):
        from spp.core import rate_limit
        key = "test:rl:2"
        for _ in range(5):
            rate_limit(key, 5, 60)
        self.assertFalse(rate_limit(key, 5, 60))

    def test_empty_key(self):
        from spp.core import rate_limit
        self.assertTrue(rate_limit("", 5, 60))


class TestTOTP(unittest.TestCase):
    """TOTP helpers (no DB)."""

    def test_secret_format(self):
        from spp.core import totp_secret
        s = totp_secret()
        self.assertTrue(len(s) > 0)
        self.assertEqual(s.replace("=", ""), s)  # no padding chars left

    def test_verify_correct_code(self):
        from spp.core import totp_secret, totp_now, totp_verify
        s = totp_secret()
        valid_codes = totp_now(s)
        self.assertTrue(totp_verify(s, list(valid_codes)[0]))

    def test_verify_wrong_code(self):
        from spp.core import totp_secret, totp_verify
        s = totp_secret()
        self.assertFalse(totp_verify(s, 0))

    def test_verify_garbage(self):
        from spp.core import totp_verify
        self.assertFalse(totp_verify("AAAA", "not-a-number"))


class TestRfidHash(unittest.TestCase):
    """RFID UID hashing is deterministic."""

    def test_deterministic(self):
        from spp.core import hash_rfid_uid
        h1 = hash_rfid_uid("A1B2C3")
        h2 = hash_rfid_uid("a1b2c3")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # sha256 hex


# --------------- 3. Flask test_client (DB-dependent, graceful skip) ---------------

def _has_db():
    """Quick check: can we connect to PostgreSQL?"""
    try:
        from spp import db
        with db.engine.connect() as conn:
            conn.execute(db.text("SELECT 1"))
        return True
    except Exception:
        return False


class TestHealthEndpoint(unittest.TestCase):
    """GET /health → ok if DB available."""

    def setUp(self):
        from spp import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_health_with_db(self):
        if not _has_db():
            self.skipTest("PostgreSQL not available")
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("database", data)


class TestApkLatestEndpoint(unittest.TestCase):
    """GET /api/apk/latest → public, no DB required."""

    def setUp(self):
        from spp import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_latest_no_apk(self):
        resp = self.client.get("/api/apk/latest")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("version", data)
        self.assertIn("available", data)
        # available may be False if no APK in static/download/


class TestDashboardEndpoint(unittest.TestCase):
    """GET /api/dashboard → public data without auth."""

    def setUp(self):
        from spp import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_dashboard_public(self):
        resp = self.client.get("/api/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("school", data)
        self.assertIn("modules", data)
        # public stats when no user
        self.assertIsInstance(data["stats"], list)

    def test_security_headers(self):
        resp = self.client.get("/api/dashboard")
        self.assertIn("Content-Security-Policy", resp.headers)
        self.assertIn("X-Content-Type-Options", resp.headers)
        self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("Strict-Transport-Security", resp.headers)
        self.assertEqual(resp.headers["Cache-Control"], "no-store")


class TestAuthLoginEndpoint(unittest.TestCase):
    """POST /api/auth/login → validation without hitting DB."""

    def setUp(self):
        from spp import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_login_missing_fields(self):
        resp = self.client.post("/api/auth/login", json={})
        self.assertEqual(resp.status_code, 400)

    def test_login_empty_email(self):
        resp = self.client.post("/api/auth/login", json={"email": "", "password": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_login_empty_password(self):
        resp = self.client.post("/api/auth/login", json={"email": "a@b.com", "password": ""})
        self.assertEqual(resp.status_code, 400)

    def test_login_bad_credentials(self):
        if not _has_db():
            self.skipTest("PostgreSQL not available")
        resp = self.client.post("/api/auth/login", json={
            "email": "nonexistent@test.com", "password": "wrong"})
        self.assertEqual(resp.status_code, 401)


class TestErrorHandlers(unittest.TestCase):
    """Flask error handlers return JSON."""

    def setUp(self):
        from spp import create_app
        self.app = create_app()
        self.client = self.app.test_client()

    def test_404_json(self):
        resp = self.client.get("/api/nonexistent-route-xyz")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertIn("message", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
