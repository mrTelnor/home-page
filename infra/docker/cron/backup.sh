#!/bin/sh
# Дамп PostgreSQL-БД + архив фото рецептов, загрузка на Я.Диск (WebDAV) и ротация.
# RETENTION_DAYS — сколько дней хранить (по умолчанию 14).
# При любом провале шлёт алерт админам через бот (POST /alert, X-Cron-Secret).
set -e

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="${BACKUP_DIR:-/tmp/backups}"
YADISK_DIR="backups"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DATABASES="homepage"
RECIPE_IMAGES_SRC="${RECIPE_IMAGES_SRC:-/backup-src/recipe_images}"
BOT_DATA_SRC="${BOT_DATA_SRC:-/backup-src/bot_data}"
# Dead-man's-switch: URL внешнего монитора (healthchecks.io), пингуем ТОЛЬКО при
# полном успехе. Если пинг не пришёл — монитор сам поднимет тревогу: так ловим
# «тихую смерть» crond/контейнера, а не только явный провал. Пусто → пропуск.
HEARTBEAT_URL="${HEARTBEAT_URL:-}"
MIN_DUMP_BYTES=1024  # пустой/оборванный дамп = провал, а не «успех»

mkdir -p "$BACKUP_DIR"
# Локальные копии, оставшиеся после прошлых неудачных загрузок, не копим вечно
find "$BACKUP_DIR" -type f -mtime +2 -delete 2>/dev/null || true
FAILURES=""

alert() {
    # Не валим скрипт, если бот недоступен — алерт best-effort
    curl -s -m 10 -X POST http://bot:8080/alert \
      -H "X-Cron-Secret: $CRON_SECRET" \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"$1\"}" || echo "[$(date)] WARN: alert delivery failed"
}

upload() {
    # Ретраи против разовых сетевых сбоев; --retry-all-errors — и против 5xx WebDAV
    local path="$1"
    local filename="$2"
    curl -sf --retry 3 --retry-all-errors -m 300 -T "$path" \
      "https://webdav.yandex.ru/${YADISK_DIR}/${filename}" \
      --user "${YADISK_USER}:${YADISK_APP_PASSWORD}"
}

backup_db() {
    local db="$1"
    local filename="${db}_${DATE}.dump"
    local path="${BACKUP_DIR}/${filename}"

    echo "[$(date)] dumping $db..."
    # Без пайпа: код возврата pg_dump не маскируется, а -Fc уже сжат (-Z6) —
    # gzip поверх был двойным сжатием и проверял статус gzip вместо pg_dump.
    if ! PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
      -h postgres -U "$POSTGRES_USER" -d "$db" -Fc -Z6 -f "$path"; then
      echo "[$(date)] ERROR: pg_dump of $db failed"
      rm -f "$path"
      return 1
    fi

    local size
    size=$(wc -c < "$path")
    if [ "$size" -lt "$MIN_DUMP_BYTES" ]; then
      echo "[$(date)] ERROR: dump of $db suspiciously small (${size} bytes)"
      return 1
    fi

    echo "[$(date)] uploading ${filename} (${size} bytes)..."
    if ! upload "$path" "$filename"; then
      echo "[$(date)] ERROR: upload of ${filename} failed; local copy kept"
      return 1
    fi

    rm -f "$path"
}

backup_dir() {
    # backup_dir <src_dir> <archive_prefix> <label>: tar.gz каталога → Я.Диск
    local src="$1"
    local prefix="$2"
    local label="$3"

    if [ ! -d "$src" ]; then
      echo "[$(date)] ERROR: ${label} dir ${src} is not mounted"
      return 1
    fi

    local filename="${prefix}_${DATE}.tar.gz"
    local path="${BACKUP_DIR}/${filename}"

    echo "[$(date)] archiving ${label}..."
    if ! tar -czf "$path" -C "$src" .; then
      echo "[$(date)] ERROR: tar of ${label} failed"
      rm -f "$path"
      return 1
    fi

    echo "[$(date)] uploading ${filename} ($(wc -c < "$path") bytes)..."
    if ! upload "$path" "$filename"; then
      echo "[$(date)] ERROR: upload of ${filename} failed; local copy kept"
      return 1
    fi

    rm -f "$path"
}

heartbeat() {
    # best-effort: провал пинга не должен ронять успешный бэкап.
    # Все три исхода логируются явно — иначе «нет WARN» не отличить от
    # «URL не задан», и по логу нельзя понять, дошёл ли пинг до монитора.
    if [ -z "$HEARTBEAT_URL" ]; then
      echo "[$(date)] heartbeat: HEARTBEAT_URL не задан — пропуск"
      return 0
    fi
    if curl -fsS -m 10 --retry 2 "$HEARTBEAT_URL" > /dev/null; then
      echo "[$(date)] heartbeat sent"
    else
      echo "[$(date)] WARN: heartbeat ping failed"
    fi
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

    # Все наши форматы: <db>_<дата>.dump, legacy <db>_<дата>.dump.gz, <recipe_images|bot_data>_<дата>.tar.gz
    echo "$listing" \
      | grep -oE "[a-z_]+_[0-9]{4}-[0-9]{2}-[0-9]{2}\.(dump(\.gz)?|tar\.gz)" \
      | sort -u \
      | while IFS= read -r f; do
          file_date=$(printf "%s" "$f" \
            | sed -nE "s/[a-z_]+_([0-9]{4}-[0-9]{2}-[0-9]{2})\..*/\1/p")
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

backup_dir "$RECIPE_IMAGES_SRC" recipe_images "recipe images" || FAILURES="${FAILURES} recipe_images"
backup_dir "$BOT_DATA_SRC" bot_data "bot data (дедуп напоминаний)" || FAILURES="${FAILURES} bot_data"

if [ -n "$FAILURES" ]; then
    alert "💾❌ Бэкап провалился:${FAILURES}. Подробности: docker logs cron"
    echo "[$(date)] backup FAILED for:${FAILURES}"
    exit 1
fi

CUTOFF=$(date -d "@$(( $(date +%s) - RETENTION_DAYS*86400 ))" +%Y-%m-%d)
rotate_old "$CUTOFF"

echo "[$(date)] backup complete."
heartbeat
