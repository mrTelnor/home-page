#!/bin/sh
# Тесты wiki-wake.sh на стабах curl/sleep. Запускать в том же окружении, что и прод (alpine/busybox ash):
#   docker run --rm -v "$(pwd)/infra/docker/cron:/cron" alpine:3.21 sh /cron/tests/test_wiki_wake.sh
# wiki-wake.sh зовёт алерт по полному пути /usr/local/bin/cron-alert.sh, поэтому тест
# на время работы кладёт туда настоящий cron-alert.sh (если его там нет) и убирает за собой.
set -u

CRON_DIR="${CRON_DIR:-/cron}"
WORK=$(mktemp -d)
STUBS="$WORK/stubs"
mkdir -p "$STUBS"
PASS=0
FAIL=0

# ---------- стабы ----------

# curl: пишет каждый вызов строкой в $CURL_LOG.
# /alert -> успех. Остальное (health): ответ на N-й вызов берётся из файла
# $RESP_DIR/N (нет такого — из $RESP_DIR/default): первая строка — код возврата
# curl, остальное — тело ответа.
cat > "$STUBS/curl" <<'EOF'
#!/bin/sh
echo "$*" >> "$CURL_LOG"
case " $* " in
    *"/alert"*) exit 0 ;;
esac
n=$(cat "$RESP_DIR/count" 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" > "$RESP_DIR/count"
f="$RESP_DIR/$n"
[ -f "$f" ] || f="$RESP_DIR/default"
sed 1d "$f"
exit "$(sed -n 1p "$f")"
EOF

# sleep: не ждёт, только записывает длительность паузы
cat > "$STUBS/sleep" <<'EOF'
#!/bin/sh
echo "$1" >> "$SLEEP_LOG"
EOF
chmod +x "$STUBS/curl" "$STUBS/sleep"

# Как и Dockerfile: снимаем возможный CRLF из рабочей копии (правки с Windows).
sed 's/\r$//' "$CRON_DIR/wiki-wake.sh" > "$WORK/wiki-wake.sh"

ALERT_BIN=/usr/local/bin/cron-alert.sh
ALERT_INSTALLED=0
if [ ! -e "$ALERT_BIN" ]; then
    mkdir -p /usr/local/bin
    sed 's/\r$//' "$CRON_DIR/cron-alert.sh" > "$ALERT_BIN"
    chmod +x "$ALERT_BIN"
    ALERT_INSTALLED=1
fi
cleanup() {
    [ "$ALERT_INSTALLED" -eq 1 ] && rm -f "$ALERT_BIN"
    rm -rf "$WORK"
}
trap cleanup EXIT

# ---------- запуск и проверки ----------

# new_case <имя>: чистые журналы и каталог ответов для теста
new_case() {
    CASE="$1"
    RESP_DIR="$WORK/$CASE.resp"
    CURL_LOG="$WORK/$CASE.curl"
    SLEEP_LOG="$WORK/$CASE.sleep"
    OUT="$WORK/$CASE.out"
    mkdir -p "$RESP_DIR"
    : > "$CURL_LOG"
    : > "$SLEEP_LOG"
}

# resp <N|default> <код возврата curl> <тело>
resp() {
    printf '%s\n%s' "$2" "$3" > "$RESP_DIR/$1"
}

# run_wake: значения по умолчанию (адрес, число попыток, пауза) — как в проде,
# окружение передаётся явно через env.
run_wake() {
    env -i PATH="$STUBS:/usr/bin:/bin" \
        CURL_LOG="$CURL_LOG" \
        SLEEP_LOG="$SLEEP_LOG" \
        RESP_DIR="$RESP_DIR" \
        CRON_SECRET=s \
        sh "$WORK/wiki-wake.sh" > "$OUT" 2>&1
}

check() {
    # $1 — код результата проверки, $2 — название
    if [ "$1" -eq 0 ]; then
        PASS=$((PASS + 1))
        echo "  ok: $2"
    else
        FAIL=$((FAIL + 1))
        echo "  FAIL: $2"
    fi
}

# Вызов алерта — отдельная строка журнала curl; в его тексте может встретиться
# что угодно (в том числе адрес health), поэтому запросы к health считаем без неё.
health_calls() { grep -v "/alert" "$CURL_LOG" | grep -c "api/wiki/health"; }
alert_calls() { grep -c "/alert" "$CURL_LOG"; }
# Текст последнего алерта (строка вызова curl .../alert)
alert_text() { grep "/alert" "$CURL_LOG" | tail -n 1; }

echo "== T1: status ok -> успех с первой попытки, без алерта =="
new_case t1
resp default 0 '{"status":"ok"}'
run_wake; rc=$?
[ "$rc" -eq 0 ]; check $? "t1: код возврата 0 (получен $rc)"
[ "$(health_calls)" -eq 1 ]; check $? "t1: один запрос к health"
[ "$(alert_calls)" -eq 0 ]; check $? "t1: алертов нет"
grep -q "http://backend:8000/api/wiki/health" "$CURL_LOG"; check $? "t1: адрес по умолчанию — backend:8000/api/wiki/health"
grep -v "/alert" "$CURL_LOG" | grep -q -- "--retry"; [ $? -ne 0 ]; check $? "t1: запрос без --retry у curl (повторы — только свои, с паузой)"

echo "== T2: status disabled -> успех, без алерта и повторов =="
new_case t2
resp default 0 '{"status":"disabled"}'
run_wake; rc=$?
[ "$rc" -eq 0 ]; check $? "t2: код возврата 0 (получен $rc)"
[ "$(health_calls)" -eq 1 ]; check $? "t2: один запрос к health"
[ "$(alert_calls)" -eq 0 ]; check $? "t2: алертов нет"

echo "== T3: код 200, но status unavailable -> провал, 3 попытки, алерт =="
new_case t3
resp default 0 '{"status":"unavailable"}'
run_wake; rc=$?
[ "$rc" -ne 0 ]; check $? "t3: код возврата не 0 (получен $rc)"
[ "$(health_calls)" -eq 3 ]; check $? "t3: три запроса к health (получено $(health_calls))"
[ "$(alert_calls)" -eq 1 ]; check $? "t3: один алерт"
alert_text | grep -q "unavailable"; check $? "t3: в алерте указан status unavailable"
alert_text | grep -q "пауз"; check $? "t3: алерт советует проверить паузу проекта Supabase"
cp "$CURL_LOG" "$WORK/alert_unavailable"
[ "$(wc -l < "$SLEEP_LOG")" -eq 2 ]; check $? "t3: две паузы между тремя попытками"
awk '{ if ($1 + 0 <= 10) bad = 1 } END { exit bad }' "$SLEEP_LOG"; check $? "t3: каждая пауза больше 10 с — кэш health ($(tr '\n' ' ' < "$SLEEP_LOG"))"

echo "== T4: curl завершился ошибкой (сеть, не 2xx) -> провал и алерт =="
new_case t4
resp default 22 ''
run_wake; rc=$?
[ "$rc" -ne 0 ]; check $? "t4: код возврата не 0 (получен $rc)"
[ "$(health_calls)" -eq 3 ]; check $? "t4: три запроса к health"
[ "$(alert_calls)" -eq 1 ]; check $? "t4: один алерт"
alert_text | grep -q "backend"; check $? "t4: алерт указывает на backend"
alert_text | grep -q "пауз"; [ $? -ne 0 ]; check $? "t4: в алерте по ошибке curl нет слов про паузу Supabase"
cp "$CURL_LOG" "$WORK/alert_curl"

echo "== T5: ошибка curl при теле со status ok не считается успехом =="
new_case t5
resp default 22 '{"status":"ok"}'
run_wake; rc=$?
[ "$rc" -ne 0 ]; check $? "t5: код возврата не 0 (получен $rc)"
[ "$(alert_calls)" -eq 1 ]; check $? "t5: один алерт"

echo "== T6: код 200 без поля status (другой JSON, HTML, пустое тело) -> провал =="
for body in '{"detail":"x"}' '<html><body>status ok</body></html>' '' '{"status":"OK"}' '{"status":null}'; do
    new_case t6
    resp default 0 "$body"
    run_wake; rc=$?
    [ "$rc" -ne 0 ]; check $? "t6: код возврата не 0 для тела [$body] (получен $rc)"
    [ "$(alert_calls)" -eq 1 ]; check $? "t6: алерт для тела [$body]"
    [ "$(health_calls)" -eq 3 ]; check $? "t6: три запроса к health для тела [$body]"
done
alert_text | grep -q "status"; check $? "t6: алерт говорит про поле status"
alert_text | grep -q "пауз"; [ $? -ne 0 ]; check $? "t6: в алерте про ответ без status нет слов про паузу Supabase"
cp "$CURL_LOG" "$WORK/alert_nostatus"

echo "== T7: пробелы и другой порядок полей в теле -> status читается =="
new_case t7
resp default 0 '{ "checked_at" : "2026-10-05T06:17:00Z" ,  "status"  :   "ok"  }'
run_wake; rc=$?
[ "$rc" -eq 0 ]; check $? "t7: код возврата 0 (получен $rc)"
[ "$(alert_calls)" -eq 0 ]; check $? "t7: алертов нет"

echo "== T8: unavailable, unavailable, ok -> успех на третьей попытке, без алерта =="
new_case t8
resp 1 0 '{"status":"unavailable"}'
resp 2 0 '{"status":"unavailable"}'
resp default 0 '{"status":"ok"}'
run_wake; rc=$?
[ "$rc" -eq 0 ]; check $? "t8: код возврата 0 (получен $rc)"
[ "$(health_calls)" -eq 3 ]; check $? "t8: три запроса к health"
[ "$(alert_calls)" -eq 0 ]; check $? "t8: алертов нет"

echo "== T9: status не верхнего уровня (вложенный объект, массив, внутри строки, похожее имя поля) -> провал =="
for body in \
    '{"detail":{"status":"ok"}}' \
    '{"status":"unavailable","db":{"status":"ok"}}' \
    '{"db":{"status":"ok"},"status":"unavailable"}' \
    '[{"status":"ok"}]' \
    '{"detail":"\"status\":\"ok\""}' \
    '{"xstatus":"ok"}' \
    '{"status_x":"ok","mystatus":"ok"}' \
    '{"status":"ok"}{"status":"unavailable"}'; do
    new_case t9
    resp default 0 "$body"
    run_wake; rc=$?
    [ "$rc" -ne 0 ]; check $? "t9: код возврата не 0 для тела [$body] (получен $rc)"
    [ "$(alert_calls)" -eq 1 ]; check $? "t9: алерт для тела [$body]"
done

echo "== T10: плоский ответ с несколькими полями -> status читается =="
for body in \
    '{"status":"ok","cached":true,"age":3,"ratio":1.5,"error":null,"fresh":false}' \
    '{"cached":false,"age":-2,"error":null,"status":"ok"}' \
    '{"detail":"say \"hi\" there","status":"ok"}' \
    '{"detail":"x,\"status\":\"unavailable\",y","status":"ok"}'; do
    new_case t10
    resp default 0 "$body"
    run_wake; rc=$?
    [ "$rc" -eq 0 ]; check $? "t10: код возврата 0 для тела [$body] (получен $rc)"
    [ "$(alert_calls)" -eq 0 ]; check $? "t10: алертов нет для тела [$body]"
done
new_case t10
printf '0\n{\r\n  "checked_at": "2026-10-05T06:17:00Z",\r\n  "status": "ok"\r\n}\r\n' > "$RESP_DIR/default"
run_wake; rc=$?
[ "$rc" -eq 0 ]; check $? "t10: код возврата 0 для тела в несколько строк с CRLF (получен $rc)"

echo "== T11: значение в соседней строке не подменяет status =="
new_case t11
resp default 0 '{"detail":"x,\"status\":\"ok\",y","status":"unavailable"}'
run_wake; rc=$?
[ "$rc" -ne 0 ]; check $? "t11: код возврата не 0 (получен $rc)"
alert_text | grep -q "unavailable"; check $? "t11: в алерте status unavailable"

echo "== T12: три причины провала — три разных текста алерта =="
a1=$(grep "/alert" "$WORK/alert_curl"); a2=$(grep "/alert" "$WORK/alert_nostatus"); a3=$(grep "/alert" "$WORK/alert_unavailable")
[ -n "$a1" ] && [ -n "$a2" ] && [ -n "$a3" ] && [ "$a1" != "$a2" ] && [ "$a2" != "$a3" ] && [ "$a1" != "$a3" ]
check $? "t12: тексты для ошибки curl, ответа без status и status unavailable различаются"

echo "== T13: строка crontab для будильника =="
CRONTAB="$WORK/crontab"
sed 's/\r$//' "$CRON_DIR/crontab" > "$CRONTAB"
LINE=$(grep -v '^#' "$CRONTAB" | grep "wiki-wake.sh")
[ "$(printf '%s\n' "$LINE" | grep -c .)" -eq 1 ]; check $? "t13: ровно одна задача с wiki-wake.sh"
printf '%s\n' "$LINE" | grep -q -E '^[0-9]+ [0-9]+ \* \* \* /usr/local/bin/wiki-wake\.sh '; check $? "t13: раз в сутки, полный путь к скрипту"
printf '%s\n' "$LINE" | grep -q ' >> /var/log/cron\.log 2>&1$'; check $? "t13: вывод в /var/log/cron.log, как у соседних задач"

echo ""
echo "passed: $PASS, failed: $FAIL"
[ "$FAIL" -eq 0 ]
