FROM alpine:3.21

RUN apk add --no-cache curl

COPY crontab /etc/crontabs/root

CMD ["crond", "-f", "-l", "2"]
