# Website SPP Sekolah

Sistem informasi keuangan dan operasional sekolah untuk Yayasan Pendidikan El Yaomy Klaten. Aplikasi mencakup SPP, pembayaran, tabungan/dompet, e-kantin RFID, inventaris, aset, akuntansi, RAB, laporan, audit, serta aplikasi Android pendamping.

Repository GitHub: `rofiqcp/Website-SPP-Sekolah`  
Default branch: **`v1`**

## Stack

- **Backend:** Python, Flask, PostgreSQL, SQLAlchemy, Gunicorn
- **Frontend:** React + Vite
- **Android:** Gradle/Kotlin project
- **Security:** JWT, RBAC, object-level authorization, MFA/TOTP, rate limiting, audit logging
- **RFID:** HID keyboard reader dan Web Serial API
- **Process manager:** PM2 melalui `server.sh`

## Struktur

- `backend/` — API, domain SPP/keuangan, migration, test, dan static source
- `frontend/` — aplikasi React/Vite
- `android/` — aplikasi Android
- `scripts/` — backup database dan seed data demo
- `workflow/` — catatan/desain alur sistem
- `server.sh` — start, build, stop, status, syntax check, dan backup
- `CHANGELOG.md` — riwayat perubahan

## Quick start

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

./server.sh build
./server.sh status
```

Default endpoint lokal:

- Frontend: `http://localhost:5100`
- Backend: `http://localhost:5101`
- Health: `http://localhost:5101/health`

Konfigurasi production dan credential harus diisi melalui file `.env` lokal yang **tidak di-commit**.

## Seed data demo

Script `scripts/seed_demo.py` menggunakan password demo dari environment. Contoh:

```bash
export DEMO_ADMIN_PASSWORD='ganti-dengan-password-demo-lokal'
backend/.venv/bin/python scripts/seed_demo.py
```

Jangan menaruh password demo atau password production di README, source code, maupun commit Git.

## Database backup

```bash
./server.sh backup
# atau
./scripts/backup-db.sh
```

Backup disimpan secara lokal di `backups/` dan tidak ikut Git.

## Build Android

Gunakan Gradle wrapper di folder `android/`. File `.apk`, `.aab`, keystore, `local.properties`, dan direktori build tidak disimpan di Git. Artefak aplikasi sebaiknya dipublikasikan melalui GitHub Releases atau mekanisme deployment terpisah.

## Git workflow

```bash
git switch v1
git pull --rebase origin v1
git add -A
git commit -m "..."
git push origin v1
```

## Keamanan repository

Repository tidak boleh berisi `.env`, JWT/RFID/webhook secret, password database, credential OAuth/payment gateway, backup database, log runtime, virtualenv, `node_modules`, build output, APK/AAB, keystore, cache, atau file lokal IDE.

Untuk konfigurasi awal gunakan `backend/.env.example` dan `frontend/.env.example`.
