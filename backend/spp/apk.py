"""APK metadata & download endpoints for Android app."""
import re
from pathlib import Path
from flask import Blueprint, jsonify, send_file, request
from werkzeug.utils import secure_filename
from . import core

apk_bp = Blueprint("apk", __name__, url_prefix="/api/apk")

STATIC_DIR = Path(__file__).parent.parent / "static"
DOWNLOAD_DIR = STATIC_DIR / "download"
MAX_APK_SIZE = 100 * 1024 * 1024


def parse_version_code(version_str):
    parts = version_str.split(".")
    try:
        return int(parts[0]) * 10000 + int(parts[1]) * 100 + int(parts[2])
    except (IndexError, ValueError):
        return 1


@apk_bp.get("/latest")
def latest_metadata():
    """Public endpoint: return latest APK metadata."""
    apk_files = list(DOWNLOAD_DIR.glob("*.apk"))
    if not apk_files:
        return jsonify({
            "version": "1.0.0",
            "version_code": 1,
            "download_url": "/api/apk/download/spp-elyaomy.apk",
            "size_bytes": 0,
            "release_date": "2026-07-07",
            "changelog": "Initial release",
            "available": False
        })
    
    latest = max(apk_files, key=lambda p: p.stat().st_mtime)
    stat = latest.stat()
    
    version = "1.0.0"
    version_code = 1
    match = re.search(r'(\d+\.\d+\.\d+)', latest.stem)
    if match:
        version = match.group(1)
        version_code = parse_version_code(version)
    
    return jsonify({
        "version": version,
        "version_code": version_code,
        "download_url": f"/api/apk/download/{latest.name}",
        "filename": latest.name,
        "size_bytes": stat.st_size,
        "release_date": stat.st_mtime,
        "changelog": f"SPP El Yaomy v{version}",
        "available": True,
        "min_android_version": 21
    })


@apk_bp.get("/list")
@core.require_auth(permissions=["users.manage"])
def list_apks():
    """Admin only: list all available APKs."""
    apk_files = sorted(DOWNLOAD_DIR.glob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True)
    items = []
    for apk in apk_files:
        stat = apk.stat()
        version = "1.0.0"
        match = re.search(r'(\d+\.\d+\.\d+)', apk.stem)
        if match:
            version = match.group(1)
        items.append({
            "filename": apk.name,
            "version": version,
            "size_bytes": stat.st_size,
            "uploaded_at": stat.st_mtime,
            "download_url": f"/api/apk/download/{apk.name}"
        })
    return jsonify({"items": items})


@apk_bp.get("/download/<filename>")
def download_apk(filename):
    """Public endpoint: download APK file."""
    if not filename.endswith(".apk") or "/" in filename or "\\" in filename:
        return jsonify({"message": "Invalid file"}), 400
    
    safe_name = secure_filename(filename)
    apk_path = DOWNLOAD_DIR / safe_name
    
    if not apk_path.exists() or not apk_path.is_file():
        return jsonify({"message": "File not found"}), 404
    
    return send_file(
        apk_path,
        mimetype="application/vnd.android.package-archive",
        as_attachment=True,
        download_name=safe_name
    )


@apk_bp.post("/upload")
@core.require_auth(permissions=["users.manage"])
def upload_apk():
    """Admin only: upload new APK version."""
    if "file" not in request.files:
        return core.json_error("No file provided", 400)
    
    file = request.files["file"]
    if not file.filename or not file.filename.endswith(".apk"):
        return core.json_error("File harus berekstensi .apk", 400)
    
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_APK_SIZE:
        return core.json_error(f"File terlalu besar (max {MAX_APK_SIZE // 1024 // 1024}MB)", 400)
    if size < 1024:
        return core.json_error("File terlalu kecil atau corrupt", 400)
    
    version = request.form.get("version", "1.0.0")
    if not re.match(r'^\d+\.\d+\.\d+$', version):
        return core.json_error("Format version harus X.Y.Z", 400)
    
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    final_name = f"spp-elyaomy-{version}.apk"
    save_path = DOWNLOAD_DIR / final_name
    
    file.save(save_path)
    
    core.audit("apk.upload", "apk", None, new_value={"filename": final_name, "version": version, "size": size})
    
    return jsonify({
        "message": "APK uploaded",
        "filename": final_name,
        "version": version,
        "size_bytes": size,
        "download_url": f"/api/apk/download/{final_name}"
    }), 201


@apk_bp.delete("/<filename>")
@core.require_auth(permissions=["users.manage"])
def delete_apk(filename):
    """Admin only: delete APK file."""
    if not filename.endswith(".apk") or "/" in filename or "\\" in filename:
        return core.json_error("Invalid filename", 400)
    
    safe_name = secure_filename(filename)
    apk_path = DOWNLOAD_DIR / safe_name
    
    if not apk_path.exists():
        return core.json_error("File not found", 404)
    
    apk_path.unlink()
    core.audit("apk.delete", "apk", None, old_value={"filename": filename})
    
    return jsonify({"message": "APK deleted"})
