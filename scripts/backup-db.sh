#!/bin/bash
#
# PostgreSQL Backup Script for spp_sekolah
# Usage: ./scripts/backup-db.sh [backup-dir] [retention-days]
# Default: ./backups/, 30 hari
#
# Restore: pg_restore -d spp_sekolah -c --if-exists <backup_file>
#          atau: psql -d spp_sekolah -f <backup_file>  (untuk plain SQL)
#

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}/..")" && pwd)"
BACKUP_DIR="${1:-$APP_DIR/backups}"
RETENTION_DAYS="${2:-30}"
DB_NAME="spp_sekolah"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

# pg_dump env: pakai pgpass atau peer auth. JANGAN hardcode password.
# Jika butuh password, set PGPASSWORD di environment sebelum jalankan script ini.

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Backup $DB_NAME → $BACKUP_FILE"

pg_dump -d "$DB_NAME" --format=plain --no-owner --no-acl | gzip > "$BACKUP_FILE"

if [ -s "$BACKUP_FILE" ]; then
    SIZE="$(du -h "$BACKUP_FILE" | cut -f1)"
    echo "[$(date)] Backup OK — $SIZE"
else
    echo "ERROR: Backup kosong atau gagal" >&2
    exit 1
fi

# Retention: hapus backup lebih lama dari RETENTION_DAYS
echo "[$(date)] Hapus backup > $RETENTION_DAYS hari..."
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +"$RETENTION_DAYS" -print -delete

echo "[$(date)] Selesai"
