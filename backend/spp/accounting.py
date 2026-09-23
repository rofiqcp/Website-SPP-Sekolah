"""Accounting: COA, periods, journals, neraca (balance sheet), RAB, reports."""
from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from . import db, core

accounting_bp = Blueprint("accounting", __name__, url_prefix="/api")


@accounting_bp.get("/coa")
@core.require_auth(permissions=["accounting.view"])
def list_coa():
    fid = _foundation(core.current_user())
    return jsonify({"items": db.query_all("SELECT * FROM chart_of_accounts WHERE foundation_id=:f ORDER BY code", {"f": fid})})


@accounting_bp.get("/journals")
@core.require_auth(permissions=["accounting.view"])
def list_journals():
    return jsonify({"items": db.query_all(
        "SELECT j.*, (SELECT SUM(debit) FROM journal_lines l WHERE l.journal_id=j.id) AS total "
        "FROM journal_entries j ORDER BY j.id DESC LIMIT 200")})


@accounting_bp.get("/neraca")
@core.require_auth(permissions=["accounting.view"])
def neraca():
    fid = _foundation(core.current_user())
    as_of = str(request.args.get("as_of", "")) or None
    # balances per account from journal_lines up to as_of
    sql = (
        "SELECT a.id, a.code, a.name, a.account_type, a.normal_balance, "
        "COALESCE(SUM(l.debit),0) - COALESCE(SUM(l.credit),0) AS net "
        "FROM journal_lines l JOIN chart_of_accounts a ON a.id=l.account_id "
        "JOIN journal_entries j ON j.id=l.journal_id "
        "WHERE a.foundation_id=:f" + (" AND j.journal_date <= :asof" if as_of else "") +
        " GROUP BY a.id, a.code, a.name, a.account_type, a.normal_balance ORDER BY a.code"
    )
    rows = db.query_all(sql, {"f": fid, "asof": as_of} if as_of else {"f": fid})
    # normal balance sign
    def balance(r):
        sign = 1 if r["normal_balance"] == "debit" else -1
        return sign * r["net"]
    assets = sum(r["net"] for r in rows if r["account_type"] == "asset" and r["normal_balance"] == "debit") - \
             sum(r["net"] for r in rows if r["account_type"] == "asset" and r["normal_balance"] == "credit")
    liabilities = sum(r["net"] for r in rows if r["account_type"] == "liability" and r["normal_balance"] == "credit") - \
                  sum(r["net"] for r in rows if r["account_type"] == "liability" and r["normal_balance"] == "debit")
    equity = sum(r["net"] for r in rows if r["account_type"] == "equity" and r["normal_balance"] == "credit") - \
             sum(r["net"] for r in rows if r["account_type"] == "equity" and r["normal_balance"] == "debit")
    balanced = (assets - (liabilities + equity)) == 0
    return jsonify({
        "as_of": as_of or "sekarang",
        "accounts": [{"code": r["code"], "name": r["name"], "type": r["account_type"],
                      "balance": (r["net"] if r["normal_balance"] == "debit" else -r["net"])} for r in rows],
        "totals": {"assets": assets, "liabilities": liabilities, "equity": equity},
        "balanced": balanced,
    })


@accounting_bp.get("/reports/cashflow")
@core.require_auth(permissions=["reports.view"])
def cashflow():
    fid = _foundation(core.current_user())
    rows = db.query_all(
        "SELECT DATE(j.journal_date) AS d, "
        "COALESCE(SUM(CASE WHEN a.is_cash_account AND l.debit>0 THEN l.debit END),0) AS inflow, "
        "COALESCE(SUM(CASE WHEN a.is_cash_account AND l.credit>0 THEN l.credit END),0) AS outflow "
        "FROM journal_lines l JOIN journal_entries j ON j.id=l.journal_id "
        "JOIN chart_of_accounts a ON a.id=l.account_id "
        "WHERE a.foundation_id=:f GROUP BY DATE(j.journal_date) ORDER BY d DESC LIMIT 60", {"f": fid})
    return jsonify({"items": rows})


@accounting_bp.get("/reports/receivables")
@core.require_auth(permissions=["reports.view"])
def receivables():
    rows = db.query_all(
        "SELECT s.full_name, s.nis, c.name AS class_name, i.period_month, i.period_year, "
        "i.total_amount, i.paid_amount, i.outstanding_amount, i.status "
        "FROM invoices i JOIN students s ON s.id=i.student_id LEFT JOIN classes c ON c.id=s.class_id "
        "WHERE i.outstanding_amount > 0 ORDER BY i.outstanding_amount DESC")
    total = sum(r["outstanding_amount"] for r in rows)
    return jsonify({"items": rows, "total_outstanding": total, "count": len(rows)})


@accounting_bp.get("/reports/summary")
@core.require_auth(permissions=["reports.view"])
def summary():
    bills = db.query_all("SELECT COALESCE(SUM(total_amount),0) AS t, COALESCE(SUM(paid_amount),0) AS p FROM invoices")
    wallet = db.query_all("SELECT COALESCE(SUM(cached_balance),0) AS b FROM financial_accounts WHERE account_type='wallet'")
    savings = db.query_all("SELECT COALESCE(SUM(cached_balance),0) AS b FROM financial_accounts WHERE account_type='savings'")
    students = db.query_all("SELECT COUNT(*) AS c FROM students WHERE enrollment_status='active'")
    return jsonify({
        "tagihan_total": bills[0]["t"], "tagihan_terbayar": bills[0]["p"],
        "piutang": bills[0]["t"] - bills[0]["p"],
        "saldo_dompet": wallet[0]["b"], "saldo_tabungan": savings[0]["b"],
        "siswa_aktif": students[0]["c"],
    })


# ---------------- RAB ----------------
@accounting_bp.get("/budgets")
@core.require_auth(permissions=["budget.manage", "budget.approve", "reports.view"], any_of=["budget.manage", "budget.approve", "reports.view"])
def list_budgets():
    return jsonify({"items": db.query_all(
        "SELECT b.*, (SELECT COALESCE(SUM(realized_amount),0) FROM budget_lines bl WHERE bl.budget_id=b.id) AS realized, "
        "(SELECT COALESCE(SUM(amount),0) FROM budget_lines bl WHERE bl.budget_id=b.id) AS planned "
        "FROM budgets b ORDER BY b.id DESC LIMIT 50")})


@accounting_bp.post("/budgets")
@core.require_auth(permissions=["budget.manage"])
def create_budget():
    data = core.get_json()
    unit_id = _user_unit(core.current_user())
    name = str(data.get("name", "")).strip()
    if not name:
        return core.json_error("Nama RAB wajib", 400)
    with db.engine.begin() as conn:
        bid = conn.execute(text(
            "INSERT INTO budgets (unit_id, academic_year_id, name, period_start, period_end, status, submitted_by) "
            "VALUES (:u,(SELECT id FROM academic_years WHERE is_active=TRUE LIMIT 1),:n,:ps,:pe,'draft',:sb) RETURNING id"),
            {"u": unit_id, "n": name, "ps": data.get("period_start"), "pe": data.get("period_end"),
             "sb": core.current_user()["sub"]}).scalar_one()
        for line in data.get("lines", []):
            planned = core.to_bigint(line.get("planned_amount", 0))
            conn.execute(text(
                "INSERT INTO budget_lines (budget_id, amount, realized_amount) "
                "VALUES (:b,:p,0)"), {"b": bid, "p": planned})
        core.audit("budget.create", "budgets", bid)
    return jsonify({"id": bid}), 201


@accounting_bp.post("/budgets/<uuid:budget_id>/approve")
@core.require_auth(permissions=["budget.approve"])
def approve_budget(budget_id):
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE budgets SET status='approved', approved_by=:u, approved_at=now() WHERE id=:id"),
                     {"u": core.current_user()["sub"], "id": budget_id})
        core.audit("budget.approve", "budgets", budget_id)
    return jsonify({"message": "RAB disetujui"})


# ---------------- expenses ----------------
@accounting_bp.get("/expenses")
@core.require_auth(permissions=["budget.manage", "reports.view"], any_of=["budget.manage", "reports.view"])
def list_expenses():
    return jsonify({"items": db.query_all(
        "SELECT e.*, u.name AS requester_name FROM expense_requests e "
        "JOIN users u ON u.id=e.requester_id ORDER BY e.created_at DESC LIMIT 100")})


@accounting_bp.post("/expenses")
@core.require_auth(permissions=["budget.manage"])
def create_expense():
    user = core.current_user()
    data = core.get_json()
    unit_id = _user_unit(user)
    amount = core.to_bigint(data.get("amount", 0))
    if amount <= 0:
        return core.json_error("Nominal harus > 0", 400)
    desc = str(data.get("description", "")).strip()
    account_id = data.get("account_id")  # COA account for expense
    with db.engine.begin() as conn:
        rno = db.gen_reference("EXP")
        eid = conn.execute(text(
            "INSERT INTO expense_requests (unit_id, request_number, requester_id, account_id, amount, description, status) "
            "VALUES (:u,:rno,:uid,:acc,:amt,:d,'draft') RETURNING id"),
            {"u": unit_id, "rno": rno, "uid": user["sub"],
             "acc": account_id, "amt": amount, "d": desc}).scalar_one()
        core.audit("expense.create", "expense_requests", eid, new_value={"amount": amount})
    return jsonify({"id": str(eid), "request_number": rno}), 201


@accounting_bp.patch("/expenses/<uuid:expense_id>/approve")
@core.require_auth(permissions=["approvals.decide"])
def approve_expense(expense_id):
    user = core.current_user()
    data = core.get_json()
    action = str(data.get("action", "approve")).strip().lower()
    if action not in ("approve", "reject"):
        return core.json_error("action harus approve atau reject", 400)
    with db.engine.begin() as conn:
        exp = conn.execute(text("SELECT * FROM expense_requests WHERE id=:id FOR UPDATE"), {"id": expense_id}).first()
        if not exp:
            return core.json_error("Expense tidak ditemukan", 404)
        if exp.status not in ("draft", "waiting_verification"):
            return core.json_error(f"Status {exp.status} tidak bisa di-approve", 400)
        if action == "reject":
            conn.execute(text("UPDATE expense_requests SET status='rejected', updated_at=now() WHERE id=:id"), {"id": expense_id})
            core.audit("expense.reject", "expense_requests", expense_id)
            return jsonify({"message": "Expense ditolak"})
        # approve: advance approval level
        new_level = exp.current_approval_level + 1
        new_status = "approved" if new_level >= 2 else "waiting_verification"  # ponytail: 2-level approval hardcoded; config when multi-level
        conn.execute(text(
            "UPDATE expense_requests SET status=:s, current_approval_level=:l, updated_at=now() WHERE id=:id"),
            {"s": new_status, "l": new_level, "id": expense_id})
        core.audit("expense.approve", "expense_requests", expense_id, new_value={"level": new_level, "status": new_status})
    return jsonify({"message": "Expense " + ("disetujui" if new_status == "approved" else "verifikasi level " + str(new_level)),
                     "status": new_status, "approval_level": new_level})


@accounting_bp.post("/expenses/<uuid:expense_id>/pay")
@core.require_auth(permissions=["payments.create"])
def pay_expense(expense_id):
    user = core.current_user()
    data = core.get_json()
    method = str(data.get("method", "Tunai"))[:20]
    with db.engine.begin() as conn:
        exp = conn.execute(text("SELECT * FROM expense_requests WHERE id=:id FOR UPDATE"), {"id": expense_id}).first()
        if not exp:
            return core.json_error("Expense tidak ditemukan", 404)
        if exp.status != "approved":
            return core.json_error("Expense belum disetujui", 400)
        fid = _foundation(user)
        # Resolve COA account: use expense account_id if set, else fallback to Beban Operasional 5100
        expense_acc = exp.account_id if exp.account_id else core.coa_id_by_code("5100", fid)
        if not expense_acc:
            return core.json_error("COA beban tidak ditemukan. Buat COA 5100 (Beban Operasional) atau pilih akun di expense.", 400)
        cash_acc = core.coa_id_by_code("1000", fid) if method == "Tunai" else core.coa_id_by_code("1010", fid)
        jid = core.post_journal(exp.unit_id, [
            (expense_acc, exp.amount, 0, f"Beban {exp.description or exp.request_number}"),
            (cash_acc, 0, exp.amount, f"Kas {method} untuk {exp.request_number}"),
        ], f"Pembayaran expense {exp.request_number}", "expense_payment", expense_id, user["sub"])
        conn.execute(text("UPDATE expense_requests SET status='paid', updated_at=now() WHERE id=:id"), {"id": expense_id})
        core.audit("expense.pay", "expense_requests", expense_id, new_value={"amount": exp.amount, "method": method, "journal_id": str(jid)})
    return jsonify({"message": "Expense dibayar", "journal_id": str(jid)})


def _foundation(user):
    with db.engine.connect() as conn:
        row = conn.execute(text("SELECT foundation_id FROM users WHERE id=:id LIMIT 1"), {"id": user["sub"]}).first()
    return row[0] if row else None


def _user_unit(user):
    allowed = core.unit_ids_for(user)
    if allowed:
        return next(iter(allowed))
    with db.engine.connect() as conn:
        return conn.execute(text("SELECT id FROM school_units ORDER BY id LIMIT 1")).scalar_one()
