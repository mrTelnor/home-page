#!/bin/sh
# Дамп PostgreSQL, загрузка на Я.Диск (WebDAV) и ротация старых бэкапов.
# RETENTION_DAYS — сколько дней хранить (по умолчанию 14).
set -e

DATE=$(date +%Y-%m-%d)
FILENAME="homepage_${DATE}.dump.gz"
BACKUP_DIR="/tmp/backups"
YADISK_DIR="backups"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

# 1. Dump + gzip
echo "[$(date)] Starting backup..."
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -Fc | gzip > "${BACKUP_DIR}/${FILENAME}"

# 2. Upload — fail fast если Я.Диск вернул не 2xx (раньше ошибки игнорировались
#    и старый локальный файл удалялся, что прятало проблему молча).
echo "[$(date)] Uploading to Yandex.Disk..."
if ! curl -sf -T "${BACKUP_DIR}/${FILENAME}" \
  "https://webdav.yandex.ru/${YADISK_DIR}/${FILENAME}" \
  --user "${YADISK_USER}:${YADISK_APP_PASSWORD}"; then
  echo "[$(date)] ERROR: upload failed; local file kept at ${BACKUP_DIR}/${FILENAME}"
  exit 1
fi

# 3. Rotate: удалить все бэкапы старше RETENTION_DAYS.
#    Имя файла `homepage_YYYY-MM-DD.dump.gz` — лексикографическая сортировка
#    равна хронологической, поэтому сравниваем строки напрямую.
#    Старый скрипт пытался удалить файл одной конкретной даты через `date -d
#    "-14 days"`, который busybox-date на Alpine не понимает — OLD_DATE
#    оказывался пустым, и ротация ни разу не отработала за 50 дней.
CUTOFF=$(date -d "@$(( $(date +%s) - RETENTION_DAYS*86400 ))" +%Y-%m-%d)
echo "[$(date)] Rotating: cutoff=${CUTOFF} (retain ${RETENTION_DAYS} days)"

LISTING=$(curl -sf -X PROPFIND -H "Depth: 1" \
  "https://webdav.yandex.ru/${YADISK_DIR}/" \
  --user "${YADISK_USER}:${YADISK_APP_PASSWORD}" || true)

if [ -z "$LISTING" ]; then
  echo "[$(date)] WARN: PROPFIND failed or empty, skipping rotation"
else
  echo "$LISTING" \
    | grep -oE "homepage_[0-9]{4}-[0-9]{2}-[0-9]{2}\.dump\.gz" \
    | sort -u \
    | while IFS= read -r f; do
        file_date=$(printf "%s" "$f" | sed -nE "s/homepage_([0-9]{4}-[0-9]{2}-[0-9]{2})\.dump\.gz/\1/p")
        if [ "$file_date" \< "$CUTOFF" ]; then
          echo "[$(date)] Deleting old: $f"
          curl -sf -X DELETE \
            "https://webdav.yandex.ru/${YADISK_DIR}/$f" \
            --user "${YADISK_USER}:${YADISK_APP_PASSWORD}" \
            || echo "[$(date)] WARN: failed to delete $f"
        fi
      done
fi

# 4. Cleanup local — только после успешного upload.
rm -f "${BACKUP_DIR}/${FILENAME}"
echo "[$(date)] Backup complete."
