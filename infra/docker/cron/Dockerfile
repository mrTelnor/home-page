FROM alpine:3.21

RUN apk add --no-cache curl postgresql16-client

COPY crontab /etc/crontabs/root
COPY backup.sh /usr/local/bin/backup.sh
# Защита от CRLF: Ansible rsync'ит рабочую копию как есть, а правки с Windows
# могут принести \r. busybox crond/sh ломается на \r («redir error», bad
# interpreter) — снимаем перевод строки на этапе сборки.
RUN sed -i 's/\r$//' /etc/crontabs/root /usr/local/bin/backup.sh \
    && chmod +x /usr/local/bin/backup.sh

CMD ["crond", "-f", "-l", "2"]
