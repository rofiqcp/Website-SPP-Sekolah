"""Database engine, seed helpers, query helpers.

Schema managed via Alembic migrations (see backend/migrations/).
All primary keys are UUID, monetary columns BIGINT, metadata JSONB.
Row Level Security enforced on unit-scoped tables.
"""

import os
import secrets
import calendar
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2:///spp_sekolah")
APP_ENV = os.getenv("APP_ENV", "production")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True, pool_size=10, max_overflow=20)


def now_utc():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Seed data — idempotent, works with UUID primary keys
# ---------------------------------------------------------------------------

def init_db():
    """Run all seed functions. Schema must already exist from migrations."""
    with engine.begin() as conn:
        seed_foundation(conn)
        seed_permissions(conn)
        seed_roles(conn)
        seed_role_permissions(conn)
        seed_coa(conn)
        seed_demo_users(conn)
        seed_demo_data(conn)


def _fid(conn):
    return conn.execute(text("SELECT id FROM foundations ORDER BY id LIMIT 1")).scalar_one()


def _units(conn):
    return {r[0]: r[1] for r in conn.execute(
        text("SELECT code, id FROM school_units WHERE foundation_id=(SELECT id FROM foundations ORDER BY id LIMIT 1)")).all()}


def seed_foundation(conn):
    if conn.execute(text("SELECT 1 FROM foundations LIMIT 1")).first():
        return
    conn.execute(text("""
        INSERT INTO foundations (name, legal_name, address, phone, email, tax_number)
        VALUES (:name, :legal, :addr, :phone, :email, :tax)
    """), {
        "name": "Yayasan Pendidikan El Yaomy Klaten",
        "legal": "Yayasan Pendidikan El Yaomy Klaten",
        "addr": "Batur Baru, Tegalrejo, Ceper, Klaten, Jawa Tengah 57465",
        "phone": "0272-555578",
        "email": "sdim.elyaomy@gmail.com",
        "tax": "00.000.000.0-000.000"
    })
    fid = _fid(conn)
    for code, name, level in [
        ("TK", "Taman Kanak-Kanak El Yaomy", "TK"),
        ("SD", "Sekolah Dasar Islam Mandiri", "SD"),
        ("SMP", "SMP El Yaomy", "SMP"),
        ("SMA", "SMA El Yaomy", "SMA"),
    ]:
        conn.execute(
            text("INSERT INTO school_units (foundation_id, code, name, level) VALUES (:f, :c, :n, :l)"),
            {"f": fid, "c": code, "n": name, "l": level})
    conn.execute(
        text("INSERT INTO academic_years (foundation_id, name, start_date, end_date, is_active) "
             "VALUES (:f, '2026/2027', DATE '2026-07-01', DATE '2027-06-30', TRUE)"),
        {"f": fid})


def seed_permissions(conn):
    perms = [
        ("dashboard.view", "Lihat dashboard"),
        ("students.view", "Lihat siswa"), ("students.manage", "Kelola siswa"),
        ("classes.manage", "Kelola kelas"), ("employees.manage", "Kelola pegawai"),
        ("units.manage", "Kelola unit sekolah"),
        ("billing.manage", "Kelola tagihan & aturan"), ("billing.generate", "Generate tagihan"),
        ("payments.create", "Buat pembayaran"), ("payments.refund", "Refund pembayaran"),
        ("wallet.topup", "Top up dompet/tabungan"), ("wallet.debit", "Potong saldo"),
        ("wallet.adjust", "Koreksi saldo manual"),
        ("cashier.open", "Buka shift kasir"), ("cashier.pay", "Terima bayar kasir"),
        ("canteen.manage", "Kelola menu kantin"), ("canteen.checkout", "Checkout kantin"),
        ("inventory.manage", "Kelola inventaris"), ("inventory.stock", "Stok inventaris"),
        ("assets.manage", "Kelola aset"), ("assets.depreciate", "Penyusutan aset"),
        ("accounting.journal", "Buat jurnal"), ("accounting.view", "Lihat akuntansi"),
        ("accounting.close", "Tutup periode"),
        ("budget.manage", "Kelola RAB"), ("budget.approve", "Setujui RAB"),
        ("reports.view", "Lihat laporan"),
        ("rfid.issue", "Terbitkan kartu"), ("rfid.block", "Blokir kartu"), ("rfid.manage", "Kelola RFID"),
        ("users.manage", "Kelola user"), ("roles.manage", "Kelola role"),
        ("audit.view", "Lihat audit log"), ("approvals.decide", "Putuskan approval"),
        ("mfa.manage", "Kelola MFA"),
    ]
    for code, desc in perms:
        conn.execute(
            text("INSERT INTO permissions (code, description) VALUES (:c, :d) ON CONFLICT (code) DO NOTHING"),
            {"c": code, "d": desc})


def _perm_id(conn, code):
    return conn.execute(text("SELECT id FROM permissions WHERE code=:c LIMIT 1"), {"c": code}).scalar_one()


def seed_roles(conn):
    fid = _fid(conn)
    if conn.execute(text("SELECT 1 FROM roles WHERE foundation_id=:f LIMIT 1"), {"f": fid}).first():
        return
    role_defs = [
        ("super_admin", "Super Admin Yayasan"),
        ("admin_unit", "Admin Unit Sekolah"),
        ("bendahara", "Bendahara"),
        ("kasir", "Kasir Sekolah"),
        ("kepala_sekolah", "Kepala Sekolah"),
        ("wali_kelas", "Wali Kelas"),
        ("guru", "Guru/Pegawai"),
        ("siswa", "Siswa"),
        ("orang_tua", "Orang Tua/Wali"),
        ("auditor", "Auditor"),
        ("petugas_kantin", "Petugas Kantin"),
        ("petugas_gudang", "Petugas Gudang/Aset"),
    ]
    for code, name in role_defs:
        conn.execute(
            text("INSERT INTO roles (foundation_id, code, name) VALUES (:f, :c, :n) ON CONFLICT DO NOTHING"),
            {"f": fid, "c": code, "n": name})


def _role_id(conn, code):
    return conn.execute(text("SELECT id FROM roles WHERE code=:c LIMIT 1"), {"c": code}).scalar_one()


def seed_role_permissions(conn):
    fid = _fid(conn)
    existing = conn.execute(
        text("SELECT 1 FROM role_permissions rp JOIN roles r ON r.id=rp.role_id WHERE r.foundation_id=:f LIMIT 1"),
        {"f": fid}).first()
    if existing:
        return

    all_perms = [r[0] for r in conn.execute(text("SELECT code FROM permissions")).all()]
    role_map = {
        "super_admin": all_perms,
        "admin_unit": [p for p in all_perms if p not in ("approvals.decide", "roles.manage")],
        "bendahara": ["dashboard.view", "students.view", "billing.manage", "billing.generate",
                       "payments.create", "payments.refund", "wallet.topup", "wallet.debit", "wallet.adjust",
                       "cashier.open", "cashier.pay", "canteen.manage", "canteen.checkout",
                       "inventory.manage", "inventory.stock", "assets.manage", "assets.depreciate",
                       "accounting.journal", "accounting.view", "accounting.close",
                       "budget.manage", "budget.approve", "reports.view",
                       "rfid.block", "rfid.manage", "users.manage", "approvals.decide",
                       "audit.view", "mfa.manage"],
        "kepala_sekolah": ["dashboard.view", "students.view", "reports.view", "budget.approve",
                           "approvals.decide", "accounting.view", "audit.view"],
        "kasir": ["dashboard.view", "students.view", "payments.create", "wallet.topup", "wallet.debit",
                   "cashier.open", "cashier.pay", "canteen.checkout", "inventory.stock"],
        "petugas_kantin": ["dashboard.view", "canteen.checkout"],
        "petugas_gudang": ["dashboard.view", "inventory.manage", "inventory.stock", "assets.manage"],
        "wali_kelas": ["dashboard.view", "students.view", "wallet.topup", "reports.view"],
        "guru": ["dashboard.view", "students.view", "wallet.topup", "reports.view"],
        "siswa": ["dashboard.view", "wallet.debit"],
        "orang_tua": ["dashboard.view", "payments.create", "wallet.debit", "reports.view"],
        "auditor": ["dashboard.view", "students.view", "reports.view", "accounting.view", "audit.view"],
    }
    for role_code, perm_codes in role_map.items():
        rid = _role_id(conn, role_code)
        for code in perm_codes:
            pid = _perm_id(conn, code)
            conn.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p) ON CONFLICT DO NOTHING"),
                {"r": rid, "p": pid})


def seed_coa(conn):
    fid = _fid(conn)
    if conn.execute(text("SELECT 1 FROM chart_of_accounts WHERE foundation_id=:f LIMIT 1"), {"f": fid}).first():
        return
    rows = [
        ("1000", "Kas Sekolah", "asset", "debit", True),
        ("1010", "Bank Sekolah", "asset", "debit", True),
        ("1020", "Kas Kantin", "asset", "debit", True),
        ("1100", "Piutang SPP Siswa", "asset", "debit", False),
        ("1200", "Persediaan Kantin", "asset", "debit", False),
        ("1500", "Aset Tetap", "asset", "debit", False),
        ("1510", "Akumulasi Penyusutan", "asset", "credit", False),
        ("2000", "Utang Vendor", "liability", "credit", False),
        ("2100", "Titipan Saldo Dompet Siswa", "liability", "credit", False),
        ("2200", "Pendapatan Diterima Dimuka", "liability", "credit", False),
        ("3000", "Dana Yayasan", "equity", "credit", False),
        ("4000", "Pendapatan SPP", "revenue", "credit", False),
        ("4100", "Pendapatan Kantin", "revenue", "credit", False),
        ("4200", "Pendapatan Lain-lain", "revenue", "credit", False),
        ("5000", "Beban Gaji & Honor", "expense", "debit", False),
        ("5100", "Beban Operasional", "expense", "debit", False),
        ("5200", "HPP Kantin", "expense", "debit", False),
        ("5300", "Beban Penyusutan", "expense", "debit", False),
    ]
    for code, name, atype, bal, cash in rows:
        conn.execute(
            text("INSERT INTO chart_of_accounts (foundation_id, code, name, account_type, normal_balance, is_cash_account) "
                 "VALUES (:f, :code, :name, :t, :b, :c) ON CONFLICT (foundation_id, code) DO NOTHING"),
            {"f": fid, "code": code, "name": name, "t": atype, "b": bal, "c": cash})


DEMO_USERS = [
    ("Super Admin", os.getenv("ADMIN_EMAIL", "admin@elyaomy.sch.id"), os.getenv("ADMIN_PASSWORD", "admin123"), "super_admin"),
    ("Bendahara", "bendahara@elyaomy.sch.id", "admin123", "bendahara"),
    ("Kepala Sekolah", "kepsek@elyaomy.sch.id", "admin123", "kepala_sekolah"),
    ("Kasir", "kasir@elyaomy.sch.id", "admin123", "kasir"),
    ("Petugas Kantin", "kantin@elyaomy.sch.id", "admin123", "petugas_kantin"),
    ("Wali Kelas", "wali@elyaomy.sch.id", "admin123", "wali_kelas"),
    ("Guru", "guru@elyaomy.sch.id", "admin123", "guru"),
    ("Siswa Demo", "siswa@elyaomy.sch.id", "admin123", "siswa"),
    ("Orang Tua", "ortu@elyaomy.sch.id", "admin123", "orang_tua"),
    ("Auditor", "auditor@elyaomy.sch.id", "admin123", "auditor"),
]


def seed_demo_users(conn):
    fid = _fid(conn)
    first_unit = conn.execute(text("SELECT id FROM school_units WHERE foundation_id=:f ORDER BY id LIMIT 1"), {"f": fid}).scalar_one()
    first_class = conn.execute(text("SELECT id FROM classes ORDER BY id LIMIT 1")).first()
    class_id = first_class[0] if first_class else first_unit  # fallback: use unit_id as dummy
    for name, email, password, role_code in DEMO_USERS:
        conn.execute(
            text("INSERT INTO users (foundation_id, name, email, password_hash, status) "
                 "VALUES (:f, :n, :e, :h, 'active') ON CONFLICT (email) DO NOTHING"),
            {"f": fid, "n": name, "e": email, "h": generate_password_hash(password)})
        uid = conn.execute(text("SELECT id FROM users WHERE email=:e"), {"e": email}).scalar_one()
        role_id = _role_id(conn, role_code)
        conn.execute(
            text("INSERT INTO user_roles (user_id, role_id, unit_id, class_id) VALUES (:u, :r, :unit, :cls) ON CONFLICT DO NOTHING"),
            {"u": uid, "r": role_id, "unit": first_unit, "cls": class_id})


def seed_demo_data(conn):
    if conn.execute(text("SELECT 1 FROM students LIMIT 1")).first():
        return
    fid = _fid(conn)
    units = _units(conn)
    ay = conn.execute(
        text("SELECT id FROM academic_years WHERE is_active=TRUE AND foundation_id=:f LIMIT 1"),
        {"f": fid}).scalar_one()

    # Classes
    class_data = [("1A", 250000, "SD"), ("2B", 275000, "SD"), ("3C", 300000, "SD")]
    class_ids = {}
    for name, spp, lvl in class_data:
        cid = conn.execute(
            text("INSERT INTO classes (unit_id, academic_year_id, name, grade_level, monthly_spp) "
                 "VALUES (:u, :ay, :n, :g, :s) RETURNING id"),
            {"u": units[lvl], "ay": ay, "n": name, "g": name[0], "s": spp}).scalar_one()
        class_ids[name] = cid

    # Students
    students = [
        ("2401001", "Aisyah Putri", "1A", "Siti Aminah", "0812340001", 85000, 450000),
        ("2401002", "Raka Pratama", "1A", "Budi Santoso", "0812340002", 40000, 125000),
        ("2302007", "Nabila Zahra", "2B", "Dewi Lestari", "0812340003", 120000, 300000),
        ("2203018", "Kevin Saputra", "3C", "Rina Marlina", "0812340004", 75000, 75000),
    ]
    student_ids = {}
    for nis, name, cls, guardian, phone, wallet, savings in students:
        sid = conn.execute(
            text("INSERT INTO students (unit_id, class_id, nis, full_name, guardian_name, guardian_phone, enrollment_status) "
                 "VALUES (:u, :c, :nis, :n, :g, :p, 'active') RETURNING id"),
            {"u": units["SD"], "c": class_ids[cls], "nis": nis, "n": name, "g": guardian, "p": phone}).scalar_one()
        student_ids[nis] = sid

        # Wallet + financial account
        wid = conn.execute(
            text("INSERT INTO wallets (unit_id, owner_type, owner_id, wallet_number, cached_balance, daily_spending_limit) "
                 "VALUES (:u, 'student', :o, :wn, :b, 50000) RETURNING id"),
            {"u": units["SD"], "o": sid, "wn": f"WAL-{nis}", "b": wallet}).scalar_one()
        conn.execute(
            text("INSERT INTO wallet_transactions (unit_id, wallet_id, transaction_number, amount, transaction_type, status) "
                 "VALUES (:u, :w, :tn, :a, 'initial', 'success')"),
            {"u": units["SD"], "w": wid, "tn": f"TXN-INIT-{nis}", "a": wallet})
        conn.execute(
            text("INSERT INTO wallet_ledger (wallet_id, transaction_id, direction, transaction_type, amount, balance_before, balance_after) "
                 "SELECT :w, id, 'credit', 'initial', :a, 0, :a FROM wallet_transactions WHERE wallet_id=:w ORDER BY created_at LIMIT 1"),
            {"w": wid, "a": wallet})

    # Billing types + rules
    bt_spp = conn.execute(
        text("INSERT INTO billing_types (foundation_id, code, name, is_recurring) "
             "VALUES (:f, 'SPP', 'SPP Bulanan', TRUE) RETURNING id"),
        {"f": fid}).scalar_one()
    for name, cid, spp in [("1A", class_ids["1A"], 250000), ("2B", class_ids["2B"], 275000), ("3C", class_ids["3C"], 300000)]:
        conn.execute(
            text("INSERT INTO billing_rules (unit_id, billing_type_id, academic_year_id, class_id, amount, recurrence, due_day) "
                 "VALUES (:u, :bt, :ay, :c, :s, 'monthly', 10)"),
            {"u": units["SD"], "bt": bt_spp, "ay": ay, "c": cid, "s": spp})

    # Invoices for current month
    today = date.today()
    for nis, amount, paid, status in [
        ("2401001", 250000, 250000, "paid"),
        ("2401002", 250000, 100000, "partial"),
        ("2302007", 275000, 0, "published"),
        ("2203018", 300000, 0, "published"),
    ]:
        inv_no = f"INV-{nis}-{today.year}{today.month:02d}"
        outstanding = amount - paid
        iid = conn.execute(
            text("INSERT INTO invoices (unit_id, student_id, invoice_number, academic_year_id, period_month, period_year, "
                 "subtotal_amount, total_amount, paid_amount, outstanding_amount, status, due_date) "
                 "VALUES (:u, :s, :no, :ay, :m, :y, :a, :a, :p, :o, :st, :d) RETURNING id"),
            {"u": units["SD"], "s": student_ids[nis], "no": inv_no, "ay": ay,
             "m": today.month, "y": today.year, "a": amount, "p": paid, "o": outstanding,
             "st": status, "d": f"{today.year}-{today.month:02d}-10"}).scalar_one()
        conn.execute(
            text("INSERT INTO invoice_items (invoice_id, billing_type_id, description, amount, net_amount, paid_amount, status) "
                 "VALUES (:i, :bt, 'SPP', :a, :a, :p, 'unpaid')"),
            {"i": iid, "bt": bt_spp, "a": amount, "p": paid})

    # Canteen products
    for name, price, stock in [("Nasi Ayam", 15000, 42), ("Es Teh", 3000, 80), ("Roti Coklat", 5000, 35)]:
        conn.execute(
            text("INSERT INTO canteen_products (unit_id, name, selling_price, cost_price, stock_qty) "
                 "VALUES (:u, :n, :p, :c, :s)"),
            {"u": units["SD"], "n": name, "p": price, "c": int(price * 0.6), "s": stock})

    # Budget
    bid = conn.execute(
        text("INSERT INTO budgets (unit_id, academic_year_id, name, period_start, period_end, status) "
             "VALUES (:u, :ay, 'RAB 2026/2027', DATE '2026-07-01', DATE '2027-06-30', 'approved') RETURNING id"),
        {"u": units["SD"], "ay": ay}).scalar_one()
    for cat, planned in [("Gaji Guru", 45000000), ("Operasional", 18000000),
                         ("Sarana Prasarana", 25000000), ("Kegiatan Siswa", 12000000)]:
        conn.execute(
            text("INSERT INTO budget_lines (budget_id, amount, realized_amount) VALUES (:b, :p, 0)"),
            {"b": bid, "p": planned})


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def rowdict(row):
    if row is None:
        return None
    data = dict(row._mapping)
    for key, value in data.items():
        if isinstance(value, Decimal):
            data[key] = float(value)
        elif isinstance(value, (datetime, date)):
            data[key] = value.isoformat()
    return data


def query_all(sql, params=None):
    with engine.connect() as conn:
        return [rowdict(r) for r in conn.execute(text(sql), params or {})]


def query_one(sql, params=None):
    with engine.connect() as conn:
        row = conn.execute(text(sql), params or {}).first()
        return rowdict(row)


def gen_reference(prefix):
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4).upper()}"


def to_bigint(value):
    """Convert rupiah input (number/string) to integer rupiah. Reject negatives."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Nominal tidak valid")
    if d != d.to_integral_value():
        d = d.quantize(Decimal("1"))
    ival = int(d)
    if ival < 0:
        raise ValueError("Nominal tidak boleh negatif")
    return ival
