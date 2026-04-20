FROM alpine:3.21

RUN apk add --no-cache curl postgresql16-client

COPY crontab /etc/crontabs/root
COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

CMD ["crond", "-f", "-l", "2"]
