# 🍽️ Home Page

Семейный домашний сервис. Первое приложение — **Dinner Vote**: голосование за ужин через веб-интерфейс или Telegram-бота.

## Возможности

- 📖 **База рецептов** — просматривай рецепты и добавляй свои
- 🗳️ **Голосование** — каждый день приложение предлагает варианты ужина, каждый член семьи голосует за понравившийся
- 🤖 **Telegram-бот** — голосуй прямо в Telegram, не заходя на сайт
- 🌐 **Веб-интерфейс** — полноценный сайт с авторизацией

## Стек технологий

| Слой | Технологии |
|---|---|
| Бэкенд | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic |
| База данных | PostgreSQL 16 |
| Фронтенд | React 18, Vite, Tailwind CSS, TanStack Query |
| Telegram-бот | Aiogram 3 |
| Инфраструктура | Docker, Docker Compose, Traefik, Ansible |
| CI/CD | GitHub Actions, Docker Hub |
| Мониторинг | Prometheus, Grafana, Loki, Portainer |

## Структура репозитория

```
home-page/
├── backend/      # FastAPI приложение
├── frontend/     # React приложение
├── bot/          # Telegram-бот
├── infra/        # Docker Compose, Ansible, Traefik
└── .github/      # GitHub Actions workflows
```

## Быстрый старт (локальная разработка)

> Требования: Docker, Docker Compose

```bash
git clone https://github.com/mrTelnor/home-page.git
cd home-page
cp infra/docker/.env.example infra/docker/.env
# Заполни .env своими значениями
docker compose -f infra/docker/docker-compose.yml up -d
```

- Фронтенд: http://localhost:3000
- API документация: http://localhost:8000/docs
- Portainer: http://localhost:9000

## Деплой на сервер

Подготовка ВМ через Ansible:

```bash
cd infra/ansible
ansible-playbook -i inventory/hosts.yml playbooks/setup.yml --ask-vault-pass
```

После этого CI/CD (GitHub Actions) автоматически деплоит новые версии при пуше в `main`.

## Архитектура

Подробные архитектурные решения описаны в [ARCHITECTURE.md](./ARCHITECTURE.md).

## Лицензия

MIT
