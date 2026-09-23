#!/usr/bin/env python3
"""Seed spp_sekolah with minimal demo data - idempotent."""
import os

from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash

engine = create_engine('postgresql+psycopg2:///spp_sekolah', pool_pre_ping=True, future=True)

DEMO_ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD")
if not DEMO_ADMIN_PASSWORD:
    raise SystemExit("DEMO_ADMIN_PASSWORD wajib di-set sebelum menjalankan seed_demo.py")


def scalar(sql, params=None):
    """Read scalar value."""
    with engine.connect() as c:
        r = c.execute(text(sql), params or {})
        row = r.first()
        return row[0] if row else None


def exec(sql, params=None):
    """Execute write statement (auto-commit)."""
    with engine.begin() as c:
        c.execute(text(sql), params or {})


def exec_returning(sql, params=None):
    """Execute write statement, return first column of first row."""
    with engine.begin() as c:
        r = c.execute(text(sql), params or {})
        row = r.first()
        return row[0] if row else None


# Foundation
fid = scalar("SELECT id FROM foundations WHERE email='admin@elyaomy.sch.id'")
if not fid:
    fid = exec_returning("INSERT INTO foundations (id, name, legal_name, address, phone, email, status) VALUES (gen_random_uuid(), 'Yayasan Pendidikan El Yaomy Klaten', 'Yayasan Pendidikan El Yaomy Klaten', 'Klaten', '0272-123456', 'admin@elyaomy.sch.id', 'active') RETURNING id")
print(f'Foundation: {fid}')

# Unit
uid = scalar("SELECT id FROM school_units WHERE code='SD-EL-01'")
if not uid:
    uid = exec_returning("INSERT INTO school_units (id, foundation_id, code, name, level, address, status) VALUES (gen_random_uuid(), :f, 'SD-EL-01', 'SD El Yaomy 01', 'SD', 'Klaten', 'active') RETURNING id", {'f': fid})
print(f'Unit: {uid}')

# Academic year
ay = scalar("SELECT id FROM academic_years WHERE is_active=TRUE LIMIT 1")
if not ay:
    ay = exec_returning("INSERT INTO academic_years (id, foundation_id, name, start_date, end_date, is_active) VALUES (gen_random_uuid(), :f, '2025/2026', '2025-07-01', '2026-06-30', true) RETURNING id", {'f': fid})
print(f'AY: {ay}')

# Role
rid = scalar("SELECT id FROM roles WHERE code='super_admin' AND foundation_id=:f", {'f': fid})
if not rid:
    rid = exec_returning("INSERT INTO roles (id, foundation_id, code, name, description) VALUES (gen_random_uuid(), :f, 'super_admin', 'Super Admin', 'Full access') RETURNING id", {'f': fid})

perms = [
    'dashboard.view','students.view','billing.manage','billing.generate','payments.create','payments.refund',
    'wallet.topup','wallet.debit','canteen.manage','canteen.checkout','cashier.open','cashier.pay',
    'cashier.close','rfid.manage','rfid.issue','rfid.block','accounting.view','reports.view',
    'budget.manage','budget.approve','inventory.manage','assets.manage','audit.view','approvals.decide',
    'users.manage','mfa.manage',
]
for code in perms:
    pid = scalar("SELECT id FROM permissions WHERE code=:c", {'c': code})
    if not pid:
        pid = exec_returning("INSERT INTO permissions (id, code, description) VALUES (gen_random_uuid(), :c, :d) RETURNING id", {'c': code, 'd': code})
    exists = scalar("SELECT 1 FROM role_permissions WHERE role_id=:r AND permission_id=:p", {'r': rid, 'p': pid})
    if not exists:
        exec("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)", {'r': rid, 'p': pid})

# Admin user
uid_u = scalar("SELECT id FROM users WHERE email='admin@elyaomy.sch.id'")
if not uid_u:
    pw = generate_password_hash(DEMO_ADMIN_PASSWORD, method='scrypt')
    uid_u = exec_returning("INSERT INTO users (id, foundation_id, email, phone, password_hash, status, failed_login_count) VALUES (gen_random_uuid(), :f, 'admin@elyaomy.sch.id', '087832900005', :pw, 'active', 0) RETURNING id", {'f': fid, 'pw': pw})
    exec("INSERT INTO user_roles (user_id, role_id, unit_id) VALUES (:u, :r, :unit)", {'u': uid_u, 'r': rid, 'unit': uid})
print(f'Admin: {uid_u}')

# 3 students + wallets
for nis, nama, wali, hp in [
    ('2025001','Ahmad Fauzi','Bapak Fauzi','081234500001'),
    ('2025002','Siti Nurhaliza','Ibu Haliza','081234500002'),
    ('2025003','Muhammad Rizki','Bapak Rizki','081234500003'),
]:
    sid = scalar("SELECT id FROM students WHERE nis=:n", {'n': nis})
    if not sid:
        sid = exec_returning("INSERT INTO students (id, unit_id, nis, full_name, guardian_name, guardian_phone, enrollment_status, admission_date) VALUES (gen_random_uuid(), :u, :nis, :nm, :g, :p, 'active', CURRENT_DATE) RETURNING id", {'u': uid, 'nis': nis, 'nm': nama, 'g': wali, 'p': hp})
    for atype, an, name, bal in [('wallet', f'WAL-{nis}', f'Dompet {nama}', 500000), ('savings', f'SAV-{nis}', f'Tabungan {nama}', 0)]:
        acc = scalar("SELECT id FROM financial_accounts WHERE account_number=:an", {'an': an})
        if not acc:
            exec("INSERT INTO financial_accounts (unit_id, owner_type, owner_id, account_type, account_number, name, cached_balance, daily_limit, status) VALUES (:u,'student',:s,:at,:an,:n,:b,1000000,'active')", {'u': uid, 's': sid, 'at': atype, 'an': an, 'n': name, 'b': bal})
    print(f'Siswa {nama}: {sid}')

# Invoice if none
if not scalar("SELECT 1 FROM invoices LIMIT 1"):
    s1 = scalar("SELECT id FROM students WHERE nis='2025001'")
    if s1:
        exec("INSERT INTO invoices (unit_id, student_id, invoice_number, academic_year_id, period_month, period_year, subtotal_amount, total_amount, paid_amount, outstanding_amount, issue_date, due_date, status) VALUES (:u, :s, 'INV-2026001', :ay, 1, 2026, 1500000, 1500000, 1500000, 0, CURRENT_DATE, CURRENT_DATE+30, 'paid')", {'u': uid, 's': s1, 'ay': ay})
        print('Invoice INV-2026001 (paid)')

print('\n=== SEED OK ===')
print('Login demo dibuat untuk admin@elyaomy.sch.id; password diambil dari DEMO_ADMIN_PASSWORD.')
