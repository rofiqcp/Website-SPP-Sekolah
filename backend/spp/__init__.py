"""Application factory for the SPP Sekolah backend."""
import os

from flask import Flask, jsonify, request, g
from flask_cors import CORS
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from . import db, core
from .auth import auth_bp
from .finance import finance_bp
from .ops import ops_bp
from .accounting import accounting_bp
from .rfid import rfid_bp
from .audit import audit_bp
from .apk import apk_bp

SCHOOL_NAME = os.getenv("SCHOOL_NAME", "Yayasan Pendidikan El Yaomy Klaten")
FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGIN", "http://localhost:5100").split(",") if o.strip()]


def money(v):
    try:
        return "Rp " + f"{int(v):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "Rp 0"


def create_app():
    app = Flask(__name__)
    CORS(app, origins=FRONTEND_ORIGINS + ["http://127.0.0.1:5100", "http://localhost:5100"], supports_credentials=True)
    app.db_ready = False
    app.db_init_attempted = False

    @app.before_request
    def ensure_db():
        if not app.db_ready and not app.db_init_attempted:
            app.db_init_attempted = True
            try:
                db.init_db()
                app.db_ready = True
            except SQLAlchemyError as e:
                app.logger.error("DB init error: %s", e)

    @app.after_request
    def security_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), usb=(self), serial=(self)"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(SQLAlchemyError)
    def db_error(e):
        return jsonify({"message": "Kesalahan database", "detail": str(e).split("\n")[0][:200]}), 503

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(429)
    def http_error(e):
        msg = e.description if hasattr(e, "description") else "Error"
        return jsonify({"message": msg}), e.code

    @app.get("/health")
    def health():
        db.query_one("SELECT 1 AS ok")
        return jsonify({"status": "ok", "database": "postgresql", "service": "SPP Sekolah API"})

    @app.get("/api/dashboard")
    def dashboard():
        user = None
        raw = core.token_from_request()
        if raw:
            user = core.decode_token(raw, "access")
        # Check user status/lockout like require_auth does
        if user:
            from datetime import timezone as tz
            with db.engine.connect() as conn:
                row = conn.execute(text("SELECT status, locked_until FROM users WHERE id=:id"), {"id": user["sub"]}).first()
            if not row or row[0] != "active":
                user = None
            elif row[1]:
                lu = row[1].replace(tzinfo=tz.utc) if row[1].tzinfo is None else row[1]
                if lu > datetime.now(tz.utc):
                    user = None
        public = {
            "school": SCHOOL_NAME,
            "foundation": {"name": SCHOOL_NAME, "address": "Batur Baru, Tegalrejo, Ceper, Klaten, Jawa Tengah 57465",
                           "phone": "0272-555578", "email": "sdim.elyaomy@gmail.com", "npsn": "20331580",
                           "accreditation": "A", "tagline": "Bertaqwa, Cerdas, Mandiri, Kreatif"},
            "modules": ["Tagihan Siswa", "Tabungan Siswa", "Pembayaran SPP Online", "Kasir Sekolah", "E-Kantin",
                        "Dompet Digital", "Inventaris & Aset", "Manajemen Aset", "Jurnal", "Neraca",
                        "RAB Sekolah", "Laporan Keuangan", "RFID"],
            "stats": [], "students": [], "bills": [], "wallets": [], "canteen": [], "transactions": [],
            "assets": [], "journals": [], "budget": [], "invoices": [],
        }
        if not user:
            public["stats"] = [
                {"label": "Unit Pendidikan", "value": "4 Program", "tone": "blue"},
                {"label": "Modul Keuangan", "value": "13 Modul", "tone": "orange"},
                {"label": "Akses", "value": "24/7 Online", "tone": "purple"},
                {"label": "Security", "value": "Hardened", "tone": "green"},
            ]
            return jsonify(public)
        g.user = user
        perms = core.get_permissions(user["role"])
        # role-scoped dashboard data
        if "students.view" in perms:
            cls_ids = core.class_ids_for(user)
            if user['role'] in ('wali_kelas','guru') and cls_ids:
                students = db.query_all(
                    "SELECT s.id, s.full_name, c.name AS class_name, s.nis FROM students s LEFT JOIN classes c ON c.id=s.class_id "
                    "WHERE s.class_id = ANY(:cls) ORDER BY s.id LIMIT 50", {"cls": list(cls_ids)})
            else:
                students = db.query_all(
                    "SELECT s.id, s.full_name, c.name AS class_name, s.nis FROM students s LEFT JOIN classes c ON c.id=s.class_id "
                    "ORDER BY s.id LIMIT 50")
        else:
            students = []
        if "students.view" in perms:
            if user['role'] in ('siswa','orang_tua'):
                sid = core.user_student_id(user)
                if sid:
                    invoices = db.query_all(
                        "SELECT i.*, s.full_name AS student_name FROM invoices i JOIN students s ON s.id=i.student_id "
                        "WHERE i.student_id = :sid ORDER BY i.id DESC LIMIT 50", {"sid": sid})
                else:
                    invoices = []
            else:
                invoices = db.query_all(
                    "SELECT i.*, s.full_name AS student_name FROM invoices i JOIN students s ON s.id=i.student_id "
                    "ORDER BY i.id DESC LIMIT 50")
        else:
            invoices = []
        wallets = db.query_all("SELECT * FROM financial_accounts WHERE account_type IN ('wallet','savings') ORDER BY id LIMIT 50") if "students.view" in perms else []
        canteen = db.query_all("SELECT * FROM canteen_products ORDER BY name") if "canteen.manage" in perms else []
        assets = db.query_all("SELECT * FROM fixed_assets ORDER BY id LIMIT 50") if "assets.manage" in perms else []
        journals = db.query_all("SELECT * FROM journal_entries ORDER BY id DESC LIMIT 20") if "accounting.view" in perms else []
        budgets = db.query_all("SELECT * FROM budgets ORDER BY id DESC LIMIT 20") if "budget.manage" in perms or "reports.view" in perms else []
        # summary stats
        summ = db.query_one(
            "SELECT (SELECT COALESCE(SUM(total_amount),0) FROM invoices) AS bill, "
            "(SELECT COALESCE(SUM(paid_amount),0) FROM invoices) AS paid, "
            "(SELECT COALESCE(SUM(cached_balance),0) FROM financial_accounts WHERE account_type='wallet') AS wal, "
            "(SELECT COALESCE(SUM(cached_balance),0) FROM financial_accounts WHERE account_type='savings') AS sav, "
            "(SELECT COUNT(*) FROM students WHERE enrollment_status='active') AS stu")
        total_bill = summ["bill"] or 0
        paid = summ["paid"] or 0
        public["stats"] = [
            {"label": "Tagihan Siswa", "value": money(total_bill), "tone": "blue"},
            {"label": "Pembayaran Masuk", "value": money(paid), "tone": "green"},
            {"label": "Piutang SPP", "value": money(total_bill - paid), "tone": "orange"},
            {"label": "Saldo Dompet", "value": money(summ["wal"] or 0), "tone": "purple"},
            {"label": "Tabungan", "value": money(summ["sav"] or 0), "tone": "green"},
            {"label": "Siswa Aktif", "value": str(summ["stu"] or 0), "tone": "blue"},
        ]
        public.update({"students": students, "invoices": invoices, "wallets": wallets, "canteen": canteen,
                       "assets": assets, "journals": journals, "budget": budgets,
                       "permissions": sorted(perms), "role": user["role"]})
        return jsonify(public)

    app.register_blueprint(auth_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(ops_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(rfid_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(apk_bp)
    return app
