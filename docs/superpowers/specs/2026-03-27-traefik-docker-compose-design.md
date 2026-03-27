# Traefik + Docker Compose — Design Spec

## Обзор

Базовая инфраструктура Docker Compose для проекта home-page: Traefik v3 как reverse proxy с автоматическим SSL, PostgreSQL 16, pgAdmin, Portainer CE.

## Структура файлов

```
infra/docker/
├── docker-compose.yml
├── .env.example
└── traefik/
    └── traefik.yml
```

## Traefik (traefik.yml)

- **Entrypoints**: `web` (80) → редирект на `websecure` (443)
- **Let's Encrypt**: TLS resolver `letsencrypt`, email `mrtelnor@gmail.com`, хранение в `/letsencrypt/acme.json`
- **Провайдер**: Docker (автообнаружение через labels, `exposedByDefault: false`)
- **Дашборд**: включён, доступен на `traefik.telnor.ru`

## Docker Compose — сервисы

### 1. Traefik

- Образ: `traefik:v3.3`
- Порты: 80, 443
- Volumes: `docker.sock` (read-only), `traefik.yml`, volume для acme.json
- Сети: `web`

### 2. PostgreSQL 16

- Образ: `postgres:16`
- Порты: не проброшены наружу
- Volumes: `pg_data` для персистентности
- Сети: `internal`
- Переменные: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` из `.env`

### 3. pgAdmin

- Образ: `dpage/pgadmin4`
- Доступ: `pgadmin.telnor.ru`
- Ограничение по IP: `93.100.230.103`
- Сети: `web`, `internal`
- Переменные: `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD` из `.env`

### 4. Portainer CE

- Образ: `portainer/portainer-ce`
- Доступ: `portainer.telnor.ru`
- Ограничение по IP: `93.100.230.103`
- Volumes: `docker.sock` (read-only), `portainer_data`
- Сети: `web`

## Сети

- `web` — внешняя сеть для Traefik и сервисов с публичным доступом
- `internal` — внутренняя сеть для PostgreSQL и сервисов, которым нужна БД

## Поддомены

| Поддомен | Сервис | Ограничение по IP |
|---|---|---|
| `traefik.telnor.ru` | Дашборд Traefik | да (`93.100.230.103`) |
| `pgadmin.telnor.ru` | pgAdmin | да (`93.100.230.103`) |
| `portainer.telnor.ru` | Portainer CE | да (`93.100.230.103`) |

Остальные поддомены (`telnor.ru`, `api.telnor.ru`, `grafana.telnor.ru`) добавляются по мере появления сервисов.

## Ограничение по IP

Traefik middleware `ipWhiteList` — доступ к дашборду Traefik, pgAdmin и Portainer только с `93.100.230.103`.

## Секреты (.env)

```
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
PGADMIN_DEFAULT_EMAIL=
PGADMIN_DEFAULT_PASSWORD=
DOMAIN=telnor.ru
ACME_EMAIL=mrtelnor@gmail.com
HOME_IP=93.100.230.103
```

Пример хранится в `.env.example`. Реальный `.env` не попадает в git.
