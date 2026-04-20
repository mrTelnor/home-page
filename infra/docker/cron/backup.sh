#!/bin/sh
set -e

DATE=$(date +%Y-%m-%d)
FILENAME="homepage_${DATE}.dump.gz"
BACKUP_DIR="/tmp/backups"
YADISK_DIR="backups"

mkdir -p "$BACKUP_DIR"

# Dump and compress
echo "[$(date)] Starting backup..."
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -Fc | gzip > "${BACKUP_DIR}/${FILENAME}"

echo "[$(date)] Uploading to Yandex.Disk..."
curl -s -T "${BACKUP_DIR}/${FILENAME}" \
  "https://webdav.yandex.ru/${YADISK_DIR}/${FILENAME}" \
  --user "${YADISK_USER}:${YADISK_APP_PASSWORD}"

# Rotate: delete backup older than 14 days
OLD_DATE=$(date -d "-14 days" +%Y-%m-%d 2>/dev/null || date -v-14d +%Y-%m-%d 2>/dev/null)
if [ -n "$OLD_DATE" ]; then
  OLD_FILENAME="homepage_${OLD_DATE}.dump.gz"
  echo "[$(date)] Deleting old backup: ${OLD_FILENAME}"
  curl -s -X DELETE \
    "https://webdav.yandex.ru/${YADISK_DIR}/${OLD_FILENAME}" \
    --user "${YADISK_USER}:${YADISK_APP_PASSWORD}" || true
fi

# Cleanup local
rm -f "${BACKUP_DIR}/${FILENAME}"
echo "[$(date)] Backup complete."
