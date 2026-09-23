# Changelog - Website SPP Sekolah

## [Unreleased] - 2026-07-07

### Added
- **APK Management Module** (`backend/spp/apk.py`)
  - `GET /api/apk/latest` - Public endpoint untuk metadata APK terbaru (version, download_url, size, changelog)
  - `GET /api/apk/download/<filename>` - Public endpoint download APK file dengan mimetype Android
  - `POST /api/apk/upload` - Admin endpoint upload APK baru (requires `users.manage` permission)
  - Storage: `backend/static/download/` untuk APK files
  - Naming convention: `spp-elyaomy-{version}.apk`
  - Security: path sanitization, extension validation (.apk only), auth untuk upload

### Fixed
- **RFID Card Events Bug** (`backend/spp/rfid.py:85`)
  - Removed non-existent `reason` column from INSERT statement in `block_card()` endpoint
  - Column `reason` tidak ada di schema `rfid_card_events`, hanya ada `metadata JSONB`
  - Fix: hanya insert `card_id, event_type, user_id`

### Changed
- **Blueprint Registration** (`backend/spp/__init__.py:142`)
  - Added `apk_bp` blueprint registration
  - Total 7 blueprints: auth, finance, ops, accounting, rfid, audit, apk

### Infrastructure
- Created `backend/static/download/` directory
- Added dummy APK file for testing: `spp-elyaomy-1.0.0.apk`

### Verified
- ✅ Python syntax check: passed
- ✅ App creation: OK
- ✅ 69 routes registered (3 APK routes)
- ✅ APK latest endpoint: 200 OK, returns metadata
- ✅ APK download endpoint: 200 OK, correct mimetype
- ✅ APK download 404: returns 404 for non-existent file
- ✅ APK download validation: rejects non-.apk files (400)
- ✅ APK upload auth: requires authentication (401 without token)
- ✅ Health endpoint: 200 OK
- ✅ Dashboard endpoint: 200 OK
- ✅ Auth validation: 400 for empty login payload

### Documentation
- Updated `memory.md` with new APK module structure
- Added endpoint documentation (section 6)
- Documented bug fix (section 8)

### Notes
- Frontend/Android tidak diubah sesuai instruksi (jangan edit frontend/android)
- APK endpoints siap digunakan oleh Android app untuk auto-update feature
- Static file serving sudah built-in di Flask
- File upload menggunakan Flask `request.files` dengan size tracking
