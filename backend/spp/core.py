"""Security & shared helpers: JWT, RBAC + object-level authorization, rate
limiting, audit logging, idempotency, input validation, security flags."""
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import request, g
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

import os
from . import db

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_EXPIRES_HOURS = int(os.getenv("JWT_EXPIRES_HOURS", "10"))
JWT_REFRESH_HOURS = int(os.getenv("JWT_REFRESH_HOURS", "168"))
RFID_SECRET = os.getenv("RFID_SECRET", JWT_SECRET)

# in-memory rate limit / lock state (ponytail: ganti Redis di scale tinggi)
_RATE = {}


def hash_password(password):
    # werkzeug pbkdf2:sha256 default; cukup kuat. Argon2 jika diinstal.
    return generate_password_hash(password, method="pbkdf2:sha256:260000")


def verify_password(pwhash, password):
    return check_password_hash(pwhash, password)


def hash_rfid_uid(raw_uid):
    """HMAC-hash raw card UID so the DB never stores plaintext UID."""
    return hmac.new(RFID_SECRET.encode(), str(raw_uid).strip().upper().encode(), hashlib.sha256).hexdigest()


# ----------------------------- JWT -----------------------------
def make_tokens(user):
    """user must be a dict with id, email, name, role."""
    now = datetime.now(timezone.utc)
    sub = {"sub": str(user["id"]), "email": user["email"], "role": user["role"], "name": user["name"]}
    access = {**sub, "iat": now, "exp": now + timedelta(hours=JWT_EXPIRES_HOURS), "typ": "access"}
    refresh = {**sub, "iat": now, "exp": now + timedelta(hours=JWT_REFRESH_HOURS), "typ": "refresh"}
    return jwt.encode(access, JWT_SECRET, algorithm="HS256"), jwt.encode(refresh, JWT_SECRET, algorithm="HS256")


def user_role(user_id):
    """Get primary role code for user from user_roles + roles."""
    with db.engine.connect() as conn:
        row = conn.execute(text(
            "SELECT r.code FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE ur.user_id=:u LIMIT 1"), {"u": user_id}).first()
    return row[0] if row else "user"


def decode_token(raw, typ="access"):
    try:
        payload = jwt.decode(raw, JWT_SECRET, algorithms=["HS256"])
        if payload.get("typ") != typ:
            return None
        return payload
    except jwt.PyJWTError:
        return None


def current_user():
    return getattr(g, "user", None)


def token_from_request():
    cookie = request.cookies.get("spp_token")
    header = request.headers.get("Authorization", "")
    raw = cookie or (header.split(" ", 1)[1] if header.startswith("Bearer ") and len(header.split(" ", 1)) > 1 and header.split(" ", 1)[1] else "")
    return raw


# ----------------------------- RBAC -----------------------------
def get_permissions(role_code):
    """Get permissions for a role by looking up role_id from code."""
    with db.engine.connect() as conn:
        rows = conn.execute(
            text("SELECT p.code FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id JOIN roles r ON r.id=rp.role_id WHERE r.code=:r"), {"r": role_code}).fetchall()
    return {r[0] for r in rows}


def require_auth(permissions=None, any_of=None):
    """Decorator: cek login + permission. `any_of` => cukup satu dari daftar."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            raw = token_from_request()
            if not raw:
                return json_error("Login diperlukan", 401)
            user = decode_token(raw, "access")
            if not user:
                return json_error("Sesi tidak valid", 401)
            # check user status and lock
            with db.engine.connect() as conn:
                row = conn.execute(text("SELECT status, locked_until FROM users WHERE id=:id"), {"id": user["sub"]}).first()
            if not row or row[0] != "active":
                return json_error("Akun tidak aktif", 401)
            if row[1]:
                lu = row[1].replace(tzinfo=timezone.utc) if row[1].tzinfo is None else row[1]
                if lu > datetime.now(timezone.utc):
                    return json_error("Akun terkunci", 401)
            g.user = user
            g.perms = get_permissions(user["role"])
            if permissions and not all(p in g.perms for p in permissions):
                return json_error("Akses ditolak", 403)
            if any_of and not any(p in g.perms for p in any_of):
                return json_error("Akses ditolak", 403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ------------------- object-level authorization -------------------
def unit_ids_for(user):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT allowed_units FROM users WHERE id=:id"), {"id": user["sub"]}).first()
    if not row or not row[0]:
        return None  # None = semua unit
    return set(row[0])


def class_ids_for(user):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT allowed_classes FROM users WHERE id=:id"), {"id": user["sub"]}).first()
    if not row or not row[0]:
        return None
    return set(row[0])


def student_unit_id(student_id):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT unit_id FROM students WHERE id=:id"), {"id": student_id}).first()
    return row[0] if row else None


def authorize_unit(user, unit_id):
    allowed = unit_ids_for(user)
    if allowed is None:
        return True
    return unit_id in allowed


def authorize_student(user, student_id):
    """Siswa hanya data sendiri; wali_kelas/guru hanya kelasnya; orang_tua hanya anaknya."""
    role = user["role"]
    if role == "siswa":
        return str(student_id) == str(user_student_id(user))
    if role in ("wali_kelas", "guru"):
        sid = student_unit_id(student_id)
        cls = class_of_student(student_id)
        allowed = class_ids_for(user)
        if allowed is None:
            return True
        return cls in allowed
    if role == "orang_tua":
        return str(student_id) == str(user_student_id(user))
    return True


def user_student_id(user):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT student_id FROM users WHERE id=:id"), {"id": user["sub"]}).first()
    return row[0] if row else None


def class_of_student(student_id):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT class_id FROM students WHERE id=:id"), {"id": student_id}).first()
    return row[0] if row else None


# ----------------------------- rate limit -----------------------------
def rate_limit(key, limit, window):
    now = time.time()
    bucket = _RATE.setdefault(key, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


def login_locked(user_id):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT locked_until FROM users WHERE id=:id"), {"id": user_id}).first()
    if row and row[0]:
        lu = row[0].replace(tzinfo=timezone.utc) if row[0].tzinfo is None else row[0]
        return lu > datetime.now(timezone.utc)
    return False


# ----------------------------- audit -----------------------------
def audit(action, entity_type=None, entity_id=None, old_value=None, new_value=None, foundation_id=None):
    user = current_user()
    actor = user["sub"] if user else None
    fid = foundation_id
    if fid is None and user:
        with db.engine.connect() as conn:
            row = conn.execute(text("SELECT foundation_id FROM users WHERE id=:id"), {"id": user["sub"]}).first()
            fid = row[0] if row else None
    payload = {
        "foundation_id": fid, "actor_user_id": actor, "action": action,
        "object_type": entity_type, "object_id": entity_id,
        "before_data": json.dumps(old_value) if old_value is not None else None,
        "after_data": json.dumps(new_value) if new_value is not None else None,
        "ip_address": request.remote_addr, "user_agent": request.headers.get("User-Agent", "")[:300],
    }
    with db.engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO audit_logs (foundation_id, actor_user_id, action, object_type, object_id, before_data, after_data, ip_address, user_agent) "
            "VALUES (:foundation_id,:actor_user_id,:action,:object_type,:object_id,:before_data,:after_data,:ip_address,:user_agent)"),
            payload)


def flag_security(flag_type, severity, description, source_module=None, source_id=None, user_id=None, device_id=None, unit_id=None):
    with db.engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO security_flags (unit_id, flag_type, severity, source_module, source_id, user_id, description) "
            "VALUES (:u,:ft,:s,:sm,:sid,:uid,:d)"),
            {"u": unit_id, "ft": flag_type, "s": severity, "sm": source_module, "sid": source_id,
             "uid": user_id, "d": description})


# ----------------------------- idempotency -----------------------------
def idempotency_guard(key):
    """Return previous response dict if key already used, else None."""
    if not key:
        return None
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT response_body FROM idempotency_keys WHERE key=:k"), {"k": key}).first()
    return row[0] if row else None


def save_idempotency(key, response):
    if not key:
        return
    with db.engine.begin() as conn:
        conn.execute(text("INSERT INTO idempotency_keys (key, response_body, status) VALUES (:k,:r,'completed') ON CONFLICT (key) DO UPDATE SET response_body=:r"),
                     {"k": key, "r": json.dumps(response, default=str)})


# ----------------------------- helpers -----------------------------
def json_error(message, code=400):
    from flask import jsonify
    return jsonify({"message": message}), code


def client_json(body, code=200):
    from flask import jsonify
    return jsonify(body), code


def get_json():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return {}
    return data


def request_id():
    return request.headers.get("X-Request-Id") or db.gen_reference("req")


def idempotency_key():
    return request.headers.get("X-Idempotency-Key")


def device_id_header():
    return request.headers.get("X-Device-Id")


def to_bigint(value):
    from . import db as _db
    return _db.to_bigint(value)


# ----------------------------- TOTP (RFC 6238, dependency-free) -----------------------------
import base64
import struct


def totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().replace("=", "")


def _b32decode(secret):
    secret = secret.upper().replace(" ", "")
    pad = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret + pad)


def totp_at(secret, counter):
    key = _b32decode(secret)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return binary % 10 ** 6


def totp_now(secret, drift=1):
    counter = int(time.time() // 30)
    return {totp_at(secret, counter + d) for d in range(-drift, drift + 1)}


def totp_verify(secret, code, drift=1):
    try:
        code = int(str(code).strip())
    except (ValueError, TypeError):
        return False
    return code in totp_now(secret, drift)


# ----------------------------- accounting helper -----------------------------
def coa_id_by_code(code, foundation_id):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT id FROM chart_of_accounts WHERE foundation_id=:f AND code=:c"),
                           {"f": foundation_id, "c": code}).first()
    return row[0] if row else None


def foundation_of_unit(unit_id):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT foundation_id FROM school_units WHERE id=:id"), {"id": unit_id}).first()
    return row[0] if row else None


def post_journal(unit_id, lines, description, source_module, source_id, user_id=None):
    """lines: list of (account_id, debit_bigint, credit_bigint, description).
    Validates balanced, inserts journal_entries + journal_lines, returns journal_id."""
    total_debit = sum(l[1] for l in lines)
    total_credit = sum(l[2] for l in lines)
    if total_debit != total_credit:
        raise ValueError("Jurnal tidak seimbang (debit != kredit)")
    if total_debit <= 0:
        raise ValueError("Jurnal kosong")
    fid = foundation_of_unit(unit_id)
    jnum = db.gen_reference("JRN")
    with db.engine.begin() as conn:
        jid = conn.execute(text(
            "INSERT INTO journal_entries (unit_id, journal_number, description, source_module, source_id, posted_by) "
            "VALUES (:u,:n,:d,:sm,:sid,:uid) RETURNING id"),
            {"u": unit_id, "n": jnum, "d": description, "sm": source_module, "sid": source_id,
             "uid": user_id}).scalar_one()
        for account_id, debit, credit, desc in lines:
            conn.execute(text(
                "INSERT INTO journal_lines (journal_id, account_id, debit, credit, description) "
                "VALUES (:j,:a,:d,:c,:desc)"),
                {"j": jid, "a": account_id, "d": debit, "c": credit, "desc": desc})
    return jid
