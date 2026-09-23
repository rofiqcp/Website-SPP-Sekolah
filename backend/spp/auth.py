"""Authentication: login/logout/me, refresh, MFA (TOTP), password change."""
import os
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, make_response, request
from sqlalchemy import text

from . import db, core

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

MAX_FAIL = int(os.getenv("MAX_LOGIN_FAIL", "5"))
LOCK_MINUTES = int(os.getenv("LOCK_MINUTES", "15"))
SECURE_COOKIE = os.getenv("APP_ENV") == "production"


def _user_safe(user):
    """Enrich user dict with role from DB if missing."""
    u = dict(user)
    if "role" not in u or not u.get("role"):
        u["role"] = core.user_role(u["id"])
    return {
        "id": u["id"], "name": u["name"], "email": u["email"],
        "role": u["role"], "mfa_enabled": u.get("mfa_enabled", False),
        "permissions": sorted(core.get_permissions(u["role"])),
    }


def _set_cookies(response, access, refresh):
    response.set_cookie("spp_token", access, httponly=True, secure=SECURE_COOKIE,
                        samesite="Lax", max_age=core.JWT_EXPIRES_HOURS * 3600)
    response.set_cookie("spp_refresh", refresh, httponly=True, secure=SECURE_COOKIE,
                        samesite="Lax", max_age=core.JWT_REFRESH_HOURS * 3600)
    return response


@auth_bp.post("/login")
def login():
    ip = request.remote_addr
    data = core.get_json()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    mfa_code = str(data.get("mfa_code", "")).strip()
    if not email or not password:
        return core.json_error("Email dan password wajib diisi", 400)

    key = f"login:{ip}:{email}"
    if not core.rate_limit(key, 10, 60):
        return core.json_error("Terlalu banyak percobaan. Coba lagi nanti.", 429)

    user = db.query_one("SELECT * FROM users WHERE lower(email)=:e", {"e": email})
    if not user:
        user = db.query_one("SELECT * FROM users WHERE phone=:e", {"e": email})
    with db.engine.connect() as conn:
        uid = user["id"] if user else None
        if not user or core.login_locked(uid):
            with db.engine.begin() as c:
                c.execute(text(
                    "INSERT INTO login_attempts (user_id, email_or_phone, success, ip_address, user_agent, reason) "
                    "VALUES (:u,:e,false,:ip,:ua,:r)"),
                    {"u": uid, "e": email, "ip": ip, "ua": request.headers.get("User-Agent", "")[:300],
                     "r": "locked" if (user and core.login_locked(uid)) else "bad_credentials"})
            return core.json_error("Login gagal atau akun terkunci", 401)

        if not core.verify_password(user["password_hash"], password):
            locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCK_MINUTES) if (user["failed_login_count"] + 1) >= MAX_FAIL else None
            with db.engine.begin() as c:
                c.execute(text("UPDATE users SET failed_login_count = failed_login_count + 1, locked_until=:lu WHERE id=:id"),
                          {"lu": locked_until, "id": user["id"]})
                c.execute(text(
                    "INSERT INTO login_attempts (user_id, email_or_phone, success, ip_address, user_agent, reason) "
                    "VALUES (:u,:e,false,:ip,:ua,'bad_credentials')"),
                    {"u": user["id"], "e": email, "ip": ip, "ua": request.headers.get("User-Agent", "")[:300]})
            return core.json_error("Login gagal", 401)

        # MFA challenge
        if user["mfa_enabled"]:
            if not mfa_code or not core.totp_verify(user["mfa_secret"], mfa_code):
                return jsonify({"mfa_required": True, "message": "Masukkan kode MFA"}), 200

        # success
        role_code = core.user_role(user["id"])
        user_for_token = dict(user)
        user_for_token["role"] = role_code
        with db.engine.begin() as c:
            c.execute(text("UPDATE users SET failed_login_count=0, locked_until=NULL, last_login_at=now() WHERE id=:id"),
                      {"id": user["id"]})
            c.execute(text(
                "INSERT INTO login_attempts (user_id, email_or_phone, success, ip_address, user_agent) "
                "VALUES (:u,:e,true,:ip,:ua)"),
                {"u": user["id"], "e": email, "ip": ip, "ua": request.headers.get("User-Agent", "")[:300]})

    access, refresh = core.make_tokens(user_for_token)
    resp = make_response(jsonify({"user": _user_safe(user_for_token)}))
    return _set_cookies(resp, access, refresh)


@auth_bp.post("/refresh")
def refresh():
    raw = request.cookies.get("spp_refresh")
    user = core.decode_token(raw, "refresh") if raw else None
    if not user:
        return core.json_error("Sesi habis, silakan login", 401)
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT id, name, email, mfa_enabled FROM users WHERE id=:id AND status='active'"),
                           {"id": user["sub"]}).first()
    if not row:
        return core.json_error("User tidak aktif", 401)
    u = db.rowdict(row)
    u["role"] = core.user_role(u["id"])
    access, refresh = core.make_tokens(u)
    resp = make_response(jsonify({"user": _user_safe(u)}))
    return _set_cookies(resp, access, refresh)


@auth_bp.post("/logout")
def logout():
    resp = make_response(jsonify({"message": "Logout berhasil"}))
    resp.delete_cookie("spp_token")
    resp.delete_cookie("spp_refresh")
    return resp


@auth_bp.get("/me")
@core.require_auth()
def me():
    user = core.current_user()
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT id,name,email,mfa_enabled FROM users WHERE id=:id"), {"id": user["sub"]}).first()
    if not row:
        return core.json_error("User tidak ditemukan", 404)
    u = db.rowdict(row)
    u["role"] = core.user_role(u["id"])
    return jsonify({"user": _user_safe(u)})


@auth_bp.post("/mfa/enable")
@core.require_auth()
def mfa_enable():
    secret = core.totp_secret()
    user = core.current_user()
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE users SET mfa_secret=:s WHERE id=:id"), {"s": secret, "id": user["sub"]})
    core.audit("mfa.enable", "users", user["sub"])
    return jsonify({"secret": secret, "message": "Simpan secret di authenticator app, lalu verifikasi."})


@auth_bp.post("/mfa/verify")
@core.require_auth()
def mfa_verify():
    user = core.current_user()
    data = core.get_json()
    code = str(data.get("code", "")).strip()
    if not core.rate_limit(f"mfa_verify:{user['sub']}", 10, 60):
        return core.json_error("Terlalu banyak percobaan MFA. Coba lagi nanti.", 429)
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT mfa_secret FROM users WHERE id=:id"), {"id": user["sub"]}).first()
    if not row or not row[0]:
        return core.json_error("MFA belum di-setup", 400)
    if not core.totp_verify(row[0], code):
        return core.json_error("Kode MFA salah", 400)
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE users SET mfa_enabled=TRUE WHERE id=:id"), {"id": user["sub"]})
    core.audit("mfa.verify", "users", user["sub"])
    return jsonify({"message": "MFA aktif"})


@auth_bp.post("/mfa/disable")
@core.require_auth()
def mfa_disable():
    user = core.current_user()
    data = core.get_json()
    if not core.rate_limit(f"mfa_disable:{user['sub']}", 10, 60):
        return core.json_error("Terlalu banyak percobaan MFA. Coba lagi nanti.", 429)
    secret = _secret_for(user)
    if not secret:
        return core.json_error("MFA belum di-setup", 400)
    if not core.totp_verify(_secret_for(user), str(data.get("code", ""))):
        return core.json_error("Kode MFA salah", 400)
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE users SET mfa_enabled=FALSE WHERE id=:id"), {"id": user["sub"]})
    core.audit("mfa.disable", "users", user["sub"])
    return jsonify({"message": "MFA nonaktif"})


def _secret_for(user):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT mfa_secret FROM users WHERE id=:id"), {"id": user["sub"]}).first()
    return row[0] if row else None


@auth_bp.post("/password")
@core.require_auth()
def change_password():
    user = core.current_user()
    data = core.get_json()
    old = str(data.get("old_password", ""))
    new = str(data.get("new_password", ""))
    if len(new) < 8:
        return core.json_error("Password baru minimal 8 karakter", 400)
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT password_hash FROM users WHERE id=:id"), {"id": user["sub"]}).first()
    if not core.verify_password(row[0], old):
        return core.json_error("Password lama salah", 400)
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE users SET password_hash=:h WHERE id=:id"), {"h": core.hash_password(new), "id": user["sub"]})
    core.audit("password.change", "users", user["sub"])
    return jsonify({"message": "Password diperbarui"})
