# Traefik + Docker Compose — Design Spec

## Обзор

Базовая инфраструктура Docker Compose для проекта home-page: Traefik v3 как reverse proxy с автоматическим SSL, PostgreSQL 16, Portainer CE. Доступ к PostgreSQL — через десктопный клиент (pgAdmin на ПК), порт 5432 открыт только для домашнего IP.

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
- Порты: 5432 проброшен на хост (доступ ограничен firewalld по IP)
- Volumes: `pg_data` для персистентности
- Сети: `internal`
- Переменные: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` из `.env`

### 3. Portainer CE

- Образ: `portainer/portainer-ce`
- Доступ: `portainer.telnor.ru`
- Ограничение по IP: Traefik middleware `ipAllowList` (`93.100.230.103`)
- Volumes: `docker.sock` (read-only), `portainer_data`
- Сети: `web`

## Сети

- `web` — внешняя сеть для Traefik и сервисов с публичным доступом
- `internal` — внутренняя сеть для PostgreSQL и сервисов, которым нужна БД

## Поддомены

| Поддомен | Сервис | Ограничение по IP |
|---|---|---|
| `traefik.telnor.ru` | Дашборд Traefik | да, Traefik middleware (`93.100.230.103`) |
| `portainer.telnor.ru` | Portainer CE | да, Traefik middleware (`93.100.230.103`) |

Остальные поддомены (`telnor.ru`, `api.telnor.ru`, `grafana.telnor.ru`) добавляются по мере появления сервисов.

## Доступ к PostgreSQL

Порт 5432 открыт в firewalld только для домашнего IP `93.100.230.103`. Подключение через десктопный клиент (pgAdmin, DBeaver и т.д.):

- **Host**: `147.45.183.98`
- **Port**: `5432`
- **User/Password**: из `.env`

## Ограничение по IP

- **Traefik middleware `ipAllowList`** — дашборд Traefik и Portainer доступны только с `93.100.230.103`
- **Firewalld rich rule** — порт 5432 (PostgreSQL) открыт только для `93.100.230.103`

## Секреты (.env)

```
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
DOMAIN=telnor.ru
ACME_EMAIL=mrtelnor@gmail.com
HOME_IP=93.100.230.103
```

Пример хранится в `.env.example`. Реальный `.env` не попадает в git.
