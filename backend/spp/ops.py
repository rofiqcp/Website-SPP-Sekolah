"""Operations: cashier sessions, e-kantin (RFID checkout), inventory, assets."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from . import db, core

ops_bp = Blueprint("ops", __name__, url_prefix="/api")


# ---------------- cashier sessions ----------------
@ops_bp.post("/cashier/sessions/open")
@core.require_auth(permissions=["cashier.open"])
def open_session():
    user = core.current_user()
    unit_id = _user_unit(user)
    if not unit_id:
        return core.json_error("User tidak punya unit", 400)
    with db.engine.begin() as conn:
        open_one = conn.execute(text(
            "SELECT id FROM cashier_sessions WHERE cashier_user_id=:u AND status='open'"), {"u": user["sub"]}).first()
        if open_one:
            return core.json_error("Masih ada shift terbuka", 400)
        opening = core.to_bigint(request.get_json(silent=True).get("opening_cash", 0) if request.get_json(silent=True) else 0)
        sid = conn.execute(text(
            "INSERT INTO cashier_sessions (unit_id, cashier_user_id, location_type, opening_cash) "
            "VALUES (:u,:c,'school',:o) RETURNING id"),
            {"u": unit_id, "c": user["sub"], "o": opening}).scalar_one()
        core.audit("cashier.open", "cashier_sessions", sid)
    return jsonify({"message": "Shift kasir dibuka", "session_id": sid}), 201


@ops_bp.post("/cashier/sessions/close")
@core.require_auth(permissions=["cashier.open"])
def close_session():
    user = core.current_user()
    data = core.get_json()
    actual = core.to_bigint(data.get("closing_cash_actual", 0))
    with db.engine.begin() as conn:
        sess = conn.execute(text(
            "SELECT * FROM cashier_sessions WHERE cashier_user_id=:u AND status='open' ORDER BY id DESC LIMIT 1"),
            {"u": user["sub"]}).first()
        if not sess:
            return core.json_error("Tidak ada shift terbuka", 404)
        system = conn.execute(text(
            "SELECT COALESCE(SUM(amount),0) AS s FROM cash_movements WHERE session_id=:id"),
            {"id": sess.id}).first()[0]
        diff = actual - (sess.opening_cash + system)
        conn.execute(text(
            "UPDATE cashier_sessions SET status='closed', closed_at=now(), closing_cash_system=:s, closing_cash_actual=:a, difference_amount=:d WHERE id=:id"),
            {"s": system, "a": actual, "d": diff, "id": sess.id})
        core.audit("cashier.close", "cashier_sessions", sess.id, new_value={"difference": diff})
    return jsonify({"message": "Shift ditutup", "difference": diff})


def _active_session(user):
    with db.engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM cashier_sessions WHERE cashier_user_id=:u AND status='open' ORDER BY id DESC LIMIT 1"),
            {"u": user["sub"]}).first()
    return row[0] if row else None


@ops_bp.post("/cashier/pay")
@core.require_auth(permissions=["cashier.pay"])
def cashier_pay():
    user = core.current_user()
    session_id = _active_session(user)
    if not session_id:
        return core.json_error("Buka shift kasir dulu", 400)
    key = core.idempotency_key()
    if core.idempotency_guard(key):
        return jsonify({"message": "Sudah diproses"}), 200
    data = core.get_json()
    unit_id = _user_unit(user)
    student_id = int(data.get("student_id", 0))
    invoice_ids = [int(x) for x in data.get("invoice_ids", [])]
    amount = core.to_bigint(data.get("amount", 0))
    if amount <= 0 or not invoice_ids:
        return core.json_error("Data tidak valid", 400)
    with db.engine.begin() as conn:
        pno = db.gen_reference("CSH")
        pid = conn.execute(text(
            "INSERT INTO payments (unit_id, payment_number, student_id, payer_name, method, amount, cashier_user_id, idempotency_key, status) "
            "VALUES (:u,:n,:s,'',:m,:a,:c,:k,'success') RETURNING id"),
            {"u": unit_id, "n": pno, "s": student_id, "m": "Tunai", "a": amount, "c": user["sub"], "k": key}).scalar_one()
        remaining = amount
        for inv_id in invoice_ids:
            inv = conn.execute(text("SELECT * FROM invoices WHERE id=:id FOR UPDATE"), {"id": inv_id}).first()
            if not inv or inv.student_id != student_id:
                continue
            alloc = min(remaining, inv.outstanding_amount)
            if alloc <= 0:
                continue
            conn.execute(text("INSERT INTO payment_allocations (payment_id, invoice_id, amount) VALUES (:p,:i,:a)"),
                         {"p": pid, "i": inv_id, "a": alloc})
            conn.execute(text("UPDATE invoices SET paid_amount=paid_amount+:a, outstanding_amount=outstanding_amount-:a, status=(CASE WHEN outstanding_amount-:a<=0 THEN 'paid' ELSE 'partial' END) WHERE id=:id"),
                         {"a": alloc, "id": inv_id})
            remaining -= alloc
        conn.execute(text(
            "INSERT INTO cash_movements (session_id, movement_type, source_type, source_id, amount, method, description) "
            "VALUES (:s,'in','payment',:p,:a,'cash','Pembayaran kasir')"),
            {"s": session_id, "p": pid, "a": amount})
        fid = _foundation(user)
        cash_acc = core.coa_id_by_code("1000", fid)
        piutang = core.coa_id_by_code("1100", fid)
        core.post_journal(unit_id, [(cash_acc, amount, 0, "Kas tunai"), (piutang, 0, amount, "Piutang SPP")],
                          f"Kasir {pno}", "cashier_pay", pid, user["sub"])
        core.audit("cashier.pay", "payments", pid, new_value={"amount": amount})
    return jsonify({"message": "Pembayaran kasir tercatat", "session_id": session_id}), 201


# ---------------- canteen ----------------
@ops_bp.get("/canteen/products")
@core.require_auth(permissions=["canteen.manage"])
def list_products():
    return jsonify({"items": db.query_all("SELECT * FROM canteen_products ORDER BY name")})


@ops_bp.post("/canteen/products")
@core.require_auth(permissions=["canteen.manage"])
def create_product():
    data = core.get_json()
    unit_id = _user_unit(core.current_user())
    name = str(data.get("name", "")).strip()
    if not name:
        return core.json_error("Nama wajib", 400)
    with db.engine.begin() as conn:
        pid = conn.execute(text(
            "INSERT INTO canteen_products (unit_id, name, selling_price, cost_price, stock_qty, status) "
            "VALUES (:u,:n,:p,:c,:s,'active') RETURNING id"),
            {"u": unit_id, "n": name, "p": core.to_bigint(data.get("selling_price", 0)),
             "c": core.to_bigint(data.get("cost_price", 0)), "s": int(data.get("stock", 0))}).scalar_one()
        core.audit("canteen.product.create", "canteen_products", pid)
    return jsonify({"id": pid}), 201


@ops_bp.post("/canteen/checkout")
@core.require_auth(permissions=["canteen.checkout"])
def canteen_checkout():
    user = core.current_user()
    key = core.idempotency_key()
    prior = core.idempotency_guard(key)
    if prior:
        return jsonify(prior), 200

    data = core.get_json()
    raw_uid = str(data.get("raw_uid", "")).strip()
    student_id = int(data.get("student_id", 0))
    cart = data.get("cart", [])
    if not cart:
        return core.json_error("Keranjang kosong", 400)

    if raw_uid:
        uid_hash = core.hash_rfid_uid(raw_uid)
        card = db.query_one("SELECT * FROM rfid_cards WHERE card_uid_hash=:h", {"h": uid_hash})
        if not card:
            core.flag_security("unknown_card", "medium", "Kartu tidak dikenal dipindai", source_module="canteen")
            return core.json_error("Kartu tidak dikenal", 404)
        if card["status"] != "active":
            return core.json_error(f"Kartu {card['status']}", 403)
        student_id = card["student_id"]
        if not student_id:
            return core.json_error("Kartu belum dipetakan ke siswa", 400)

    if not student_id:
        return core.json_error("Siswa tidak dikenali", 400)

    unit_id = _user_unit(user)
    total = 0
    items = []
    for it in cart:
        pid = int(it.get("product_id", 0))
        qty = int(it.get("qty", 1))
        prod = db.query_one("SELECT * FROM canteen_products WHERE id=:id", {"id": pid})
        if not prod:
            return core.json_error(f"Produk {pid} tidak ada", 400)
        line = prod["selling_price"] * qty
        total += line
        items.append((prod, qty, line))

    if total <= 0:
        return core.json_error("Total tidak valid", 400)

    # daily limit
    today_spent = db.query_one(
            "SELECT COALESCE(SUM(co.total_amount),0) AS t FROM canteen_orders co "
            "WHERE co.student_id=:s AND co.status='paid' AND co.created_at >= date_trunc('day', now())",
        {"s": student_id})["t"]
    limit_row = db.query_one("SELECT daily_limit FROM student_spending_limits WHERE student_id=:s AND active", {"s": student_id})
    daily_limit = limit_row["daily_limit"] if limit_row else 50000
    if today_spent + total > daily_limit:
        core.flag_security("over_daily_limit", "medium", f"Melebihi limit harian (siswa {student_id})", source_module="canteen", source_id=student_id)
        return core.json_error("Melebihi limit harian", 403)

    result = {}
    with db.engine.begin() as conn:
        acc = conn.execute(text(
            "SELECT * FROM financial_accounts WHERE owner_type='student' AND owner_id=:s AND account_type='wallet' FOR UPDATE"),
            {"s": student_id}).first()
        if not acc:
            return core.json_error("Dompet siswa tidak ada", 404)
        if acc.cached_balance < total:
            return core.json_error("Saldo dompet tidak cukup", 400)
        new_bal = acc.cached_balance - total
        conn.execute(text("UPDATE financial_accounts SET cached_balance=:b WHERE id=:id"), {"b": new_bal, "id": acc.id})
        ono = db.gen_reference("CKN")
        oid = conn.execute(text(
            "INSERT INTO canteen_orders (unit_id, order_number, student_id, cashier_user_id, subtotal_amount, total_amount, payment_method, status) "
            "VALUES (:u,:n,:s,:c,:sub,:t,'wallet','paid') RETURNING id"),
            {"u": unit_id, "n": ono, "s": student_id, "c": user["sub"], "sub": total, "t": total}).scalar_one()
        for prod, qty, line in items:
            conn.execute(text(
                "INSERT INTO canteen_order_items (order_id, product_id, product_name, qty, unit_price, total_price) VALUES (:o,:p,:pn,:q,:pr,:t)"),
                {"o": oid, "p": prod["id"], "pn": prod["name"], "q": qty, "pr": prod["selling_price"], "t": line})
            if prod["stock_tracking_enabled"]:
                conn.execute(text("UPDATE canteen_products SET stock_qty=stock_qty-:q WHERE id=:id AND stock_qty>=:q"),
                             {"q": qty, "id": prod["id"]})
        conn.execute(text(
            "INSERT INTO account_ledger (account_id, transaction_type, direction, amount, balance_after, source_type, source_id, description, created_by) "
            "VALUES (:a,'canteen_payment','debit',:amt,:b,'canteen',:o,'Belanja kantin',:u)"),
            {"a": acc.id, "amt": total, "b": new_bal, "o": oid, "u": user["sub"]})
        fid = _foundation(user)
        titip = core.coa_id_by_code("2100", fid)
        rev = core.coa_id_by_code("4100", fid)
        core.post_journal(unit_id, [(titip, total, 0, "Titipan dompet (kantin)"), (rev, 0, total, "Pendapatan kantin")],
                          f"Kantin {ono}", "canteen", oid, user["sub"])
        if raw_uid:
            conn.execute(text(
                "INSERT INTO rfid_card_events (card_id, event_type, user_id, ip_address) "
                "SELECT id,'scanned',:u,:ip FROM rfid_cards WHERE student_id=:s LIMIT 1"),
                {"u": user["sub"], "ip": request.remote_addr, "s": student_id})
        core.audit("canteen.checkout", "canteen_orders", oid, new_value={"total": total, "student_id": student_id})
        result = {"message": "Pembayaran kantin berhasil", "order_id": oid, "total": total, "balance": new_bal}
    core.save_idempotency(key, result)
    return jsonify(result), 201


@ops_bp.get("/canteen/orders")
@core.require_auth(permissions=["canteen.manage"])
def list_orders():
    return jsonify({"items": db.query_all(
        "SELECT co.*, s.full_name AS student_name FROM canteen_orders co LEFT JOIN students s ON s.id=co.student_id ORDER BY co.id DESC LIMIT 100")})


@ops_bp.get("/canteen/spending-limits/<int:student_id>")
@core.require_auth(permissions=["students.view"])
def get_limit(student_id):
    row = db.query_one("SELECT * FROM student_spending_limits WHERE student_id=:s AND active", {"s": student_id})
    return jsonify({"item": row or {"daily_limit": 50000, "weekly_limit": 250000}})


@ops_bp.post("/canteen/spending-limits")
@core.require_auth(permissions=["students.manage"])
def set_limit():
    data = core.get_json()
    student_id = int(data.get("student_id", 0))
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE student_spending_limits SET active=FALSE WHERE student_id=:s"), {"s": student_id})
        conn.execute(text(
            "INSERT INTO student_spending_limits (student_id, daily_limit, weekly_limit, blocked_categories) "
            "VALUES (:s,:d,:w,:b)"),
            {"s": student_id, "d": core.to_bigint(data.get("daily_limit", 50000)),
             "w": core.to_bigint(data.get("weekly_limit", 250000)),
             "b": data.get("blocked_categories", [])})
    return jsonify({"message": "Limit diperbarui"})


# ---------------- inventory ----------------
@ops_bp.get("/inventory/items")
@core.require_auth(permissions=["inventory.manage"])
def list_inventory():
    return jsonify({"items": db.query_all(
        "SELECT i.*, COALESCE((SELECT SUM(qty_on_hand) FROM inventory_stock s WHERE s.item_id=i.id),0) AS qty FROM inventory_items i ORDER BY i.id")})


@ops_bp.post("/inventory/items")
@core.require_auth(permissions=["inventory.manage"])
def create_item():
    data = core.get_json()
    unit_id = _user_unit(core.current_user())
    name = str(data.get("name", "")).strip()
    if not name:
        return core.json_error("Nama wajib", 400)
    with db.engine.begin() as conn:
        iid = conn.execute(text(
            "INSERT INTO inventory_items (unit_id, name, unit_of_measure, minimum_stock) VALUES (:u,:n,:uom,:m) RETURNING id"),
            {"u": unit_id, "n": name, "uom": str(data.get("unit_of_measure", "pcs")), "m": int(data.get("minimum_stock", 0))}).scalar_one()
        core.audit("inventory.item.create", "inventory_items", iid)
    return jsonify({"id": iid}), 201


@ops_bp.post("/inventory/movements")
@core.require_auth(permissions=["inventory.stock", "inventory.manage"], any_of=["inventory.stock", "inventory.manage"])
def stock_movement():
    data = core.get_json()
    item_id = int(data.get("item_id", 0))
    loc_id = int(data.get("location_id", 0))
    qty = int(data.get("qty", 0))
    mtype = str(data.get("movement_type", "purchase"))
    if qty <= 0:
        return core.json_error("Qty harus > 0", 400)
    with db.engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO inventory_movements (item_id, to_location_id, movement_type, qty, unit_cost, created_by, source_type) "
            "VALUES (:i,:l,:t,:q,:c,:u,'manual')"),
            {"i": item_id, "l": loc_id, "t": mtype, "q": qty, "c": core.to_bigint(data.get("unit_cost", 0)), "u": core.current_user()["sub"]})
        conn.execute(text(
            "INSERT INTO inventory_stock (item_id, location_id, qty_on_hand) VALUES (:i,:l,:q) "
            "ON CONFLICT (item_id, location_id) DO UPDATE SET qty_on_hand = inventory_stock.qty_on_hand + :q"),
            {"i": item_id, "l": loc_id, "q": qty if mtype in ("purchase", "transfer_in", "return", "opname") else -qty})
        core.audit("inventory.movement", "inventory_items", item_id, new_value={"qty": qty, "type": mtype})
    return jsonify({"message": "Stok diperbarui"})


# ---------------- assets ----------------
@ops_bp.get("/assets")
@core.require_auth(permissions=["assets.manage"])
def list_assets():
    return jsonify({"items": db.query_all("SELECT * FROM assets ORDER BY id")})


@ops_bp.post("/assets")
@core.require_auth(permissions=["assets.manage"])
def create_asset():
    data = core.get_json()
    unit_id = _user_unit(core.current_user())
    code = str(data.get("asset_code", "")).strip()
    name = str(data.get("name", "")).strip()
    if not code or not name:
        return core.json_error("Kode & nama wajib", 400)
    cost = core.to_bigint(data.get("acquisition_cost", 0))
    with db.engine.begin() as conn:
        aid = conn.execute(text(
            "INSERT INTO assets (unit_id, asset_code, name, acquisition_cost, book_value, location_id, responsible_employee_id) "
            "VALUES (:u,:c,:n,:cost,:cost,:l,:r) RETURNING id"),
            {"u": unit_id, "c": code, "n": name, "cost": cost, "l": int(data.get("location_id", 0)) or None,
             "r": int(data.get("responsible_employee_id", 0)) or None}).scalar_one()
        core.audit("asset.create", "assets", aid)
    return jsonify({"id": aid}), 201


@ops_bp.post("/assets/depreciate")
@core.require_auth(permissions=["assets.depreciate"])
def run_depreciation():
    user = core.current_user()
    now = datetime.now()
    month, year = now.month, now.year
    done = 0
    with db.engine.begin() as conn:
        assets = conn.execute(text(
            "SELECT * FROM assets WHERE status='active' AND depreciation_method='straight_line' AND useful_life_months > 0 AND book_value > 0"),
            ).fetchall()
        for a in assets:
            exists = conn.execute(text(
                "SELECT 1 FROM asset_depreciations WHERE asset_id=:id AND period_month=:m AND period_year=:y"),
                {"id": a.id, "m": month, "y": year}).first()
            if exists:
                continue
            monthly = a.acquisition_cost // a.useful_life_months
            monthly = min(monthly, a.book_value)
            nb = a.book_value - monthly
            conn.execute(text("UPDATE assets SET book_value=:b, accumulated_depreciation=accumulated_depreciation+:d WHERE id=:id"),
                         {"b": nb, "d": monthly, "id": a.id})
            conn.execute(text(
                "INSERT INTO asset_depreciations (asset_id, period_month, period_year, amount) VALUES (:id,:m,:y,:d)"),
                {"id": a.id, "m": month, "y": year, "d": monthly})
            fid = _foundation(user)
            beban = core.coa_id_by_code("5300", fid)
            akum = core.coa_id_by_code("1510", fid)
            core.post_journal(a.unit_id, [(beban, monthly, 0, "Beban penyusutan"), (akum, 0, monthly, "Akumulasi penyusutan")],
                              f"Penyusutan {a.asset_code}", "depreciation", a.id, user["sub"])
            done += 1
    return jsonify({"message": f"{done} aset disusutkan", "done": done})


# ---------------- helpers ----------------
def _user_unit(user):
    allowed = core.unit_ids_for(user)
    if allowed:
        return next(iter(allowed))
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT allowed_units[1] FROM users WHERE id=:id"), {"id": user["sub"]}).first()
        if row and row[0]:
            return row[0]
        return conn.execute(text("SELECT id FROM school_units ORDER BY id LIMIT 1")).scalar_one()


def _foundation(user):
    with db.engine.connect() as conn:
        return conn.execute(text("SELECT foundation_id FROM users WHERE id=:id"), {"id": user["sub"]}).scalar_one()
