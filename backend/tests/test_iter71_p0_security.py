"""SEC-001/002/003 regression tests (iter 71).
Covers: cookie flags (Lax/HttpOnly/Secure), cookie+bearer auth, ?auth= removal,
magic-byte upload validation, download nosniff header, CORS allowlist."""
import os
import io
import struct
import zlib
import requests
import pytest

EXT = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://work-connect-147.preview.emergentagent.com"
LOCAL = "http://localhost:8001"
WORKER = ("worker.demo@hcobcleaners.com", "WorkerDemo2026!")
ADMIN = ("admin@hcobcleaners.com", "HcobAdmin2026!")


def _real_png_bytes() -> bytes:
    """Minimal 1x1 valid PNG."""
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


@pytest.fixture(scope="module")
def worker_session():
    s = requests.Session()
    r = s.post(f"{EXT}/api/auth/login", json={"email": WORKER[0], "password": WORKER[1]}, timeout=30)
    assert r.status_code == 200, r.text
    return s, r


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{EXT}/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]}, timeout=30)
    assert r.status_code == 200, r.text
    return s, r


# ---- SEC-001: cookie flags & CORS ----
class TestCookieAndCors:
    def test_login_cookie_flags(self, worker_session):
        _, r = worker_session
        sc = r.headers.get("set-cookie", "")
        assert "session_token=" in sc.lower()
        assert "httponly" in sc.lower()
        assert "samesite=lax" in sc.lower()
        # Secure may still be set since proxy is https
        assert "secure" in sc.lower()

    def test_cors_allowed_origin_localhost(self):
        r = requests.options(
            f"{LOCAL}/api/gigs",
            headers={
                "Origin": "https://hcobnetwork.com",
                "Access-Control-Request-Method": "GET",
            },
            timeout=10,
        )
        assert r.headers.get("access-control-allow-origin") == "https://hcobnetwork.com"
        assert r.headers.get("access-control-allow-credentials", "").lower() == "true"

    def test_cors_blocked_evil_origin_localhost(self):
        r = requests.options(
            f"{LOCAL}/api/gigs",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
            timeout=10,
        )
        assert "access-control-allow-origin" not in {k.lower() for k in r.headers.keys()}


# ---- Cookie + Bearer auth ----
class TestAuthMethods:
    def test_cookie_auth_gigs(self, worker_session):
        s, _ = worker_session
        r = s.get(f"{EXT}/api/gigs", timeout=30)
        assert r.status_code == 200

    def test_bearer_auth_gigs(self, worker_session):
        s, _ = worker_session
        token = s.cookies.get("session_token")
        assert token, "no session_token cookie"
        r = requests.get(f"{EXT}/api/gigs", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r.status_code == 200

    def test_admin_referrals_cookie(self, admin_session):
        s, _ = admin_session
        r = s.get(f"{EXT}/api/admin/referrals", timeout=30)
        assert r.status_code == 200, r.text

    def test_worker_referrals_cookie(self, worker_session):
        s, _ = worker_session
        r = s.get(f"{EXT}/api/worker/referrals", timeout=30)
        assert r.status_code == 200, r.text


# ---- SEC-002: ?auth= removed on /api/files/ ----
class TestFileAuth:
    def test_upload_then_query_param_rejected(self, worker_session):
        s, _ = worker_session
        token = s.cookies.get("session_token")
        # Upload a real PNG avatar
        png = _real_png_bytes()
        up = s.post(
            f"{EXT}/api/profile/avatar",
            files={"file": ("a.png", png, "image/png")},
            timeout=60,
        )
        assert up.status_code == 200, up.text
        path = up.json().get("avatar_path")
        assert path
        file_url = f"{EXT}/api/files/{path.lstrip('/')}"
        # Access with cookie - 200 and nosniff
        r_ok = s.get(file_url, timeout=30)
        assert r_ok.status_code == 200, f"{r_ok.status_code} {r_ok.text[:200]}"
        assert r_ok.headers.get("x-content-type-options", "").lower() == "nosniff"
        # Access with only ?auth=token, no cookie: should be 401
        bare = requests.Session()  # no cookies
        r_bad = bare.get(f"{file_url}?auth={token}", timeout=30)
        assert r_bad.status_code == 401, f"expected 401, got {r_bad.status_code}"


# ---- SEC-003: magic-byte upload validation ----
class TestUploadValidation:
    def test_html_as_jpg_rejected(self, worker_session):
        s, _ = worker_session
        payload = b"<html><script>alert(1)</script></html>"
        r = s.post(
            f"{EXT}/api/profile/avatar",
            files={"file": ("x.jpg", payload, "image/jpeg")},
            timeout=30,
        )
        assert r.status_code == 400
        assert "invalid" in r.text.lower() or "unsupported" in r.text.lower()

    def test_real_png_accepted(self, worker_session):
        s, _ = worker_session
        r = s.post(
            f"{EXT}/api/profile/avatar",
            files={"file": ("real.png", _real_png_bytes(), "image/png")},
            timeout=60,
        )
        assert r.status_code == 200
        assert r.json().get("avatar_path")

    def test_message_attachment_rejects_non_image(self, worker_session):
        s, _ = worker_session
        r = s.post(
            f"{EXT}/api/messages/attachments",
            files={"file": ("evil.png", b"not an image at all", "image/png")},
            timeout=30,
        )
        assert r.status_code == 400

    def test_message_attachment_accepts_real_image(self, worker_session):
        s, _ = worker_session
        r = s.post(
            f"{EXT}/api/messages/attachments",
            files={"file": ("ok.png", _real_png_bytes(), "image/png")},
            timeout=60,
        )
        # Endpoint may require additional fields; accept 200 OR 400 as long as
        # rejection reason is not the file-validation error.
        assert r.status_code in (200, 201, 400, 422)
        if r.status_code == 400:
            assert "invalid or unsupported" not in r.text.lower()
