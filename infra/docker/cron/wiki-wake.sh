#!/bin/sh
# Будильник Supabase: бесплатный проект уходит в паузу от простоя, поэтому раз
# в сутки дёргаем /api/wiki/health — backend при этом выполняет запрос к базе
# знаний через пулер.
# Эндпоинт всегда отвечает 200, состояние — в поле status тела ответа
# (ok / unavailable / disabled), поэтому смотрим на тело, а не на код ответа.
# При провале — алерт админам через cron-alert.sh.
URL="${WIKI_HEALTH_URL:-http://backend:8000/api/wiki/health}"
ATTEMPTS="${WIKI_WAKE_ATTEMPTS:-3}"
# Пауза между попытками больше 10 с: backend отдаёт результат проверки из памяти
# 10 секунд, более частый повтор получил бы тот же ответ, а не новую проверку.
PAUSE="${WIKI_WAKE_PAUSE:-15}"

# top_level_status <тело>: значение поля status верхнего уровня или пусто.
# jq в образе нет, поэтому разбор строгий: тело должно быть одним плоским
# JSON-объектом — без вложенных объектов и массивов. Тогда любое поле в нём —
# верхнего уровня, и status из вложенного объекта (`{"detail":{"status":"ok"}}`)
# или из массива не может сойти за ответ health. Тело другой формы — «нет status».
top_level_status() {
    printf '%s' "$1" | tr -d '\r\n' | sed -n \
        '/^[[:space:]]*{[^][{}]*}[[:space:]]*$/ s/.*[{,][[:space:]]*"status"[[:space:]]*:[[:space:]]*"\([a-z]*\)"[[:space:]]*[,}].*/\1/p'
}

attempt=1
while :; do
    # Ошибка curl (сеть, не 2xx) — backend не ответил; текст ошибки уходит в лог cron
    if body=$(curl -sS -f -m 30 "$URL"); then
        answered=1
        status=$(top_level_status "$body")
    else
        answered=0
        status=""
    fi
    case "$status" in
        ok)
            echo "[$(date)] wiki-wake: ok (попытка $attempt)"
            exit 0
            ;;
        disabled)
            # Вики выключена настройкой (WIKI_DATABASE_URL пуст) — будить нечего
            echo "[$(date)] wiki-wake: disabled — вики выключена, запроса к базе не было"
            exit 0
            ;;
    esac
    if [ "$answered" -eq 0 ]; then
        problem="backend не ответил на проверку health вики — проверь контейнер backend"
    elif [ -z "$status" ]; then
        problem="backend ответил на проверку health вики без поля status — неожиданный ответ, проверь backend"
    else
        problem="backend ответил, что база знаний недоступна (status: $status) — проверь, не на паузе ли проект Supabase"
    fi
    echo "[$(date)] wiki-wake: попытка $attempt из $ATTEMPTS — $problem"
    [ "$attempt" -ge "$ATTEMPTS" ] && break
    attempt=$((attempt + 1))
    sleep "$PAUSE"
done

/usr/local/bin/cron-alert.sh "⏰❌ будильник Supabase: $problem"
exit 1
