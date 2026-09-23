"""RFID: card management, device registration, scan, issue, block/replace, terminals."""
import secrets

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from . import db, core

rfid_bp = Blueprint("rfid", __name__, url_prefix="/api")


@rfid_bp.get("/rfid/cards")
@core.require_auth(permissions=["rfid.manage", "students.view"], any_of=["rfid.manage", "students.view"])
def list_cards():
    user = core.current_user()
    sql = "SELECT c.*, s.full_name AS student_name FROM rfid_cards c LEFT JOIN students s ON s.id=c.student_id ORDER BY c.id DESC"
    if user["role"] not in ("super_admin", "admin_unit", "bendahara"):
        sql += " LIMIT 200"
    return jsonify({"items": db.query_all(sql)})


@rfid_bp.post("/rfid/scan")
@core.require_auth(permissions=["canteen.checkout", "wallet.topup", "rfid.manage"], any_of=["canteen.checkout", "wallet.topup", "rfid.manage"])
def scan_card():
    user = core.current_user()
    data = core.get_json()
    raw_uid = str(data.get("raw_uid", "")).strip()
    if not raw_uid:
        return core.json_error("raw_uid wajib", 400)
    # terminal validation: if terminal_id provided, check allowed_modules
    terminal_id = str(data.get("terminal_id", "")).strip()
    context = str(data.get("context", "scan")).strip()
    if terminal_id:
        term = db.query_one("SELECT * FROM web_terminals WHERE terminal_code=:c AND status='active'", {"c": terminal_id})
        if not term:
            core.flag_security("unknown_terminal", "medium", f"Terminal tidak dikenal: {terminal_id}", source_module="rfid")
            return core.json_error("Terminal tidak terdaftar/nonaktif", 403)
        allowed = term.get("allowed_modules") or []
        if allowed and context not in allowed:
            core.flag_security("terminal_module_violation", "high", f"Terminal {terminal_id} tidak diizinkan modul {context}", source_module="rfid", source_id=term["id"])
            return core.json_error("Terminal tidak diizinkan untuk modul ini", 403)
    uid_hash = core.hash_rfid_uid(raw_uid)
    card = db.query_one("SELECT * FROM rfid_cards WHERE card_uid_hash=:h", {"h": uid_hash})
    if not card:
        core.flag_security("unknown_card", "medium", "RFID scan kartu tidak dikenal", source_module="rfid")
        return jsonify({"status": "unknown_card"})
    if card["status"] != "active":
        return jsonify({"status": "blocked_card", "reason": card.get("blocked_reason")})
    student = db.query_one(
        "SELECT s.id, s.full_name, c.name AS class_name, "
        "(SELECT cached_balance FROM financial_accounts WHERE owner_type='student' AND owner_id=s.id AND account_type='wallet' LIMIT 1) AS wallet_balance "
        "FROM students s LEFT JOIN classes c ON c.id=s.class_id WHERE s.id=:id", {"id": card["student_id"]})
    with db.engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO rfid_card_events (card_id, event_type, user_id, ip_address, metadata) VALUES (:c,'scanned',:u,:ip,:m)"),
            {"c": card["id"], "u": user["sub"], "ip": request.remote_addr,
             "m": __import__("json").dumps({"context": context, "terminal_id": terminal_id})})
        # update terminal last_seen
        if terminal_id:
            conn.execute(text("UPDATE web_terminals SET last_seen_at=now(), last_ip=:ip WHERE terminal_code=:c"),
                         {"ip": request.remote_addr, "c": terminal_id})
    return jsonify({"status": "active", "card_id": card["id"], "student": student})


@rfid_bp.post("/rfid/cards/issue")
@core.require_auth(permissions=["rfid.issue"])
def issue_card():
    user = core.current_user()
    data = core.get_json()
    raw_uid = str(data.get("raw_uid", "")).strip()
    student_id = int(data.get("student_id", 0))
    if not raw_uid or not student_id:
        return core.json_error("raw_uid dan student_id wajib", 400)
    uid_hash = core.hash_rfid_uid(raw_uid)
    if db.query_one("SELECT 1 FROM rfid_cards WHERE card_uid_hash=:h", {"h": uid_hash}):
        return core.json_error("Kartu sudah terdaftar", 400)
    if not core.authorize_student(user, student_id):
        return core.json_error("Tidak berwenang", 403)
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE rfid_cards SET status='replaced', replaced_by_card_id=NULL WHERE student_id=:s AND status='active'"),
                     {"s": student_id})
        cid = conn.execute(text(
            "INSERT INTO rfid_cards (unit_id, student_id, card_uid_hash, card_public_id, card_type, card_label, status, issued_at, created_by) "
            "VALUES (:u,:s,:h,:p,'UID_ONLY',:l,'active',now(),:cr) RETURNING id"),
            {"u": _user_unit(user), "s": student_id, "h": uid_hash,
             "p": f"YC{db.gen_reference('C')}", "l": str(data.get("card_label", "Kartu Siswa")), "cr": user["sub"]}).scalar_one()
        conn.execute(text("INSERT INTO rfid_card_events (card_id, event_type, user_id) VALUES (:c,'issued',:u)"),
                     {"c": cid, "u": user["sub"]})
        core.audit("rfid.issue", "rfid_cards", cid, new_value={"student_id": student_id})
    return jsonify({"message": "Kartu diterbitkan", "card_id": cid}), 201


@rfid_bp.post("/rfid/cards/<int:card_id>/block")
@core.require_auth(permissions=["rfid.block"])
def block_card(card_id):
    data = core.get_json()
    reason = str(data.get("reason", "diblokir"))
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE rfid_cards SET status='blocked', blocked_at=now(), blocked_reason=:r WHERE id=:id"),
                     {"r": reason, "id": card_id})
        conn.execute(text("INSERT INTO rfid_card_events (card_id, event_type, user_id) VALUES (:c,'blocked',:u)"),
                     {"c": card_id, "u": core.current_user()["sub"]})
        core.audit("rfid.block", "rfid_cards", card_id, new_value={"reason": reason})
    return jsonify({"message": "Kartu diblokir"})


@rfid_bp.post("/rfid/cards/<int:card_id>/lost")
@core.require_auth(permissions=["rfid.block"])
def lost_card(card_id):
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE rfid_cards SET status='lost', blocked_at=now(), blocked_reason='hilang' WHERE id=:id"), {"id": card_id})
        conn.execute(text("INSERT INTO rfid_card_events (card_id, event_type, user_id) VALUES (:c,'lost_reported',:u)"),
                     {"c": card_id, "u": core.current_user()["sub"]})
        core.audit("rfid.lost", "rfid_cards", card_id)
    return jsonify({"message": "Laporan kartu hilang diterima. Saldo tetap aman di server."})


@rfid_bp.get("/rfid/devices")
@core.require_auth(permissions=["rfid.manage"])
def list_devices():
    return jsonify({"items": db.query_all("SELECT * FROM rfid_devices ORDER BY id")})


@rfid_bp.post("/rfid/devices")
@core.require_auth(permissions=["rfid.manage"])
def register_device():
    data = core.get_json()
    unit_id = _user_unit(core.current_user())
    code = str(data.get("device_code", "")).strip()
    if not code:
        return core.json_error("device_code wajib", 400)
    api_key = secrets.token_hex(24)
    api_key_hash = core.hash_rfid_uid(api_key)  # reuse hmac
    with db.engine.begin() as conn:
        did = conn.execute(text(
            "INSERT INTO rfid_devices (unit_id, device_code, device_name, device_type, location_type, location_name, allowed_modules, api_key_hash) "
            "VALUES (:u,:c,:n,:t,:lt,:ln,:am,:k) RETURNING id"),
            {"u": unit_id, "c": code, "n": str(data.get("device_name", code)), "t": str(data.get("device_type", "reader")),
             "lt": str(data.get("location_type", "kantin")), "ln": str(data.get("location_name", "")),
             "am": data.get("allowed_modules", ["canteen"]), "k": api_key_hash}).scalar_one()
        core.audit("rfid.device.register", "rfid_devices", did)
    # return plaintext api_key ONCE
    return jsonify({"id": did, "api_key": api_key, "message": "Simpan api_key, tidak ditampilkan lagi."}), 201


# ---------------- web terminals ----------------
@rfid_bp.get("/terminals")
@core.require_auth(permissions=["rfid.manage"])
def list_terminals():
    return jsonify({"items": db.query_all("SELECT * FROM web_terminals ORDER BY enrolled_at DESC")})


@rfid_bp.post("/terminals/enroll")
@core.require_auth(permissions=["rfid.manage"])
def enroll_terminal():
    user = core.current_user()
    data = core.get_json()
    code = str(data.get("terminal_code", "")).strip()
    name = str(data.get("terminal_name", "")).strip()
    if not code or not name:
        return core.json_error("terminal_code dan terminal_name wajib", 400)
    unit_id = _user_unit(user)
    location = str(data.get("location_name", "")).strip()
    allowed = data.get("allowed_modules", ["canteen"])
    pubkey = str(data.get("public_key", "")).strip()
    if db.query_one("SELECT 1 FROM web_terminals WHERE terminal_code=:c", {"c": code}):
        return core.json_error("Terminal code sudah terdaftar", 400)
    with db.engine.begin() as conn:
        tid = conn.execute(text(
            "INSERT INTO web_terminals (unit_id, terminal_code, terminal_name, location_name, allowed_modules, public_key, status, enrolled_by) "
            "VALUES (:u,:c,:n,:l,:am,:pk,'active',:uid) RETURNING id"),
            {"u": unit_id, "c": code, "n": name, "l": location,
             "am": allowed if isinstance(allowed, list) else [allowed],
             "pk": pubkey or None, "uid": user["sub"]}).scalar_one()
        core.audit("terminal.enroll", "web_terminals", tid)
    return jsonify({"id": str(tid), "terminal_code": code, "message": "Terminal terdaftar"}), 201


@rfid_bp.patch("/terminals/<uuid:terminal_id>/block")
@core.require_auth(permissions=["rfid.manage"])
def block_terminal(terminal_id):
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE web_terminals SET status='blocked' WHERE id=:id"), {"id": terminal_id})
        core.audit("terminal.block", "web_terminals", terminal_id)
    return jsonify({"message": "Terminal diblokir"})


def _user_unit(user):
    allowed = core.unit_ids_for(user)
    if allowed:
        return next(iter(allowed))
    with db.engine.connect() as conn:
        return conn.execute(text("SELECT id FROM school_units ORDER BY id LIMIT 1")).scalar_one()
