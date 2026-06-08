#!/bin/sh
# Дамп нескольких PostgreSQL-БД, загрузка на Я.Диск (WebDAV) и ротация старых бэкапов.
# RETENTION_DAYS — сколько дней хранить (по умолчанию 14).
set -e

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/tmp/backups"
YADISK_DIR="backups"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DATABASES="homepage knowledge"

mkdir -p "$BACKUP_DIR"

backup_db() {
    local db="$1"
    local filename="${db}_${DATE}.dump.gz"

    echo "[$(date)] dumping $db..."
    PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
      -h postgres -U "$POSTGRES_USER" -d "$db" -Fc | gzip > "${BACKUP_DIR}/${filename}"

    echo "[$(date)] uploading ${filename}..."
    if ! curl -sf -T "${BACKUP_DIR}/${filename}" \
      "https://webdav.yandex.ru/${YADISK_DIR}/${filename}" \
      --user "${YADISK_USER}:${YADISK_APP_PASSWORD}"; then
      echo "[$(date)] ERROR: upload of ${filename} failed; local copy kept"
      return 1
    fi

    rm -f "${BACKUP_DIR}/${filename}"
}

rotate_old() {
    local cutoff="$1"
    echo "[$(date)] rotating files with date < ${cutoff}..."

    local listing
    listing=$(curl -sf -X PROPFIND -H "Depth: 1" \
      "https://webdav.yandex.ru/${YADISK_DIR}/" \
      --user "${YADISK_USER}:${YADISK_APP_PASSWORD}" || true)

    if [ -z "$listing" ]; then
      echo "[$(date)] WARN: PROPFIND failed, skipping rotation"
      return
    fi

    echo "$listing" \
      | grep -oE "(homepage|knowledge)_[0-9]{4}-[0-9]{2}-[0-9]{2}\.dump\.gz" \
      | sort -u \
      | while IFS= read -r f; do
          file_date=$(printf "%s" "$f" \
            | sed -nE "s/[a-z]+_([0-9]{4}-[0-9]{2}-[0-9]{2})\.dump\.gz/\1/p")
          if [ "$file_date" \< "$cutoff" ]; then
            echo "[$(date)] deleting old: $f"
            curl -sf -X DELETE \
              "https://webdav.yandex.ru/${YADISK_DIR}/$f" \
              --user "${YADISK_USER}:${YADISK_APP_PASSWORD}" \
              || echo "[$(date)] WARN: failed to delete $f"
          fi
        done
}

for db in $DATABASES; do
    backup_db "$db"
done

CUTOFF=$(date -d "@$(( $(date +%s) - RETENTION_DAYS*86400 ))" +%Y-%m-%d)
rotate_old "$CUTOFF"

echo "[$(date)] backup complete."
