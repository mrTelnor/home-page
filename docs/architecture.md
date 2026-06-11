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
- **Селективный деплой через теги** — каждый сервис помечен тегом (`backend`, `frontend`, `bot`, `cron`), у каждого свой handler; `--tags bot` пересоздаёт только bot-контейнер. Без тегов — полный деплой
- **Handler'ы вызывают `docker compose` напрямую** через shell-модуль (а не `community.docker.docker_compose_v2`) — модуль падает на post-action `compose images --format json` при `--build --force-recreate`. Прямой вызов стабилен
- **Автоочистка dangling-образов** — `docker image prune -f` запускается с тегом `always` перед каждым деплоем, чтобы образы не копились на диске

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

### VPN для бота
- **WireGuard** на ВМ (роль `vpn` в Ansible) — обходит блокировки Telegram API из РФ
- `AllowedIPs` ограничены только подсетями Telegram (149.154.160.0/20, 91.108.4.0/22 и др.) — остальной трафик идёт напрямую
- Endpoint — узел VPN-сервиса (с 2026-06 — Казахстан, `kz-2`; ключи и endpoint в Vault: `vault_wg_*`)
- ⚠️ При замене конфига от провайдера переносить только ключи и Endpoint: строка `DNS=` переключает системный DNS всей ВМ на резолверы провайдера и ломает резолвинг (инцидент 2026-06-10, бот лежал 2 суток). Смерть пира ловится монитором `GET /healthz` бота

### Telegram-бот
- **Aiogram 3** (async) — polling mode, отдельный Docker-сервис
- Общается с backend API через httpx (`http://backend:8000`) с JWT авторизацией
- Команды: `/menu`, `/vote`, `/suggest`, `/recipes`, `/schedule`, `/mute`, `/unmute`, `/start`, `/help`
- Aiohttp-сервер на `:8080` (модуль `webserver.py`, отделён от polling-логики):
  - `GET /healthz` — реальная связность с Telegram (`get_me`): 200/503; цель для внешнего uptime-монитора — ловит «HTTP жив, polling мёртв»
  - `POST /alert` (X-Cron-Secret) — рассылка произвольного текста админам; канал алертов cron (провал бэкапа)
  - `POST /notify` (X-Cron-Secret) — рассылка уведомлений меню, вызывается cron
  - `POST /uptime-alert?secret=...` — алерты от HetrixTools админам
  - `POST /check-calendar` (X-Cron-Secret) — почасовые напоминания и встроенные reminders из Google Calendar; `?digest=true` — утренний дайджест на сегодня и завтра; `?force=true` — игнорировать дедупликацию. Каждый тик также проверяет статус сегодняшнего меню и досылает `voting_opened`/`voting_closed`, если разовый cron-вызов `/notify` пропал — дедуп по menu_id предотвращает дубли
- **Google Calendar** через service account (`google-api-python-client`): чтение нескольких календарей, рассылка админам почасовых напоминаний, встроенных reminders из событий, дайджеста в 08:00 (вместе с меню). Для событий с `useDefault=true` (рекуррентные, настройки уведомлений на уровне календаря — service account не видит реальные минуты) применяются дефолты из env `CALENDAR_DEFAULT_REMINDERS_MIN` (по умолчанию `30`, поддерживается список через запятую). Дедуп через persistent JSON-файл в Docker volume `bot_data:/data`
- JWT кэшируется в памяти (dict `{tg_id: token}`), обновляется при 401

### Автоматизация (cron-контейнер)
- **Alpine + curl + postgresql-client** — вызывает backend-эндпоинты по расписанию с заголовком `X-Cron-Secret`, затем `/notify` эндпоинт бота для рассылки уведомлений
- Расписание (GMT+3):
  - 03:00 — бэкап БД (`pg_dump -Fc | gzip` → Яндекс.Диск WebDAV, ротация 14 дней)
  - 08:00 — `create-daily` + уведомление о меню для не-админов + утренний дайджест админам (расписание Google Calendar + меню)
  - 13:00 — `finalize` + `voting_opened`
  - 17:00 — `close-voting` + `voting_closed`
  - каждые 5 минут — `/check-calendar` (часовые reminders, custom reminders, catch-up для voting-уведомлений)

### Мониторинг
- **HetrixTools** (бесплатный тариф) — внешний uptime-мониторинг + blacklist-мониторинг
- Webhook-алерты приходят на `/uptime-alert` бота, рассылаются администраторам через Telegram

### DNS
- **Cloudflare** — глобальные authoritative NS для `telnor.ru` (перенесены с `registrant.ru`)
- DNS-запросы работают из любой точки мира, устойчивы к российским блокировкам

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
- **Логирование:** stdlib logging, уровень из env `LOG_LEVEL` (default INFO); ключевые события — старт, регистрация, жизненный цикл меню, неуспешные логины

### База данных
- **PostgreSQL 16** — основная БД для всех данных
- Разделение по схемам: `auth` (пользователи) и `dinner` (рецепты, голосования)
- Неиспользуемая таблица `auth.sessions` удалена миграцией 008 (сессии живут в JWT)

### Схема БД

```
Схема: auth
└── users          (id, tg_id, username, email, password_hash, role,
                    first_name, birthday, is_volkov, gender,
                    notifications_enabled, created_at)

Схема: dinner
├── recipes            (id, title, description, servings, author_id,
│                       glyph_kind, glyph_color, created_at, updated_at)
├── ingredients        (id, recipe_id, name, amount, unit)
├── daily_menus        (id, date, status, winner_recipe_id, created_at)
├── daily_menu_recipes (id, menu_id, recipe_id, source, added_by)
└── votes              (id, user_id, menu_id, recipe_id, created_at)
```

- `daily_menus.status`: `collecting` → `voting` → `closed`
- `daily_menu_recipes.source`: `random` | `user`
- `votes` — unique constraint (user_id, menu_id): один голос на меню
- `users.gender`: `male` | `female` (для оповещений и склонений)
- `users.is_volkov`: фамилия Волков/Волкова
- `users.notifications_enabled`: управление уведомлениями через бота (default: true)
- `recipes.glyph_kind` ∈ {`soup`, `noodles`, `eggs`, `pancakes`, `pelmeni`, `pie`, `pizza`, `salad`, `steak`, `chicken`, `toast`, `roast`, `shashlik`, `pot`, `bread`} — тип SVG-иконки. NULL → авто-выбор по хешу названия
- `recipes.glyph_color` ∈ {`red`, `orange`, `yellow`, `green`, `teal`, `blue`, `purple`, `pink`, `brown`, `cream`} — палитра иконки. NULL → авто-выбор
- Username нормализуется в lowercase (регистронезависимость)

### Авторизация
- **JWT токены** с HS256 (python-jose), срок 7 дней
- **httpOnly cookie** для веба — cookie отправляется автоматически
- **Bearer token** для бота — JWT в заголовке `Authorization: Bearer <token>`
- **Гостевой доступ** — `GET /api/recipes`, `GET /api/recipes/{id}`, `GET /api/recipes/search` открыты без авторизации (просмотр базы рецептов)
- **Регистрация по инвайт-коду** (в Ansible Vault)
- **Пароль** — bcrypt (passlib + bcrypt 4.0 pinned), смена через `/profile`
- **Роли:** `user` (по умолчанию), `admin`
- **Привязка Telegram** через Login Widget на странице `/profile` (HMAC-проверка через `TELEGRAM_BOT_TOKEN`)
- Cron использует `X-Cron-Secret` вместо JWT
- Бот использует `X-Bot-Secret` для получения JWT по `tg_id` (`POST /api/auth/telegram-login`) и списков пользователей (`/users/notifiable`, `/users/admins`)
- HetrixTools использует общий секрет (`?secret=...` в URL webhook'а) для вызова `/uptime-alert` бота

### Фронтенд
- **React 19** + **Vite** + **TypeScript**
- **React Router v7** — навигация (ProtectedRoute для защищённых маршрутов, AuthAwareRoute для гостевых)
- **TanStack Query v5** — работа с API, кэширование, polling
- **Zustand** — хранение текущего пользователя
- **Tailwind CSS v4** + **shadcn/ui (Radix)** — стилизация и компоненты
- **Дизайн-система** — cream-палитра «кулинарная книга» (paper `#F5EFE3` + ink `#1E1B14` + терракота `#B8442A`), тёмная тема (`localStorage` + `prefers-color-scheme`), шрифты Inter Tight + JetBrains Mono (Google Fonts), маскот-волк в SVG (`WolfMark`)
- **FoodGlyph** — компонент иконок блюд (15 SVG × 10 палитр) с пикером в форме рецепта
- **Nginx** (alpine) — раздача собранного бандла с SPA fallback

### Тестирование и CI

| Сервис | Тестов | Покрытие | Стек | Запуск локально |
|---|---|---|---|---|
| backend | 120 | 100% | pytest + httpx ASGI-клиент, реальный PostgreSQL | `cd backend && pytest` (нужен Postgres, `DATABASE_URL`) |
| bot | 163 | 99% | pytest + respx, AsyncMock, aiohttp TestClient | `cd bot && pytest tests` |
| frontend | 210 | ~97% | Vitest + React Testing Library, jsdom | `npm test` (в `frontend/`) |

- **CI (GitHub Actions):** на каждый PR — backend (ruff + pytest с Postgres-сервисом), bot (ruff + pytest), frontend (tsc + eslint + prettier-check + vitest + build); sonar.yml собирает покрытие всех трёх и шлёт в SonarCloud
- **SonarCloud:** quality gate по new code (coverage, рейтинги, дублирование); для PR от dependabot скан пропускается (нет Actions-секретов)
- **Dependabot:** weekly-PR на обновления pip/npm/actions; тестовая сетка — страховка для их merge
- Тесты не ходят в сеть: Telegram/Google/backend мокаются (respx, AsyncMock, fetch-моки)

---

## Структура монорепо

```
home-page/
├── backend/
│   ├── app/
│   │   ├── api/              # Роутеры (auth, recipes [публичные list/get/search + защищённые CUD], menus, health)
│   │   ├── core/             # Конфиг, безопасность (JWT, bcrypt), dependencies, db
│   │   ├── db/
│   │   │   ├── base.py       # DeclarativeBase + mixins
│   │   │   └── models/       # User, Recipe, Ingredient, DailyMenu, DailyMenuRecipe, Vote
│   │   ├── schemas/          # Pydantic-схемы
│   │   └── services/         # Бизнес-логика (auth, recipe, menu, telegram)
│   ├── alembic/              # Миграции
│   ├── tests/                # 120 integration/unit-тестов (pytest, реальный Postgres)
│   ├── entrypoint.sh         # Alembic upgrade + uvicorn
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/                  # *.test.ts(x) лежат рядом с кодом (210 тестов, Vitest + RTL)
│   │   ├── api/              # fetch-клиент, types.ts (общие API-типы), endpoints.ts (пути)
│   │   ├── components/       # Layout, ErrorBoundary, ProtectedRoute, AuthAwareRoute, VoteWidget, MenuCollecting/Voting/Results, RecipeForm (+IngredientsEditor, GlyphPicker), SuggestRecipeDialog, TelegramLoginButton, ChangePasswordDialog, ProfileForm, FoodGlyph, ui/ (shadcn)
│   │   ├── hooks/            # useAuth, useMenu, useRecipes, useProfile, useTheme, useLocalStorage, usePageTitle
│   │   ├── pages/            # Login, Register, Home, Vote, VoteHistory, Recipes, RecipeNew/Detail/Edit, Profile, NotFound
│   │   ├── store/            # auth (Zustand)
│   │   └── test/             # setup + утилиты рендера с провайдерами
│   ├── nginx.conf
│   ├── Dockerfile
│   └── package.json          # + Prettier, Vitest, ESLint
├── bot/
│   ├── app/
│   │   ├── main.py           # Wiring: Bot, Dispatcher, запуск polling + webserver
│   │   ├── webserver.py      # aiohttp-endpoints: /healthz, /alert, /notify, /uptime-alert, /check-calendar
│   │   ├── config.py         # Настройки из env
│   │   ├── api_client.py     # HTTP-клиент к backend: JWT-кэш, retry с backoff, get_today_menu
│   │   ├── notify.py         # Логика рассылки уведомлений
│   │   ├── calendar_service.py # Google Calendar: события, напоминания, дедуп, форматтеры
│   │   ├── callbacks.py      # Константы callback_data inline-кнопок
│   │   ├── helpers.py        # check_linked и пр.
│   │   └── handlers/         # start, menu, vote, suggest, recipes, notifications, schedule
│   └── tests/                # 163 теста (pytest: respx, AsyncMock, aiohttp TestClient)
├── infra/
│   ├── ansible/              # Provisioning ВМ, деплой
│   │   ├── playbooks/        # initial-setup.yml, setup.yml
│   │   ├── roles/            # sshd, firewalld, docker, vpn (WireGuard), app
│   │   └── inventory/        # hosts.yml, group_vars/all/vault.yml
│   └── docker/
│       ├── docker-compose.yml
│       ├── cron/             # Cron-контейнер (Dockerfile, crontab, backup.sh)
│       └── traefik/
├── .github/
│   ├── workflows/            # backend.yml, frontend.yml, bot.yml, sonar.yml
│   └── dependabot.yml        # weekly: pip (backend, bot), npm, actions
└── docs/
    ├── architecture.md       # этот документ
    ├── api.md                # справочник REST API с примерами
    ├── testing.md            # гайд ручного тестирования
    ├── eschool_decommission.md
    └── knowledge_base.md
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
                          └──────▲──────┘
                                 │ pg_dump
      ┌───────────┐ HTTP + X-Cron-Secret       │
      │   Cron    ├─────────────────────→ Backend API (create-daily, finalize, close-voting)
      │ (Alpine)  │ по расписанию GMT+3         │
      │           ├─────────────────────→ Bot /notify (уведомления в Telegram)
      │           ├─────────────────────→ Яндекс.Диск (WebDAV) — бэкапы, ротация 14 дней
      └───────────┘

      ┌───────────┐  polling (через WireGuard)  ┌──────────────┐
      │ Telegram  │ ←─────────────────────────── │     Bot      │
      │   API     │                              │ (Aiogram 3)  │
      └───────────┘                              └──────┬───────┘
                                                        │ HTTP + Bearer JWT
                                                        └──→ Backend API

      ┌──────────────┐   webhook (/uptime-alert)
      │ HetrixTools  ├──────────────────→ Bot → Telegram admin alerts
      │   (внешний)  │
      └──────────────┘

      ┌──────────────┐   service account (read-only)    ┌─────┐
      │ Google       │ ←──────────────────────────────── │ Bot │ → Telegram admin reminders
      │ Calendar API │                                   └─────┘
      └──────────────┘   опрос через cron каждые 5 мин
                         + утренний дайджест в 08:00 GMT+3
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
| DNS | Cloudflare | Регистратор (registrant.ru) | Глобальные NS, устойчивы к блокировкам |
| Хранение бэкапов | Яндекс.Диск (WebDAV) | S3, локальный volume | Нет дополнительной оплаты, 1 ТБ, просто через curl |
| Мониторинг | HetrixTools (внешний) | Self-hosted Uptime Kuma | Детектит падение всей ВМ |
| VPN для бота | WireGuard к VPS в DE | Прокси, полный VPN ВМ | Обход блокировок Telegram в РФ, только нужные подсети |
| Bot mode | Polling | Webhook | `telnor.ru` забанен на DNS-резолвере Telegram |
| Calendar API auth | Service account + sharing | OAuth per-user, iCal-фид | Минимум кода, без user flow; iCal кэшируется до 24 ч на стороне Google |
| Дедуп напоминаний | JSON-файл в Docker volume | БД, in-memory | Простота; данные переживают рестарт бота |
| Селективный деплой | Ansible tags + per-service handlers | Один общий handler | Быстрее деплой при работе над одним сервисом, готовность к росту числа сервисов |
| Catch-up voting-уведомлений | Идемпотентный poll в `/check-calendar` | Retry в curl, очередь, webhook | Self-healing при пропуске разового cron-вызова, дедуп по menu_id предотвращает дубли |
| Дефолтные напоминания календаря | Env `CALENDAR_DEFAULT_REMINDERS_MIN` для событий с `useDefault=true` | Per-user calendarList.defaultReminders, domain-wide delegation | Service account видит чужие default reminders как пустые; domain-delegation требует Google Workspace; глобальный дефолт «30» покрывает 95% семейных кейсов |
| Регенерация `.env` | Task с `tags: [always]` | Тег для каждого сервиса; рукотворный hook | `.env` влияет на все контейнеры; при `--tags bot/cron` обновление vault-переменных должно подхватываться автоматически. Handler срабатывает только при реальном изменении содержимого |
| Тесты backend | Integration на реальном Postgres | Моки сессий, SQLite | FK/unique/каскады — часть поведения; SQLite не знает схем auth/dinner |
| Обновление зависимостей | Dependabot (weekly, groups) | Renovate, вручную | Нативная интеграция GitHub; тестовая сетка делает merge безопасным |
| Алерты об отказах | Бот как канал (`/alert`, `/uptime-alert`, `/healthz`) | Отдельный alertmanager | Бот уже умеет рассылать админам; ноль новой инфраструктуры |
