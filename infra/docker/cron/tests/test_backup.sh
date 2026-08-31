#!/bin/sh
# Тесты backup.sh на стабах pg_dump/curl. Запускать в том же окружении, что и прод (alpine/busybox ash):
#   docker run --rm -v "$(pwd)/infra/docker/cron:/cron" alpine:3.21 sh /cron/tests/test_backup.sh
set -u

CRON_DIR="${CRON_DIR:-/cron}"
WORK=$(mktemp -d)
STUBS="$WORK/stubs"
mkdir -p "$STUBS"
PASS=0
FAIL=0

# ---------- стабы ----------

# pg_dump: пишет ~64К несжимаемых байт в файл из "-f <path>" (или в stdout,
# если -f не передан — так работал старый пайп-вариант). PG_DUMP_MODE=fail —
# имитирует обрыв: данные записаны, но код возврата 1.
cat > "$STUBS/pg_dump" <<'EOF'
#!/bin/sh
out=""
prev=""
for a in "$@"; do
    [ "$prev" = "-f" ] && out="$a"
    prev="$a"
done
if [ -n "$out" ]; then
    head -c 65536 /dev/urandom > "$out"
else
    head -c 65536 /dev/urandom
fi
[ "${PG_DUMP_MODE:-ok}" = "fail" ] && exit 1
exit 0
EOF

# curl: пишет каждый вызов строкой в $CURL_LOG.
# PROPFIND -> содержимое $PROPFIND_FILE; -T (upload) -> ошибка при наличии
# файла $UPLOAD_FAIL_FLAG; /alert и DELETE -> успех.
cat > "$STUBS/curl" <<'EOF'
#!/bin/sh
echo "$*" >> "$CURL_LOG"
case " $* " in
    *"/alert"*) exit 0 ;;
    *" PROPFIND "*)
        [ -n "${PROPFIND_FILE:-}" ] && [ -f "$PROPFIND_FILE" ] && cat "$PROPFIND_FILE"
        exit 0 ;;
    *" -T "*)
        [ -f "${UPLOAD_FAIL_FLAG:-/nonexistent}" ] && exit 22
        exit 0 ;;
    *" DELETE "*) exit 0 ;;
esac
exit 0
EOF
chmod +x "$STUBS/pg_dump" "$STUBS/curl"

# Как и Dockerfile: снимаем возможный CRLF из рабочей копии (правки с Windows).
sed 's/\r$//' "$CRON_DIR/backup.sh" > "$WORK/backup.sh"

# ---------- запуск и проверки ----------

# run_backup <pg_dump_mode> <backup_dir> <images_src> [upload_fail_flag] [propfind_file]
# Всё окружение передаётся явно через env — префиксные присваивания перед
# вызовом функции в ash протекают в последующие тесты.
run_backup() {
    env -i PATH="$STUBS:/usr/bin:/bin" \
        CURL_LOG="$CURL_LOG" \
        PG_DUMP_MODE="$1" \
        BACKUP_DIR="$2" \
        RECIPE_IMAGES_SRC="$3" \
        UPLOAD_FAIL_FLAG="${4:-}" \
        PROPFIND_FILE="${5:-}" \
        POSTGRES_USER=u POSTGRES_PASSWORD=p CRON_SECRET=s \
        YADISK_USER=y YADISK_APP_PASSWORD=ap \
        sh "$WORK/backup.sh"
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

TODAY=$(date +%Y-%m-%d)

echo "== T1: провал pg_dump не маскируется и даёт алерт =="
CURL_LOG="$WORK/t1.curl"
: > "$CURL_LOG"
mkdir -p "$WORK/imgs_t1" && echo x > "$WORK/imgs_t1/a.jpg"
run_backup fail "$WORK/b1" "$WORK/imgs_t1" > "$WORK/t1.out" 2>&1
rc=$?
[ "$rc" -ne 0 ]; check $? "t1: код возврата не 0 (получен $rc)"
grep -q "/alert" "$CURL_LOG"; check $? "t1: отправлен алерт"

echo "== T2: recipe_images архивируются и загружаются =="
CURL_LOG="$WORK/t2.curl"
: > "$CURL_LOG"
mkdir -p "$WORK/imgs_t2" && echo photo > "$WORK/imgs_t2/r1.jpg"
run_backup ok "$WORK/b2" "$WORK/imgs_t2" > "$WORK/t2.out" 2>&1
rc=$?
[ "$rc" -eq 0 ]; check $? "t2: успешное завершение (получен $rc)"
grep -q "recipe_images_${TODAY}\.tar\.gz" "$CURL_LOG"; check $? "t2: загрузка recipe_images_*.tar.gz"

echo "== T3: провал загрузки -> алерт и код 1, локальная копия остаётся =="
CURL_LOG="$WORK/t3.curl"
: > "$CURL_LOG"
touch "$WORK/t3.uploadfail"
mkdir -p "$WORK/imgs_t3" && echo x > "$WORK/imgs_t3/a.jpg"
run_backup ok "$WORK/b3" "$WORK/imgs_t3" "$WORK/t3.uploadfail" > "$WORK/t3.out" 2>&1
rc=$?
[ "$rc" -ne 0 ]; check $? "t3: код возврата не 0 (получен $rc)"
grep -q "/alert" "$CURL_LOG"; check $? "t3: отправлен алерт"
ls "$WORK/b3"/homepage_*.dump* > /dev/null 2>&1; check $? "t3: локальная копия дампа сохранена"

echo "== T4: ротация удаляет старые файлы всех форматов, свежие не трогает =="
CURL_LOG="$WORK/t4.curl"
: > "$CURL_LOG"
cat > "$WORK/t4.propfind" <<EOF
<d:multistatus>
homepage_2020-01-01.dump.gz
homepage_2020-01-02.dump
recipe_images_2020-01-03.tar.gz
homepage_${TODAY}.dump
recipe_images_${TODAY}.tar.gz
</d:multistatus>
EOF
mkdir -p "$WORK/imgs_t4" && echo x > "$WORK/imgs_t4/a.jpg"
run_backup ok "$WORK/b4" "$WORK/imgs_t4" "" "$WORK/t4.propfind" > "$WORK/t4.out" 2>&1
grep -q "DELETE .*homepage_2020-01-01\.dump\.gz" "$CURL_LOG"; check $? "t4: удалён старый .dump.gz (legacy)"
grep -q "DELETE .*homepage_2020-01-02\.dump" "$CURL_LOG"; check $? "t4: удалён старый .dump"
grep -q "DELETE .*recipe_images_2020-01-03\.tar\.gz" "$CURL_LOG"; check $? "t4: удалён старый архив фото"
! grep -q "DELETE .*${TODAY}" "$CURL_LOG"; check $? "t4: свежие файлы не удалены"

echo "== T5: успешный прогон — без алертов, загрузка с ретраями =="
CURL_LOG="$WORK/t5.curl"
: > "$CURL_LOG"
cat > "$WORK/t5.propfind" <<EOF
homepage_${TODAY}.dump
EOF
mkdir -p "$WORK/imgs_t5" && echo x > "$WORK/imgs_t5/a.jpg"
run_backup ok "$WORK/b5" "$WORK/imgs_t5" "" "$WORK/t5.propfind" > "$WORK/t5.out" 2>&1
rc=$?
[ "$rc" -eq 0 ]; check $? "t5: успешное завершение (получен $rc)"
! grep -q "/alert" "$CURL_LOG"; check $? "t5: алертов нет"
grep -q -- "-T .*homepage_${TODAY}\.dump" "$CURL_LOG"; check $? "t5: дамп загружен"
grep " -T " "$CURL_LOG" | grep -q -- "--retry"; check $? "t5: загрузка идёт с --retry"

echo ""
echo "passed: $PASS, failed: $FAIL"
[ "$FAIL" -eq 0 ]
