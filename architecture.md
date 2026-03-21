# Architecture Decision Record — home-page

## Обзор проекта

Семейный веб-сервис с голосованием за ужин. Пользователи могут просматривать рецепты, добавлять свои, голосовать за вариант ужина на день — через веб-интерфейс или Telegram-бота.

---

## Инфраструктура

### Хостинг
- **Провайдер:** VPS у стороннего провайдера
- **Конфигурация:** 1 vCPU × 3.3 ГГц, 2 ГБ RAM, 30 ГБ NVMe, 1 Гбит/с
- **ОС:** Ubuntu 24.04 LTS

### Управление конфигурацией
- **Ansible** — provisioning ВМ, установка Docker, настройка firewall, генерация `.env` файлов
- Terraform не используется (избыточен для одной ВМ)

### Управление секретами
| Место хранения | Назначение |
|---|---|
| **Ansible Vault** | Секреты для provisioning (пароли БД, ключи) |
| **GitHub Actions Secrets** | Токены CI/CD (Docker Hub, SSH-ключ для деплоя) |
| **`.env` на ВМ** | Runtime-секреты для Docker Compose (генерируется Ansible из шаблона) |

### Контейнеризация
- **Docker** + **Docker Compose** — запуск и управление всеми сервисами
- **Docker Swarm не используется** — избыточен для одной ВМ
- **Docker Hub** — реестр образов (пространство имён: `mrtelnor`)

### Reverse Proxy и SSL
- **Traefik v3** — reverse proxy с автоматическим обнаружением Docker-контейнеров через labels
- **Let's Encrypt** — автоматическое получение и обновление SSL-сертификатов

### CI/CD
- **GitHub Actions** — пайплайны сборки, тестирования и деплоя
- **Репозиторий:** `github.com/mrTelnor/home-page` (Public, монорепо)
- Флоу: push → тесты → сборка образов → push на Docker Hub → SSH деплой на ВМ

### Мониторинг
- **Prometheus** — сбор метрик
- **Grafana** — визуализация метрик и дашборды
- **Loki** — агрегация логов контейнеров
- **Portainer** — управление Docker-контейнерами через UI

---

## Приложение — Dinner Vote

### Бэкенд
- **Язык:** Python 3.12+
- **Фреймворк:** FastAPI (async)
- **ORM:** SQLAlchemy 2.0 (async)
- **Миграции:** Alembic
- **Валидация:** Pydantic v2

### База данных
- **PostgreSQL 16** — основная БД для всех данных проекта и пользователей
- Разделение по схемам: `auth` (пользователи, сессии) и `dinner` (рецепты, голосования)

### Схема БД

```
Схема: auth
├── users          (id, tg_id, username, email, password_hash, role, created_at)
└── sessions       (id, user_id, token, expires_at)

Схема: dinner
├── recipes        (id, title, description, author_id, created_at, updated_at)
├── ingredients    (id, recipe_id, name, amount, unit)
├── daily_menus    (id, date, recipe_ids[])
└── votes          (id, user_id, recipe_id, menu_date, created_at)
```

### Авторизация
- **JWT токены** — единый механизм для веба и Telegram
- Веб: логин/пароль → JWT в httpOnly cookie
- Telegram: идентификация по `tg_id` → привязка к аккаунту → JWT внутри бота

### Telegram-бот
- **Aiogram 3** (async)
- Функции: просмотр вариантов ужина, голосование, добавление рецептов

### Фронтенд
- **React 18** + **Vite**
- **React Router** — навигация
- **TanStack Query** — работа с API, кэширование
- **Zustand** — управление состоянием
- **Tailwind CSS** — стилизация

---

## Структура монорепо

```
home-page/
├── backend/                  # FastAPI приложение
│   ├── app/
│   │   ├── api/              # Роутеры
│   │   ├── core/             # Конфиг, безопасность
│   │   ├── db/               # Модели, сессия БД
│   │   ├── schemas/          # Pydantic схемы
│   │   └── services/         # Бизнес-логика
│   ├── alembic/              # Миграции
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 # React приложение
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── store/
│   ├── Dockerfile
│   └── package.json
├── bot/                      # Telegram-бот
│   ├── app/
│   │   ├── handlers/
│   │   └── services/
│   ├── Dockerfile
│   └── requirements.txt
├── infra/
│   ├── ansible/              # Provisioning ВМ
│   │   ├── playbooks/
│   │   ├── roles/
│   │   └── inventory/
│   └── docker/
│       ├── docker-compose.yml
│       ├── docker-compose.monitoring.yml
│       └── traefik/
└── .github/
    └── workflows/
        ├── backend.yml
        ├── frontend.yml
        └── bot.yml
```

---

## Общая архитектура

```
┌─────────────────┐     ┌─────────────────┐
│  Telegram Bot   │     │  React Frontend │
│   (Aiogram 3)   │     │  (Vite + TS)    │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │ HTTPS / REST API
              ┌──────▼──────┐
              │   Traefik   │  ← SSL termination
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │   FastAPI   │
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │ PostgreSQL  │
              └─────────────┘

Мониторинг:
Prometheus → Grafana
Loki (логи) → Grafana
Portainer (Docker UI)
```

---

## Принятые решения (ADR)

| Решение | Выбор | Отклонённые варианты | Причина |
|---|---|---|---|
| Оркестрация | Docker Compose | Kubernetes, Docker Swarm | Одна ВМ, избыточность |
| БД | PostgreSQL | MongoDB | Реляционные данные, связи между сущностями |
| Бэкенд | FastAPI | Django, Flask | Async, скорость, автодокументация |
| Фронтенд | React + Vite | Vue 3, HTMX | Экосистема, перспективы развития |
| Прокси | Traefik | HAProxy, Nginx | Автообнаружение Docker-контейнеров, автоSSL |
| CI/CD | GitHub Actions | GitLab CI, Forgejo | Бесплатно, не тратит ресурсы ВМ |
| Конфиг ВМ | Ansible | Terraform + Ansible | Terraform избыточен для одной ВМ |
| Образы | Docker Hub | GHCR, self-hosted Nexus | Простота, бесплатно |
