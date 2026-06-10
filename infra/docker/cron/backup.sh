#!/bin/sh
# Дамп нескольких PostgreSQL-БД, загрузка на Я.Диск (WebDAV) и ротация старых бэкапов.
# RETENTION_DAYS — сколько дней хранить (по умолчанию 14).
# При любом провале шлёт алерт админам через бот (POST /alert, X-Cron-Secret).
set -e

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/tmp/backups"
YADISK_DIR="backups"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DATABASES="homepage"
MIN_DUMP_BYTES=1024  # пустой/оборванный дамп = провал, а не «успех»

mkdir -p "$BACKUP_DIR"
FAILURES=""

alert() {
    # Не валим скрипт, если бот недоступен — алерт best-effort
    curl -s -m 10 -X POST http://bot:8080/alert \
      -H "X-Cron-Secret: $CRON_SECRET" \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"$1\"}" || echo "[$(date)] WARN: alert delivery failed"
}

backup_db() {
    local db="$1"
    local filename="${db}_${DATE}.dump.gz"
    local path="${BACKUP_DIR}/${filename}"

    echo "[$(date)] dumping $db..."
    if ! PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
      -h postgres -U "$POSTGRES_USER" -d "$db" -Fc | gzip > "$path"; then
      echo "[$(date)] ERROR: pg_dump of $db failed"
      return 1
    fi

    local size
    size=$(wc -c < "$path")
    if [ "$size" -lt "$MIN_DUMP_BYTES" ]; then
      echo "[$(date)] ERROR: dump of $db suspiciously small (${size} bytes)"
      return 1
    fi

    echo "[$(date)] uploading ${filename} (${size} bytes)..."
    if ! curl -sf -T "$path" \
      "https://webdav.yandex.ru/${YADISK_DIR}/${filename}" \
      --user "${YADISK_USER}:${YADISK_APP_PASSWORD}"; then
      echo "[$(date)] ERROR: upload of ${filename} failed; local copy kept"
      return 1
    fi

    rm -f "$path"
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
      alert "💾 Бэкап: ротация пропущена — Яндекс.Диск не ответил на PROPFIND"
      return
    fi

    echo "$listing" \
      | grep -oE "homepage_[0-9]{4}-[0-9]{2}-[0-9]{2}\.dump\.gz" \
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
    backup_db "$db" || FAILURES="${FAILURES} ${db}"
done

if [ -n "$FAILURES" ]; then
    alert "💾❌ Бэкап БД провалился:${FAILURES}. Подробности: docker logs cron"
    echo "[$(date)] backup FAILED for:${FAILURES}"
    exit 1
fi

CUTOFF=$(date -d "@$(( $(date +%s) - RETENTION_DAYS*86400 ))" +%Y-%m-%d)
rotate_old "$CUTOFF"

echo "[$(date)] backup complete."
