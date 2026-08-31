#!/bin/sh
# Алерт админам через бот (best-effort): cron-alert.sh "текст".
# Экранируем кавычки/бэкслеши и переводы строк, чтобы не сломать JSON.
TEXT=$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')
curl -s -m 10 -X POST http://bot:8080/alert \
  -H "X-Cron-Secret: $CRON_SECRET" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"$TEXT\"}" || echo "[$(date)] WARN: alert delivery failed"
