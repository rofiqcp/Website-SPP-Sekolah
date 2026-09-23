"""Finance module: units, classes, students, employees, billing, payments, wallet."""
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from . import db, core

finance_bp = Blueprint("finance", __name__, url_prefix="/api")

# ---------------- units ----------------
@finance_bp.get("/units")
@core.require_auth(permissions=["units.manage"])
def list_units():
    return jsonify({"items": db.query_all("SELECT * FROM school_units ORDER BY id")})


# ---------------- classes ----------------
@finance_bp.get("/classes")
@core.require_auth(permissions=["students.view"])
def list_classes():
    user = core.current_user()
    if not core.authorize_unit(user, _any_unit(user)):
        return core.json_error("Tidak berwenang", 403)
    return jsonify({"items": db.query_all(
        "SELECT c.*, u.name AS unit_name FROM classes c JOIN school_units u ON u.id=c.unit_id ORDER BY c.id")})


@finance_bp.post("/classes")
@core.require_auth(permissions=["classes.manage"])
def create_class():
    data = core.get_json()
    unit_id = data.get("unit_id")
    if not core.authorize_unit(core.current_user(), unit_id):
        return core.json_error("Unit tidak berwenang", 403)
    name = str(data.get("name", "")).strip()
    if not name:
        return core.json_error("Nama kelas wajib", 400)
    monthly = core.to_bigint(data.get("monthly_spp", 0))
    with db.engine.begin() as conn:
        cid = conn.execute(text(
            "INSERT INTO classes (unit_id, academic_year_id, name, grade_level, monthly_spp) "
            "VALUES (:u,(SELECT id FROM academic_years WHERE is_active=TRUE LIMIT 1),:n,:g,:s) RETURNING id"),
            {"u": unit_id, "n": name, "g": str(data.get("grade_level", "")), "s": monthly}).scalar_one()
        core.audit("class.create", "classes", cid)
    return jsonify({"message": "Kelas dibuat", "id": cid}), 201


# ---------------- students ----------------
@finance_bp.get("/students")
@core.require_auth(permissions=["students.view"])
def list_students():
    user = core.current_user()
    sql = ("SELECT s.*, c.name AS class_name, u.name AS unit_name, "
           "(SELECT cached_balance FROM financial_accounts WHERE owner_type='student' AND owner_id=s.id AND account_type='wallet' LIMIT 1) AS wallet_balance "
           "FROM students s LEFT JOIN classes c ON c.id=s.class_id LEFT JOIN school_units u ON u.id=s.unit_id")
    params = {}
    if user["role"] in ("wali_kelas", "guru"):
        cls = core.class_ids_for(user)
        if cls:
            sql += " WHERE s.class_id = ANY(:cls)"
            params["cls"] = list(cls)
    sql += " ORDER BY s.id"
    return jsonify({"items": db.query_all(sql, params)})


@finance_bp.post("/students")
@core.require_auth(permissions=["students.manage"])
def create_student():
    data = core.get_json()
    unit_id = data.get("unit_id")
    if not core.authorize_unit(core.current_user(), unit_id):
        return core.json_error("Unit tidak berwenang", 403)
    nis = str(data.get("nis", "")).strip()
    name = str(data.get("full_name", "")).strip()
    if not nis or not name:
        return core.json_error("NIS dan nama wajib", 400)
    with db.engine.begin() as conn:
        sid = conn.execute(text(
            "INSERT INTO students (unit_id, class_id, nis, full_name, guardian_name, guardian_phone, enrollment_status) "
            "VALUES (:u,:c,:nis,:n,:g,:p,'active') RETURNING id"),
            {"u": unit_id, "c": data.get("class_id"), "nis": nis, "n": name,
             "g": str(data.get("guardian_name", "")), "p": str(data.get("guardian_phone", ""))}).scalar_one()
        # auto wallet + savings accounts
        conn.execute(text(
            "INSERT INTO financial_accounts (unit_id, owner_type, owner_id, account_type, account_number, name) "
            "VALUES (:u,'student',:o,'wallet',:an,:n) ON CONFLICT DO NOTHING"),
            {"u": unit_id, "o": sid, "an": f"WAL-{nis}", "n": f"Dompet {name}"})
        conn.execute(text(
            "INSERT INTO financial_accounts (unit_id, owner_type, owner_id, account_type, account_number, name) "
            "VALUES (:u,'student',:o,'savings',:an,:n) ON CONFLICT DO NOTHING"),
            {"u": unit_id, "o": sid, "an": f"SAV-{nis}", "n": f"Tabungan {name}"})
        core.audit("student.create", "students", sid)
    return jsonify({"message": "Siswa dibuat", "id": sid}), 201


@finance_bp.patch("/students/<uuid:item_id>")
@core.require_auth(permissions=["students.manage"])
def update_student(item_id):
    if not core.authorize_student(core.current_user(), item_id):
        return core.json_error("Tidak berwenang", 403)
    data = core.get_json()
    ALLOWED = {"full_name", "guardian_name", "guardian_phone", "class_id", "enrollment_status"}
    fields = {k: data[k] for k in ALLOWED if k in data}
    if not fields:
        return core.json_error("Tidak ada field", 400)
    # reject any key not in whitelist (defense in depth)
    for k in data:
        if k not in ALLOWED:
            return core.json_error(f"Field '{k}' tidak diizinkan", 400)
    sets = ",".join(f"{k}=:{k}" for k in fields)
    fields["id"] = item_id
    with db.engine.begin() as conn:
        conn.execute(text(f"UPDATE students SET {sets} WHERE id=:id"), fields)
        core.audit("student.update", "students", item_id)
    return jsonify({"message": "Siswa diperbarui"})


# ---------------- employees ----------------
@finance_bp.get("/employees")
@core.require_auth(permissions=["students.view"])
def list_employees():
    return jsonify({"items": db.query_all("SELECT * FROM employees ORDER BY id")})


@finance_bp.post("/employees")
@core.require_auth(permissions=["employees.manage"])
def create_employee():
    data = core.get_json()
    unit_id = data.get("unit_id") or None
    no = str(data.get("employee_no", "")).strip()
    name = str(data.get("full_name", "")).strip()
    if not no or not name:
        return core.json_error("No pegawai dan nama wajib", 400)
    with db.engine.begin() as conn:
        eid = conn.execute(text(
            "INSERT INTO employees (unit_id, employee_no, full_name, position, phone, email) "
            "VALUES (:u,:no,:n,:p,:ph,:e) RETURNING id"),
            {"u": unit_id, "no": no, "n": name, "p": str(data.get("position", "")),
             "ph": str(data.get("phone", "")), "e": str(data.get("email", ""))}).scalar_one()
        core.audit("employee.create", "employees", eid)
    return jsonify({"message": "Pegawai dibuat", "id": eid}), 201


# ---------------- billing ----------------
@finance_bp.get("/billing-types")
@core.require_auth(permissions=["billing.manage"])
def list_billing_types():
    return jsonify({"items": db.query_all("SELECT * FROM billing_types ORDER BY id")})


@finance_bp.post("/billing-types")
@core.require_auth(permissions=["billing.manage"])
def create_billing_type():
    data = core.get_json()
    fid = _foundation(core.current_user())
    code = str(data.get("code", "")).strip()
    name = str(data.get("name", "")).strip()
    if not code or not name:
        return core.json_error("Code dan nama wajib", 400)
    with db.engine.begin() as conn:
        bid = conn.execute(text(
            "INSERT INTO billing_types (foundation_id, code, name, is_recurring) VALUES (:f,:c,:n,:r) RETURNING id"),
            {"f": fid, "c": code, "n": name, "r": bool(data.get("is_recurring", False))}).scalar_one()
        core.audit("billing_type.create", "billing_types", bid)
    return jsonify({"id": bid}), 201


@finance_bp.post("/billing/generate")
@core.require_auth(permissions=["billing.generate"])
def generate_invoices():
    data = core.get_json()
    unit_id = data.get("unit_id")
    if not core.authorize_unit(core.current_user(), unit_id):
        return core.json_error("Unit tidak berwenang", 403)
    try:
        period_month = int(data.get("month", 0)) or _now().month
        period_year = int(data.get("year", 0)) or _now().year
    except (TypeError, ValueError):
        return core.json_error("Bulan/tahun tidak valid", 400)
    class_id = data.get("class_id") or None
    created = 0
    with db.engine.begin() as conn:
        rules = conn.execute(text(
            "SELECT r.*, bt.id AS bt_id, bt.name AS bt_name FROM billing_rules r "
            "JOIN billing_types bt ON bt.id=r.billing_type_id WHERE r.unit_id=:u AND r.status='active' "
            + ("AND r.class_id=:c" if class_id else "")),
            {"u": unit_id, "c": class_id}).fetchall()
        ay = conn.execute(text("SELECT id FROM academic_years WHERE is_active=TRUE LIMIT 1")).scalar_one()
        students = conn.execute(text(
            "SELECT id, full_name, class_id FROM students WHERE unit_id=:u AND enrollment_status='active' "
            + ("AND class_id=:c" if class_id else "")),
            {"u": unit_id, "c": class_id}).fetchall()
        for stu in students:
            for r in rules:
                inv_no = f"INV-{stu.id}-{period_year}{period_month:02d}-{r.bt_id}"
                exists = conn.execute(text("SELECT 1 FROM invoices WHERE invoice_number=:n"), {"n": inv_no}).first()
                if exists:
                    continue
                amount = r.amount
                iid = conn.execute(text(
                    "INSERT INTO invoices (unit_id, student_id, invoice_number, academic_year_id, period_month, period_year, subtotal_amount, total_amount, outstanding_amount, due_date) "
                    "VALUES (:u,:s,:n,:ay,:m,:y,:a,:a,:a, (CURRENT_DATE + (:d || ' days')::int)) RETURNING id"),
                    {"u": unit_id, "s": stu.id, "n": inv_no, "ay": ay, "m": period_month, "y": period_year,
                     "a": amount, "d": (r.due_day or 10) - 1}).scalar_one()
                conn.execute(text(
                    "INSERT INTO invoice_items (invoice_id, billing_type_id, description, amount, net_amount, status) "
                    "VALUES (:i,:bt,:d,:a,:a,'unpaid')"),
                    {"i": iid, "bt": r.bt_id, "d": r.bt_name, "a": amount})
                created += 1
        core.audit("billing.generate", "invoices", None, new_value={"count": created, "period": f"{period_year}-{period_month:02d}"})
    return jsonify({"message": f"{created} invoice dibuat", "created": created})


@finance_bp.get("/invoices")
@core.require_auth(permissions=["students.view"])
def list_invoices():
    user = core.current_user()
    sql = ("SELECT i.*, s.full_name AS student_name, s.nis, c.name AS class_name FROM invoices i "
           "JOIN students s ON s.id=i.student_id LEFT JOIN classes c ON c.id=s.class_id")
    params = {}
    if user["role"] in ("siswa", "orang_tua"):
        sid = core.user_student_id(user)
        if sid:
            sql += " WHERE i.student_id = :sid"
            params["sid"] = sid
        else:
            sql += " WHERE 1=0"
    elif user["role"] in ("wali_kelas", "guru"):
        cls = core.class_ids_for(user)
        if cls:
            sql += " WHERE s.class_id = ANY(:cls)"
            params["cls"] = list(cls)
        else:
            sql += " WHERE 1=0"
    sql += " ORDER BY i.period_year DESC, i.period_month DESC, i.id"
    return jsonify({"items": db.query_all(sql, params)})


# ---------------- overdue invoices ----------------
@finance_bp.post("/invoices/mark-overdue")
@core.require_auth(permissions=["invoices.manage"])
def mark_overdue_invoices():
    """Mark overdue invoices (admin only)"""
    user = core.current_user()
    if user["role"] not in ("super_admin", "bendahara", "kepala_sekolah"):
        return core.json_error("Tidak berwenang", 403)
    
    with db.engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE invoices 
            SET status = 'overdue' 
            WHERE due_date < CURRENT_DATE 
              AND status = 'published'
        """))
        updated_count = result.rowcount
    
    return jsonify({
        "message": f"{updated_count} invoice ditandai sebagai overdue",
        "updated": updated_count
    })


@finance_bp.get("/invoices/overdue-check")
@core.require_auth(permissions=["invoices.manage"])
def overdue_invoice_check():
    """Health-check endpoint for cron - mark overdue invoices"""
    user = core.current_user()
    if user["role"] not in ("super_admin", "bendahara", "kepala_sekolah"):
        return core.json_error("Tidak berwenang", 403)
    with db.engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE invoices 
            SET status = 'overdue' 
            WHERE due_date < CURRENT_DATE 
              AND status = 'published'
        """))
        updated_count = result.rowcount
    return jsonify({
        "message": f"{updated_count} invoice ditandai sebagai overdue",
        "updated": updated_count
    })


# ---------------- payments ----------------
@finance_bp.post("/payments")
@core.require_auth(permissions=["payments.create"])
def create_payment():
    user = core.current_user()
    key = core.idempotency_key()
    prior = core.idempotency_guard(key)
    if prior:
        return jsonify(prior), 200
    data = core.get_json()
    unit_id = data.get("unit_id")
    if not unit_id:
        return core.json_error("Unit ID tidak valid", 400)
    if not core.authorize_unit(user, unit_id):
        return core.json_error("Unit tidak berwenang", 403)
    student_id = data.get("student_id")
    if not student_id:
        return core.json_error("Student ID tidak valid", 400)
    invoice_ids = data.get("invoice_ids", [])
    if not invoice_ids:
        return core.json_error("Invoice ID tidak valid", 400)
    amount = core.to_bigint(data.get("amount", 0))
    if amount <= 0:
        return core.json_error("Nominal harus > 0", 400)
    method = str(data.get("method", "Tunai"))[:30]
    result = {"message": "Pembayaran tercatat"}
    fid = _foundation(user)
    with db.engine.begin() as conn:
        # validate amount <= total outstanding
        total_outstanding = 0
        for inv_id in invoice_ids:
            inv = conn.execute(text("SELECT * FROM invoices WHERE id=:id FOR UPDATE"), {"id": inv_id}).first()
            if not inv or inv.student_id != student_id:
                return core.json_error("Invoice tidak ditemukan", 400)
            total_outstanding += inv.outstanding_amount
        if amount > total_outstanding:
            return core.json_error("Nominal melebihi total tunggakan", 400)
        pno = db.gen_reference("PAY")
        pid = conn.execute(text(
            "INSERT INTO payments (unit_id, payment_number, student_id, payer_name, method, amount, paid_at, cashier_user_id, idempotency_key, status) "
            "VALUES (:u,:n,:s,:pn,:m,:a,now(),:c,:k,'success') RETURNING id"),
            {"u": unit_id, "n": pno, "s": student_id, "pn": str(data.get("payer_name", "")), "m": method,
             "a": amount, "c": user["sub"], "k": key}).scalar_one()
        # allocate
        remaining = amount
        allocated = 0
        for inv_id in invoice_ids:
            inv = conn.execute(text("SELECT * FROM invoices WHERE id=:id FOR UPDATE"), {"id": inv_id}).first()
            if not inv or inv.student_id != student_id:
                continue
            unpaid = inv.outstanding_amount
            alloc = min(remaining, unpaid)
            if alloc <= 0:
                continue
            conn.execute(text("INSERT INTO payment_allocations (payment_id, invoice_id, amount) VALUES (:p,:i,:a)"),
                         {"p": pid, "i": inv_id, "a": alloc})
            allocated += alloc
            new_paid = inv.paid_amount + alloc
            new_out = inv.outstanding_amount - alloc
            status = "paid" if new_out <= 0 else "partial"
            conn.execute(text("UPDATE invoices SET paid_amount=:p, outstanding_amount=:o, status=:s WHERE id=:id"),
                         {"p": new_paid, "o": new_out, "s": status, "id": inv_id})
            remaining -= alloc
            if remaining <= 0:
                break
        # journal: debit kas/bank, credit piutang SPP (+ overpayment ke pendapatan diterima dimuka)
        cash_acc = core.coa_id_by_code("1000", fid) if method == "Tunai" else core.coa_id_by_code("1010", fid)
        piutang = core.coa_id_by_code("1100", fid)
        dimuka = core.coa_id_by_code("2200", fid)
        over = max(0, amount - allocated)
        jid = core.post_journal(unit_id, [
            (cash_acc, amount, 0, f"Kas {method}"),
            (piutang, 0, allocated, "Pelunasan piutang SPP"),
            (dimuka, 0, over, "Pendapatan diterima dimuka (overpay)"),
        ], f"Pembayaran {pno}", "payment", pid, user["sub"])
        conn.execute(text("UPDATE payments SET journal_id=:j WHERE id=:id"), {"j": jid, "id": pid})
        core.audit("payment.create", "payments", pid, new_value={"amount": amount, "method": method})
    core.save_idempotency(key, result)
    return jsonify(result), 201


@finance_bp.post("/payments/<uuid:payment_id>/refund")
@core.require_auth(permissions=["payments.refund"])
def refund_payment(payment_id):
    user = core.current_user()
    with db.engine.begin() as conn:
        pay = conn.execute(text("SELECT * FROM payments WHERE id=:id"), {"id": payment_id}).first()
        if not pay or pay.status != "success":
            return core.json_error("Pembayaran tidak ditemukan", 404)
        if not core.authorize_unit(user, pay.unit_id):
            return core.json_error("Unit tidak berwenang", 403)
        # reverse allocations
        allocs = conn.execute(text("SELECT * FROM payment_allocations WHERE payment_id=:id"), {"id": payment_id}).fetchall()
        for a in allocs:
            inv = conn.execute(text("SELECT * FROM invoices WHERE id=:id FOR UPDATE"), {"id": a.invoice_id}).first()
            new_paid = max(0, inv.paid_amount - a.amount)
            new_out = inv.outstanding_amount + a.amount
            conn.execute(text("UPDATE invoices SET paid_amount=:p, outstanding_amount=:o, status=:s WHERE id=:id"),
                         {"p": new_paid, "o": new_out, "s": "partial" if new_out > 0 else "published"})
        fid = _foundation(user)
        cash_acc = core.coa_id_by_code("1000", fid)
        piutang = core.coa_id_by_code("1100", fid)
        core.post_journal(pay.unit_id, [(piutang, pay.amount, 0, "Reverse piutang"), (cash_acc, 0, pay.amount, "Refund kas")],
                          f"Refund {pay.payment_number}", "refund", payment_id, user["sub"])
        conn.execute(text("UPDATE payments SET status='refunded' WHERE id=:id"), {"id": payment_id})
        core.audit("payment.refund", "payments", payment_id)
    return jsonify({"message": "Refund berhasil"})


# ---------------- helpers ----------------
def _now():
    from datetime import datetime
    return datetime.now()


def _foundation(user):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT foundation_id FROM users WHERE id=:id"), {"id": user["sub"]}).first()
    if not row:
        return None
    return row[0]


def _any_unit(user):
    allowed = core.unit_ids_for(user)
    if allowed:
        return next(iter(allowed))
    with db.engine.connect() as conn:
        return conn.execute(text("SELECT id FROM school_units ORDER BY id LIMIT 1")).scalar_one()


# ---------------- payment intents (online VA/QRIS) ----------------
@finance_bp.post("/payments/intents")
@core.require_auth(permissions=["payments.create"])
def create_payment_intent():
    import uuid
    from datetime import timedelta
    user = core.current_user()
    key = core.idempotency_key()
    prior = core.idempotency_guard(key)
    if prior:
        return jsonify(prior), 200
    data = core.get_json()
    unit_id = data.get("unit_id")
    if not core.authorize_unit(user, unit_id):
        return core.json_error("Unit tidak berwenang", 403)
    student_id = data.get("student_id") if data.get("student_id") else None
    amount = core.to_bigint(data.get("amount", 0))
    if amount <= 0:
        return core.json_error("Nominal harus > 0", 400)
    method = str(data.get("method", "")).upper()
    if method not in ("VA", "QRIS"):
        return core.json_error("Method harus VA atau QRIS", 400)
    provider = str(data.get("provider", "dummy"))[:50]
    try:
        exp = _now() + timedelta(hours=int(data.get("expire_hours", 24)))
    except (TypeError, ValueError):
        return core.json_error("expire_hours tidak valid", 400)
    meta = data.get("metadata", {})
    meta_json = __import__("json").dumps(meta, default=str) if isinstance(meta, dict) else "{}"
    with db.engine.begin() as conn:
        pi_id = conn.execute(text(
            "INSERT INTO payment_intents (unit_id, payer_user_id, student_id, method, provider, "
            "amount, expired_at, idempotency_key, metadata, status) "
            "VALUES (:u,:pu,:s,:m,:pr,:a,:e,:k,:mt,'pending') RETURNING id"),
            {"u": unit_id, "pu": user["sub"], "s": student_id, "m": method, "pr": provider,
             "a": amount, "e": exp, "k": key or str(uuid.uuid4()), "mt": meta_json}).scalar_one()
        pcode = db.gen_reference(method)
        conn.execute(text("UPDATE payment_intents SET payment_code=:p WHERE id=:id"),
                     {"p": pcode, "id": pi_id})
        core.audit("payment_intent.create", "payment_intents", pi_id,
                   new_value={"amount": amount, "method": method, "provider": provider})
    result = {"id": str(pi_id), "payment_code": pcode, "amount": amount, "method": method,
              "expired_at": exp.isoformat()}
    if key:
        core.save_idempotency(key, result)
    return jsonify(result), 201


def _validate_hmac(payload_bytes, signature, secret):
    """HMAC-SHA256 verify."""
    import hmac as _hmac
    import hashlib as _hl
    expected = _hmac.new(secret.encode(), payload_bytes, _hl.sha256).hexdigest()
    return _hmac.compare_digest(expected, signature)


@finance_bp.post("/payments/webhook")
def payment_webhook():
    import hashlib
    body = request.get_data()
    sig = request.headers.get("X-Signature", "") or request.args.get("signature", "")
    webhook_secret = __import__("os").environ["WEBHOOK_SECRET"]
    sig_valid = _validate_hmac(body, sig, webhook_secret) if sig else False
    data = request.get_json(silent=True) or {}
    provider = str(data.get("provider", "unknown"))[:50]
    external_id = str(data.get("external_transaction_id", ""))
    status = str(data.get("status", "")).lower()
    amount = core.to_bigint(data.get("amount", 0))
    if amount <= 0:
        return core.json_error("Amount harus > 0", 400)
    payment_code = str(data.get("payment_code", ""))
    idem_key = str(data.get("idempotency_key", ""))
    method = str(data.get("method", "ONLINE"))[:30]
    if not external_id:
        return core.json_error("external_transaction_id wajib", 400)
    # idempotency
    with db.engine.connect() as conn:
        existing = conn.execute(text(
            "SELECT * FROM payment_webhook_events WHERE provider=:p AND external_transaction_id=:e"),
            {"p": provider, "e": external_id}).first()
        if existing:
            return jsonify({"message": "Sudah diproses", "status": existing.processing_status}), 200
    if status not in ("paid", "success", "settlement"):
        payload_hash = hashlib.sha256(body).hexdigest()
        with db.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO payment_webhook_events (provider, external_transaction_id, payload_hash, payload, signature_valid, processing_status) "
                "VALUES (:p,:e,:h,:pl,:sv,'ignored')"),
                {"p": provider, "e": external_id, "h": payload_hash, "pl": __import__("json").dumps(data, default=str), "sv": sig_valid})
        return jsonify({"message": "Ignored"}), 200
    if not sig_valid:
        core.flag_security("webhook_bad_sig", "high", f"Webhook signature invalid dari {provider}",
                           source_module="webhook")
        with db.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO payment_webhook_events (provider, external_transaction_id, payload, signature_valid, processing_status, error_message) "
                "VALUES (:p,:e,:pl,false,'failed','Bad signature')"),
                {"p": provider, "e": external_id, "pl": __import__("json").dumps(data, default=str)})
        return core.json_error("Signature tidak valid", 401)
    # resolve intent
    with db.engine.begin() as conn:
        intent = None
        if payment_code:
            intent = conn.execute(text("SELECT * FROM payment_intents WHERE payment_code=:pc FOR UPDATE"), {"pc": payment_code}).first()
        if not intent and idem_key:
            intent = conn.execute(text("SELECT * FROM payment_intents WHERE idempotency_key=:k FOR UPDATE"), {"k": idem_key}).first()
        if intent and intent.status == "paid":
            conn.execute(text(
                "INSERT INTO payment_webhook_events (provider, external_transaction_id, payload, signature_valid, processing_status) "
                "VALUES (:p,:e,:pl,true,'processed')"),
                {"p": provider, "e": external_id, "pl": __import__("json").dumps(data, default=str)})
            return jsonify({"message": "Intent sudah paid"}), 200
        if intent and intent.status != "pending":
            conn.execute(text(
                "INSERT INTO payment_webhook_events (provider, external_transaction_id, payload, signature_valid, processing_status, error_message) "
                "VALUES (:p,:e,:pl,true,'failed','Intent not pending')"),
                {"p": provider, "e": external_id, "pl": __import__("json").dumps(data, default=str)})
            return core.json_error("Intent tidak valid", 400)
        unit_id = intent.unit_id if intent else None
        if not unit_id:
            return core.json_error("Unit tidak ditemukan", 400)
        pno = db.gen_reference("PAY")
        pid = conn.execute(text(
            "INSERT INTO payments (unit_id, payment_number, student_id, payer_name, method, amount, "
            "provider, external_transaction_id, paid_at, status, metadata) "
            "VALUES (:u,:n,:s,:pn,:m,:a,:pr,:et,now(),'success',:mt) RETURNING id"),
            {"u": unit_id, "n": pno, "s": intent.student_id if intent else None,
             "pn": str(data.get("payer_name", "")), "m": method, "a": amount,
             "pr": provider, "et": external_id, "mt": __import__("json").dumps(data, default=str)}).scalar_one()
        # allocate to invoices from intent metadata
        intent_meta = {}
        if intent and intent.metadata:
            try:
                intent_meta = __import__("json").loads(intent.metadata) if isinstance(intent.metadata, str) else intent.metadata
            except Exception:
                pass
        inv_ids_from_intent = intent_meta.get("invoice_ids", []) if isinstance(intent_meta, dict) else []
        student_id = intent.student_id if intent else None
        if inv_ids_from_intent and student_id:
            remaining = amount
            allocated = 0
            for inv_id in inv_ids_from_intent:
                inv = conn.execute(text("SELECT * FROM invoices WHERE id=:id FOR UPDATE"), {"id": inv_id}).first()
                if not inv or inv.student_id != student_id:
                    continue
                unpaid = inv.outstanding_amount - inv.paid_amount
                alloc = min(remaining, unpaid)
                if alloc <= 0:
                    continue
                conn.execute(text("INSERT INTO payment_allocations (payment_id, invoice_id, amount) VALUES (:p,:i,:a)"),
                             {"p": pid, "i": inv_id, "a": alloc})
                allocated += alloc
                new_paid = inv.paid_amount + alloc
                new_out = inv.outstanding_amount - alloc
                inv_status = "paid" if new_out <= 0 else "partial"
                conn.execute(text("UPDATE invoices SET paid_amount=:p, outstanding_amount=:o, status=:s WHERE id=:id"),
                             {"p": new_paid, "o": new_out, "s": inv_status, "id": inv_id})
                remaining -= alloc
                if remaining <= 0:
                    break
        fid = core.foundation_of_unit(unit_id)
        cash_acc = core.coa_id_by_code("1010", fid)
        piutang = core.coa_id_by_code("1100", fid)
        jid = core.post_journal(unit_id, [
            (cash_acc, amount, 0, f"Kas {method} ({provider})"),
            (piutang, 0, amount, "Pelunasan piutang SPP"),
        ], f"Pembayaran online {pno}", "payment", pid, intent.payer_user_id if intent else None)
        conn.execute(text("UPDATE payments SET journal_id=:j WHERE id=:id"), {"j": jid, "id": pid})
        if intent:
            conn.execute(text("UPDATE payment_intents SET status='paid' WHERE id=:id"), {"id": intent.id})
        payload_hash = hashlib.sha256(body).hexdigest()
        conn.execute(text(
            "INSERT INTO payment_webhook_events (provider, external_transaction_id, payload_hash, payload, signature_valid, processing_status, processed_at) "
            "VALUES (:p,:e,:h,:pl,true,'processed',now())"),
            {"p": provider, "e": external_id, "h": payload_hash, "pl": __import__("json").dumps(data, default=str)})
        core.audit("payment.webhook", "payments", pid, new_value={"amount": amount, "provider": provider})
    return jsonify({"message": "Pembayaran berhasil dicatat", "payment_id": str(pid)}), 200


# ---------------- wallet / ledger ----------------
@finance_bp.get("/wallets")
@core.require_auth(permissions=["students.view"])
def list_wallets():
    return jsonify({"items": db.query_all(
        "SELECT * FROM financial_accounts WHERE account_type IN ('wallet','savings') ORDER BY owner_type, owner_id")})


@finance_bp.get("/wallets/ledger")
@core.require_auth(permissions=["students.view"])
def wallet_ledger_all():
    try:
        limit = int(request.args.get("limit", 50))
        if limit < 1 or limit > 200:
            limit = 50
    except (TypeError, ValueError):
        limit = 50
    return jsonify({"items": db.query_all(
        "SELECT * FROM account_ledger ORDER BY id DESC LIMIT :l", {"l": limit})})


@finance_bp.post("/wallets/topup")
@core.require_auth(permissions=["wallet.topup"])
def wallet_topup():
    user = core.current_user()
    key = core.idempotency_key()
    prior = core.idempotency_guard(key)
    if prior:
        return jsonify(prior), 200
    data = core.get_json()
    account_id = data.get("account_id")
    if not account_id:
        return core.json_error("Account ID tidak valid", 400)
    amount = core.to_bigint(data.get("amount", 0))
    if amount <= 0:
        return core.json_error("Nominal harus > 0", 400)
    method = str(data.get("method", "Tunai"))[:20]
    # teacher limit
    if user["role"] in ("guru", "wali_kelas") and amount > 50000:
        return core.json_error("Melebihi limit top up role Anda (Rp50.000)", 403)
    with db.engine.begin() as conn:
        acc = conn.execute(text("SELECT * FROM financial_accounts WHERE id=:id FOR UPDATE"), {"id": account_id}).first()
        if not acc or acc.status != "active":
            return core.json_error("Akun tidak ditemukan/nonaktif", 404)
        if not core.authorize_unit(user, acc.unit_id):
            return core.json_error("Unit tidak berwenang", 403)
        new_bal = acc.cached_balance + amount
        conn.execute(text("UPDATE financial_accounts SET cached_balance=:b WHERE id=:id"), {"b": new_bal, "id": account_id})
        conn.execute(text(
            "INSERT INTO account_ledger (account_id, transaction_type, direction, amount, balance_after, source_type, description, created_by) "
            "VALUES (:a,'topup','credit',:amt,:b,'topup',:d,:u)"),
            {"a": account_id, "amt": amount, "b": new_bal, "d": f"Top up {method}", "u": user["sub"]})
        fid = _foundation(user)
        cash_acc = core.coa_id_by_code("1000", fid) if method == "Tunai" else core.coa_id_by_code("1010", fid)
        titip = core.coa_id_by_code("2100", fid)
        core.post_journal(acc.unit_id, [(cash_acc, amount, 0, "Kas top up"), (titip, 0, amount, "Titipan dompet")],
                          f"Top up {acc.account_number}", "wallet_topup", account_id, user["sub"])
        core.audit("wallet.topup", "financial_accounts", account_id, new_value={"amount": amount})
    result = {"message": "Top up berhasil", "balance": new_bal}
    core.save_idempotency(key, result)
    return jsonify(result), 201


@finance_bp.post("/wallets/transfer")
@core.require_auth(permissions=["wallet.debit"])
def wallet_transfer():
    user = core.current_user()
    key = core.idempotency_key()
    prior = core.idempotency_guard(key)
    if prior:
        return jsonify(prior), 200
    data = core.get_json()
    from_id = data.get("from_account_id")
    to_id = data.get("to_account_id")
    if not from_id or not to_id:
        return core.json_error("Account ID tidak valid", 400)
    if from_id == to_id:
        return core.json_error("Tidak bisa transfer ke akun yang sama", 400)
    amount = core.to_bigint(data.get("amount", 0))
    if amount <= 0:
        return core.json_error("Nominal harus > 0", 400)
    with db.engine.begin() as conn:
        frm = conn.execute(text("SELECT * FROM financial_accounts WHERE id=:id FOR UPDATE"), {"id": from_id}).first()
        to = conn.execute(text("SELECT * FROM financial_accounts WHERE id=:id FOR UPDATE"), {"id": to_id}).first()
        if not frm or not to or frm.status != "active" or to.status != "active":
            return core.json_error("Akun tidak valid", 404)
        if frm.cached_balance < amount:
            return core.json_error("Saldo tidak cukup", 400)
        nb_f = frm.cached_balance - amount
        nb_t = to.cached_balance + amount
        conn.execute(text("UPDATE financial_accounts SET cached_balance=:b WHERE id=:id"), {"b": nb_f, "id": from_id})
        conn.execute(text("UPDATE financial_accounts SET cached_balance=:b WHERE id=:id"), {"b": nb_t, "id": to_id})
        conn.execute(text(
            "INSERT INTO account_ledger (account_id, transaction_type, direction, amount, balance_after, source_type, description, created_by) "
            "VALUES (:a,'transfer','debit',:amt,:b,'transfer',:d,:u)"),
            {"a": from_id, "amt": amount, "b": nb_f, "d": f"Transfer ke {to.account_number}", "u": user["sub"]})
        conn.execute(text(
            "INSERT INTO account_ledger (account_id, transaction_type, direction, amount, balance_after, source_type, description, created_by) "
            "VALUES (:a,'transfer','credit',:amt,:b,'transfer',:d,:u)"),
            {"a": to_id, "amt": amount, "b": nb_t, "d": f"Transfer dari {frm.account_number}", "u": user["sub"]})
        core.audit("wallet.transfer", "financial_accounts", from_id, new_value={"to": to_id, "amount": amount})
    result = {"message": "Transfer berhasil"}
    core.save_idempotency(key, result)
    return jsonify(result)


@finance_bp.get("/wallets/<uuid:account_id>/ledger")
@core.require_auth(permissions=["students.view"])
def wallet_ledger(account_id):
    user = core.current_user()
    with db.engine.connect() as conn:
        acc = conn.execute(text("SELECT * FROM financial_accounts WHERE id=:id"), {"id": account_id}).first()
    if not acc:
        return core.json_error("Akun tidak ditemukan", 404)
    if not core.authorize_unit(user, acc.unit_id):
        return core.json_error("Tidak berwenang", 403)
    items = db.query_all("SELECT * FROM account_ledger WHERE account_id=:id ORDER BY id DESC LIMIT 200", {"id": account_id})
    return jsonify({"items": items, "balance": acc.cached_balance})


# ---------------- wallet debit ----------------
@finance_bp.post("/wallets/debit")
@core.require_auth(permissions=["wallet.debit"])
def wallet_debit():
    user = core.current_user()
    key = core.idempotency_key()
    prior = core.idempotency_guard(key)
    if prior:
        return jsonify(prior), 200
    data = core.get_json()
    account_id = data.get("account_id")
    if not account_id:
        return core.json_error("Account ID tidak valid", 400)
    amount = core.to_bigint(data.get("amount", 0))
    if amount <= 0:
        return core.json_error("Nominal harus > 0", 400)
    description = str(data.get("description", "Debit dompet"))[:200]
    source_type = str(data.get("source_type", "pos"))[:30]
    with db.engine.begin() as conn:
        acc = conn.execute(text("SELECT * FROM financial_accounts WHERE id=:id FOR UPDATE"), {"id": account_id}).first()
        if not acc or acc.status != "active":
            return core.json_error("Akun tidak ditemukan/nonaktif", 404)
        if not core.authorize_unit(user, acc.unit_id):
            return core.json_error("Unit tidak berwenang", 403)
        if acc.cached_balance < amount:
            return core.json_error("Saldo tidak cukup", 400)
        new_bal = acc.cached_balance - amount
        conn.execute(text("UPDATE financial_accounts SET cached_balance=:b WHERE id=:id"), {"b": new_bal, "id": account_id})
        conn.execute(text(
            "INSERT INTO account_ledger (account_id, transaction_type, direction, amount, balance_after, source_type, description, created_by) "
            "VALUES (:a,'debit','debit',:amt,:b,:st,:d,:u)"),
            {"a": account_id, "amt": amount, "b": new_bal, "st": source_type, "d": description, "u": user["sub"]})
        # journal: debit titipan (reduce liability), credit revenue
        fid = _foundation(user)
        titip = core.coa_id_by_code("2100", fid)
        if source_type == "canteen":
            rev = core.coa_id_by_code("4100", fid)
            desc = f"Pendapatan kantin"
        else:
            rev = core.coa_id_by_code("4200", fid)  # ponytail: other income COA, add when confirmed
            desc = description
        core.post_journal(acc.unit_id, [(titip, amount, 0, "Titipan dompet (debit)"), (rev, 0, amount, desc)],
                          f"Debit {acc.account_number}", "wallet_debit", account_id, user["sub"])
        core.audit("wallet.debit", "financial_accounts", account_id, new_value={"amount": amount, "source_type": source_type})
    result = {"message": "Debit berhasil", "balance": new_bal}
    core.save_idempotency(key, result)
    return jsonify(result), 201


# ---------------- canteen ----------------
@finance_bp.get("/canteen/products")
@core.require_auth(any_of=["canteen.manage", "canteen.checkout"])
def canteen_list_products():
    return jsonify({"items": db.query_all("SELECT * FROM canteen_products WHERE status='active' ORDER BY name")})


@finance_bp.post("/canteen/checkout")
@core.require_auth(permissions=["canteen.checkout"])
def canteen_checkout():
    user = core.current_user()
    key = core.idempotency_key()
    prior = core.idempotency_guard(key)
    if prior:
        return jsonify(prior), 200
    data = core.get_json()
    account_id = data.get("account_id")
    items = data.get("items", [])
    if not account_id or not items:
        return core.json_error("account_id & items wajib", 400)
    # resolve student from wallet account
    with db.engine.connect() as conn:
        acc_check = conn.execute(text("SELECT * FROM financial_accounts WHERE id=:id"), {"id": account_id}).first()
    if not acc_check or acc_check.status != "active" or acc_check.account_type != "wallet":
        return core.json_error("Akun dompet tidak valid", 404)
    if not core.authorize_unit(user, acc_check.unit_id):
        return core.json_error("Unit tidak berwenang", 403)
    student_id = acc_check.owner_id if acc_check.owner_type == "student" else None
    if not student_id:
        return core.json_error("Akun bukan dompet siswa", 400)
    unit_id = acc_check.unit_id
    # build line items + total
    total = 0
    line_items = []
    for it in items:
        pid = it.get("product_id")
        try:
            qty = int(it.get("qty", 1))
        except (TypeError, ValueError):
            return core.json_error("Qty produk tidak valid", 400)
        if qty <= 0:
            return core.json_error(f"Qty produk {pid} tidak valid", 400)
        prod = db.query_one("SELECT * FROM canteen_products WHERE id=:id", {"id": pid})
        if not prod or prod["status"] != "active":
            return core.json_error(f"Produk {pid} tidak tersedia", 400)
        line = prod["selling_price"] * qty
        total += line
        line_items.append((prod, qty, line))
    if total <= 0:
        return core.json_error("Total tidak valid", 400)
    # daily limit
    today_spent = db.query_one(
        "SELECT COALESCE(SUM(total_amount),0) AS t FROM canteen_orders "
        "WHERE student_id=:s AND status='paid' AND created_at >= date_trunc('day', now())",
        {"s": student_id})["t"]
    limit_row = db.query_one("SELECT daily_limit FROM student_spending_limits WHERE student_id=:s AND active", {"s": student_id})
    daily_limit = limit_row["daily_limit"] if limit_row and limit_row.get("daily_limit") is not None else 50000
    if today_spent + total > daily_limit:
        core.flag_security("over_daily_limit", "medium", f"Melebihi limit harian (siswa {student_id})", source_module="canteen", source_id=student_id)
        return core.json_error("Melebihi limit harian", 403)
    result = {}
    with db.engine.begin() as conn:
        acc = conn.execute(text("SELECT * FROM financial_accounts WHERE id=:id FOR UPDATE"), {"id": account_id}).first()
        if acc.cached_balance < total:
            return core.json_error("Saldo dompet tidak cukup", 400)
        new_bal = acc.cached_balance - total
        conn.execute(text("UPDATE financial_accounts SET cached_balance=:b WHERE id=:id"), {"b": new_bal, "id": account_id})
        ono = db.gen_reference("CKN")
        oid = conn.execute(text(
            "INSERT INTO canteen_orders (unit_id, order_number, student_id, cashier_user_id, subtotal_amount, total_amount, payment_method, status) "
            "VALUES (:u,:n,:s,:c,:sub,:t,'wallet','paid') RETURNING id"),
            {"u": unit_id, "n": ono, "s": student_id, "c": user["sub"],
             "sub": total, "t": total}).scalar_one()
        for prod, qty, line in line_items:
            conn.execute(text(
                "INSERT INTO canteen_order_items (order_id, product_id, product_name, qty, unit_price, total_price) "
                "VALUES (:o,:p,:pn,:q,:pr,:t)"),
                {"o": oid, "p": prod["id"], "pn": prod["name"], "q": qty, "pr": prod["selling_price"], "t": line})
            if prod.get("stock_tracking_enabled", True):
                result = conn.execute(text("UPDATE canteen_products SET stock_qty=stock_qty-:q WHERE id=:id AND stock_qty>=:q"),
                             {"q": qty, "id": prod["id"]})
                if result.rowcount == 0:
                    conn.execute(text("ROLLBACK"))
                    return core.json_error(f"Stok produk {prod['id']} tidak cukup", 400)
        conn.execute(text(
            "INSERT INTO account_ledger (account_id, transaction_type, direction, amount, balance_after, source_type, source_id, description, created_by) "
            "VALUES (:a,'canteen_payment','debit',:amt,:b,'canteen',:o,'Belanja kantin',:u)"),
            {"a": account_id, "amt": total, "b": new_bal, "o": oid, "u": user["sub"]})
        fid = _foundation(user)
        titip = core.coa_id_by_code("2100", fid)
        rev = core.coa_id_by_code("4100", fid)
        jid = core.post_journal(unit_id, [(titip, total, 0, "Titipan dompet (kantin)"), (rev, 0, total, "Pendapatan kantin")],
                          f"Kantin {ono}", "canteen", oid, user["sub"])
        conn.execute(text("UPDATE canteen_orders SET journal_id=:j WHERE id=:id"), {"j": jid, "id": oid})
        core.audit("canteen.checkout", "canteen_orders", oid, new_value={"total": total, "account_id": account_id})
        result = {"message": "Pembayaran kantin berhasil", "order_id": str(oid), "total": total, "balance": new_bal}
    core.save_idempotency(key, result)
    return jsonify(result), 201