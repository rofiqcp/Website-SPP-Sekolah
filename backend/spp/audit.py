"""Audit & security: audit logs, security flags, approval workflow."""
from flask import Blueprint, jsonify, request
from sqlalchemy import text

from . import db, core

audit_bp = Blueprint("audit", __name__, url_prefix="/api")


@audit_bp.get("/audit-logs")
@core.require_auth(permissions=["audit.view"])
def list_audit():
    try:
        limit = int(request.args.get("limit", 100))
        if limit < 1 or limit > 200:
            limit = 100
    except (TypeError, ValueError):
        limit = 100
    return jsonify({"items": db.query_all(
        "SELECT * FROM audit_logs ORDER BY id DESC LIMIT :lim", {"lim": limit})})


@audit_bp.get("/security-flags")
@core.require_auth(permissions=["audit.view"])
def list_flags():
    return jsonify({"items": db.query_all("SELECT * FROM security_flags ORDER BY id DESC LIMIT 100")})


@audit_bp.post("/security-flags/<int:flag_id>/resolve")
@core.require_auth(permissions=["audit.view"])
def resolve_flag(flag_id):
    data = core.get_json()
    status = str(data.get("status", "resolved"))
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE security_flags SET status=:s WHERE id=:id"), {"s": status, "id": flag_id})
        core.audit("security.flag.resolve", "security_flags", flag_id)
    return jsonify({"message": "Flag diperbarui"})


# ---------------- approvals ----------------
@audit_bp.get("/approvals")
@core.require_auth(permissions=["approvals.decide", "budget.approve"], any_of=["approvals.decide", "budget.approve"])
def list_approvals():
    return jsonify({"items": db.query_all("SELECT * FROM approval_requests WHERE status='pending' ORDER BY id DESC")})


@audit_bp.post("/approvals/<int:approval_id>/decide")
@core.require_auth(permissions=["approvals.decide", "budget.approve"], any_of=["approvals.decide", "budget.approve"])
def decide_approval(approval_id):
    user = core.current_user()
    data = core.get_json()
    decision = str(data.get("decision", "approved"))
    if decision not in ("approved", "rejected"):
        return core.json_error("Keputusan tidak valid", 400)
    with db.engine.begin() as conn:
        ap = conn.execute(text("SELECT * FROM approval_requests WHERE id=:id AND status='pending'"), {"id": approval_id}).first()
        if not ap:
            return core.json_error("Approval tidak ditemukan", 404)
        if decision == "approved":
            conn.execute(text("UPDATE approval_requests SET status='approved', approved_by=:u, decided_at=now() WHERE id=:id"),
                         {"u": user["sub"], "id": approval_id})
        else:
            conn.execute(text("UPDATE approval_requests SET status='rejected', rejected_by=:u, decided_at=now(), reason=:r WHERE id=:id"),
                         {"u": user["sub"], "id": approval_id, "r": str(data.get("reason", ""))})
        core.audit("approval.decide", "approval_requests", approval_id, new_value={"decision": decision})
    return jsonify({"message": f"Approval {decision}"})
