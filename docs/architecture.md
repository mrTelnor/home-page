# Architecture Decision Record — home-page

## Обзор проекта

Семейный веб-сервис с голосованием за ужин. Пользователи добавляют рецепты, предлагают варианты ужина, голосуют. Первое приложение в семейном портале.

---

## Инфраструктура

### Хостинг
- **Провайдер:** Timeweb Cloud (VPS)
- **Конфигурация:** 1 vCPU × 3.3 ГГц, 2 ГБ RAM, 30 ГБ NVMe
- **ОС:** Ubuntu 24.04 LTS

### Управление конфигурацией
- **Ansible** — provisioning ВМ, установка Docker, настройка firewalld, генерация `.env` из Vault, синхронизация кода (rsync)
- Terraform не используется (избыточен для одной ВМ)

### Управление секретами
| Место хранения | Назначение |
|---|---|
| **Ansible Vault** | Все секреты проекта (см. README) |
| **`.env` на ВМ** | Runtime-секреты для Docker Compose (генерируется Ansible из шаблона) |

### Контейнеризация
- **Docker** + **Docker Compose** — управление всеми сервисами
- **Docker Swarm/Kubernetes** — не используется (избыточно для одной ВМ)
- Образы собираются на ВМ (без push в registry)

### Reverse Proxy и SSL
- **Traefik v3.6** — reverse proxy с автообнаружением Docker-контейнеров через labels
- **Let's Encrypt** — автоматическое получение и обновление SSL-сертификатов (HTTP challenge)
- IP-whitelist middleware для админ-панелей (Traefik, Portainer) и Swagger UI

### Firewall
- **firewalld** — порты 80/443/9922, PostgreSQL 5432 ограничен домашним IP через rich rule
- Docker-подсеть (172.16.0.0/12) в trusted zone

### Автоматизация
- **Cron-контейнер** (Alpine + curl) — вызывает backend-эндпоинты по расписанию с заголовком `X-Cron-Secret`
- Расписание: 08:00/13:00/17:00 GMT+3 для цикла голосования

### Управление
- **Portainer CE** — веб-UI для управления Docker-контейнерами, ограничен по IP

---

## Приложение — Dinner Vote

### Бэкенд
- **Язык:** Python 3.12
- **Фреймворк:** FastAPI (async), CORSMiddleware для кросс-доменных запросов
- **ORM:** SQLAlchemy 2.0 (async, asyncpg)
- **Миграции:** Alembic (async, запускаются при старте контейнера)
- **Валидация:** Pydantic v2, pydantic-settings

### База данных
- **PostgreSQL 16** — основная БД для всех данных
- Разделение по схемам: `auth` (пользователи, сессии) и `dinner` (рецепты, голосования)

### Схема БД

```
Схема: auth
├── users          (id, tg_id, username, email, password_hash, role,
│                   first_name, birthday, is_volkov, gender, created_at)
└── sessions       (id, user_id, token, expires_at)

Схема: dinner
├── recipes            (id, title, description, servings, author_id, created_at, updated_at)
├── ingredients        (id, recipe_id, name, amount, unit)
├── daily_menus        (id, date, status, winner_recipe_id, created_at)
├── daily_menu_recipes (id, menu_id, recipe_id, source, added_by)
└── votes              (id, user_id, menu_id, recipe_id, created_at)
```

- `daily_menus.status`: `collecting` → `voting` → `closed`
- `daily_menu_recipes.source`: `random` | `user`
- `votes` — unique constraint (user_id, menu_id): один голос на меню
- `users.gender`: `male` | `female` (для будущих оповещений и склонений)
- `users.is_volkov`: фамилия Волков/Волкова
- Username нормализуется в lowercase (регистронезависимость)

### Авторизация
- **JWT токены** с HS256 (python-jose), срок 7 дней
- **httpOnly cookie** для веба — cookie отправляется автоматически
- **Регистрация по инвайт-коду** (в Ansible Vault)
- **Пароль** — bcrypt (passlib + bcrypt 4.0 pinned), смена через `/profile`
- **Роли:** `user` (по умолчанию), `admin`
- **Привязка Telegram** через Login Widget на странице `/profile` (HMAC-проверка через `TELEGRAM_BOT_TOKEN`)
- Cron использует `X-Cron-Secret` вместо JWT
- Бот использует `X-Bot-Secret` для получения JWT по `tg_id` (`POST /api/auth/telegram-login`)

### Фронтенд
- **React 18** + **Vite** + **TypeScript**
- **React Router v7** — навигация (ProtectedRoute для защищённых маршрутов)
- **TanStack Query v5** — работа с API, кэширование, polling
- **Zustand** — хранение текущего пользователя
- **Tailwind CSS v4** + **shadcn/ui (Radix)** — стилизация и компоненты
- **Nginx** (alpine) — раздача собранного бандла с SPA fallback

---

## Структура монорепо

```
home-page/
├── backend/
│   ├── app/
│   │   ├── api/              # Роутеры (auth, recipes, menus, health)
│   │   ├── core/             # Конфиг, безопасность (JWT, bcrypt), dependencies, db
│   │   ├── db/
│   │   │   ├── base.py       # DeclarativeBase + mixins
│   │   │   └── models/       # User, Session, Recipe, Ingredient, DailyMenu, DailyMenuRecipe, Vote
│   │   ├── schemas/          # Pydantic-схемы
│   │   └── services/         # Бизнес-логика (auth, recipe, menu)
│   ├── alembic/              # Миграции
│   ├── tests/
│   ├── entrypoint.sh         # Alembic upgrade + uvicorn
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/              # fetch-клиент
│   │   ├── components/       # Layout, ProtectedRoute, VoteWidget, MenuCollecting/Voting/Results, RecipeForm, SuggestRecipeDialog, TelegramLoginButton, ChangePasswordDialog, ProfileForm, ui/ (shadcn)
│   │   ├── hooks/            # useAuth, useMenu, useRecipes, useProfile, usePageTitle
│   │   ├── pages/            # Login, Register, Home, Vote, VoteHistory, Recipes, RecipeNew/Detail/Edit, Profile, NotFound
│   │   └── store/            # auth (Zustand)
│   ├── nginx.conf
│   ├── Dockerfile
│   └── package.json
├── infra/
│   ├── ansible/              # Provisioning ВМ, деплой
│   │   ├── playbooks/        # initial-setup.yml, setup.yml
│   │   ├── roles/            # sshd, firewalld, docker, app
│   │   └── inventory/        # hosts.yml, group_vars/all/vault.yml
│   └── docker/
│       ├── docker-compose.yml
│       ├── cron/             # Cron-контейнер (Dockerfile, crontab)
│       └── traefik/
└── docs/
    ├── architecture.md
    └── api.md
```

---

## Общая архитектура

```
                 ┌─────────────────────────────────┐
                 │          Браузер                │
                 │  telnor.ru / api.telnor.ru      │
                 └──────────────┬──────────────────┘
                                │ HTTPS
                         ┌──────▼──────┐
                         │   Traefik   │  ← SSL termination, роутинг по hostname
                         │     v3.6    │  ← IP-whitelist для admin-панелей
                         └──┬────┬──┬──┘
                            │    │  │
                 ┌──────────┘    │  └─────────┐
                 │               │            │
          ┌──────▼──────┐ ┌──────▼──────┐ ┌───▼──────┐
          │  Frontend   │ │   Backend   │ │Portainer │
          │   (Nginx)   │ │  (FastAPI)  │ │   CE     │
          └─────────────┘ └──────┬──────┘ └──────────┘
                                 │
                                 │ asyncpg
                          ┌──────▼──────┐
                          │ PostgreSQL  │
                          │  (schemas:  │
                          │ auth, dinner)│
                          └─────────────┘

      ┌───────────┐ HTTP + X-Cron-Secret
      │   Cron    ├─────────────────────→ Backend API (create-daily, finalize, close-voting)
      │ (Alpine)  │ по расписанию GMT+3
      └───────────┘
```

---

## Принятые решения (ADR)

| Решение | Выбор | Отклонённые варианты | Причина |
|---|---|---|---|
| Оркестрация | Docker Compose | Kubernetes, Docker Swarm | Одна ВМ, избыточность |
| БД | PostgreSQL | MongoDB | Реляционные данные, FK-constraints |
| Бэкенд | FastAPI | Django, Flask | Async, Swagger из коробки |
| Фронтенд | React + Vite | Vue 3, HTMX | Экосистема, shadcn/ui |
| UI-библиотека | shadcn/ui (Radix) | MUI, Ant Design | Кастомизация через Tailwind, компоненты внутри проекта |
| State | Zustand + TanStack Query | Redux, Context | Минимум boilerplate |
| Прокси | Traefik | HAProxy, Nginx | Автообнаружение Docker, автоSSL |
| Конфиг ВМ | Ansible | Terraform + Ansible | Terraform избыточен для одной ВМ |
| Образы | Build на ВМ | Docker Hub, GHCR | MVP, без CI/CD |
| Firewall | firewalld | UFW | Rich rules (IP-whitelist для PostgreSQL), trusted zone для Docker |
| JWT storage | httpOnly cookie | localStorage + Bearer | Защита от XSS |
| Расписание | Cron-контейнер | Celery Beat, APScheduler | Простота, изоляция от приложения |
