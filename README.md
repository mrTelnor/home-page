# 🍽️ Home Page

[![Backend CI](https://github.com/mrTelnor/home-page/actions/workflows/backend.yml/badge.svg)](https://github.com/mrTelnor/home-page/actions/workflows/backend.yml)
[![Frontend CI](https://github.com/mrTelnor/home-page/actions/workflows/frontend.yml/badge.svg)](https://github.com/mrTelnor/home-page/actions/workflows/frontend.yml)
[![Sonar Analysis](https://github.com/mrTelnor/home-page/actions/workflows/sonar.yml/badge.svg)](https://github.com/mrTelnor/home-page/actions/workflows/sonar.yml)

[![Quality Gate](https://sonarcloud.io/api/project_badges/measure?project=mrTelnor_home-page&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=mrTelnor_home-page)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=mrTelnor_home-page&metric=coverage)](https://sonarcloud.io/summary/new_code?id=mrTelnor_home-page)

Семейный домашний сервис. Первое приложение — **Dinner Vote**: голосование за ужин через веб-интерфейс и Telegram-бота.

**Прод:** [telnor.ru](https://telnor.ru) | **Бот:** [@volkov_homepage_bot](https://t.me/volkov_homepage_bot)

## Возможности

- 📖 **База рецептов** — добавление, редактирование, удаление рецептов с ингредиентами. Пересчёт ингредиентов под произвольное количество порций. Сортировка списка по алфавиту, дате добавления или дате изменения (запоминается в браузере). Каждый рецепт получает SVG-иконку (15 типов: суп / лапша / пицца / салат и т.д.) и цвет (10 палитр) — выбираются вручную или назначаются автоматически по хешу названия
- 🗳️ **Голосование за ужин** — ежедневно по расписанию (8:00 GMT+3) создаётся меню из 3 случайных рецептов, члены семьи могут предлагать свои варианты и голосовать. После голоса показывается счётчик участников и кнопка "Отменить голос". В 17:00 определяется победитель
- 📜 **История голосований** — прошлые меню с результатами
- 🤖 **Telegram-бот** — просмотр меню, голосование, предложение рецептов, уведомления о событиях (новое меню, открытие голосования, результаты). Настройка уведомлений per-user (`/mute`, `/unmute`). Поиск рецептов по названию через `/suggest`
- 📅 **Интеграция с Google Calendar** — бот читает несколько семейных календарей через service account и шлёт админам почасовые напоминания о событиях, поддерживает встроенные напоминания из календаря и календарные настройки `useDefault` (через env `CALENDAR_DEFAULT_REMINDERS_MIN`, по умолчанию `30`), утренний дайджест в 8:00 (вместе с меню) и команду `/schedule` для запроса расписания на сегодня и завтра по требованию
- 🔐 **Авторизация** — регистрация по инвайт-коду, JWT в httpOnly cookie (веб) и Bearer token (бот)
- 👁 **Гостевой доступ** — публичный просмотр базы рецептов без авторизации (без возможности редактировать/голосовать)
- 👤 **Личный кабинет** — личные данные (имя, день рождения, пол, фамилия Волков/Волкова), смена пароля, привязка Telegram через Login Widget
- 💾 **Бэкапы БД** — ежедневный `pg_dump` с ротацией 14 дней на Яндекс.Диск через WebDAV
- 📡 **Мониторинг** — HetrixTools отслеживает доступность `telnor.ru` и `api.telnor.ru`, алерты админам в Telegram
- 🌐 **Веб-интерфейс** — адаптивный UI с переключением светлой/тёмной темы, тёплая cream-палитра в духе кулинарной книги, маскот-волк (фамилия Волковы), валидация форм с подсветкой ошибок

## Стек технологий

| Слой | Технологии |
|---|---|
| Бэкенд | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2 |
| База данных | PostgreSQL 16 (схемы `auth`, `dinner`) |
| Фронтенд | React 19, Vite, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Zustand |
| Telegram-бот | Python 3.12, Aiogram 3 (polling), aiohttp, httpx, google-api-python-client |
| Автоматизация | Cron-контейнер (Alpine + curl + postgresql-client): расписание голосования, уведомления, бэкапы, проверка календаря |
| Инфраструктура | Docker, Docker Compose, Traefik v3 (Let's Encrypt), Ansible, Cloudflare DNS, WireGuard (VPN для бота) |
| Мониторинг | HetrixTools (uptime + blacklist), алерты в Telegram через бот |
| Хранилище бэкапов | Яндекс.Диск (WebDAV) |
| Управление | Portainer CE |

## Структура репозитория

```
home-page/
├── backend/              # FastAPI приложение
│   ├── app/              # Код приложения (api, core, db, schemas, services)
│   ├── alembic/          # Миграции БД
│   └── Dockerfile
├── frontend/             # React приложение
│   ├── src/              # Код (api, components, hooks, pages, store)
│   ├── Dockerfile        # multi-stage build (Node + Nginx)
│   └── nginx.conf
├── bot/                  # Telegram-бот (Aiogram 3)
│   ├── app/              # Код (handlers, api_client, notify, config)
│   └── Dockerfile
├── infra/
│   ├── ansible/          # Playbooks, roles (docker, vpn, app, firewalld), inventory
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   ├── cron/         # Cron-контейнер: расписание + бэкапы БД на Яндекс.Диск
│   │   └── traefik/
│   ├── prepare-vm.sh     # Первичная подготовка ВМ
│   ├── reset-vm.sh       # Сброс настроек ВМ
│   └── setup-wsl-ssh.sh  # Подготовка WSL для Ansible
└── docs/
    ├── architecture.md   # Архитектурные решения
    └── api.md            # Документация API
```

## Поддомены

| URL | Сервис | Доступ |
|---|---|---|
| `telnor.ru` | React-фронтенд | публично |
| `api.telnor.ru` | FastAPI backend | публично (Swagger `/docs` ограничен по IP) |
| `bot.telnor.ru` | Telegram-бот (HTTP endpoints для `/notify` и `/uptime-alert`) | публично |
| `traefik.telnor.ru` | Traefik dashboard | только с домашнего IP |
| `portainer.telnor.ru` | Portainer UI | только с домашнего IP |

DNS-записи домена управляются через **Cloudflare** (бесплатный тариф) — глобальные NS, устойчивее к блокировкам.

## Деплой на сервер

### 1. Подготовка WSL (Windows)

Ansible запускается из WSL. Перед началом скопируй SSH-ключ и настрой окружение:

```bash
bash infra/setup-wsl-ssh.sh
source ~/.bashrc
```

Скрипт копирует SSH-ключ и vault password в WSL, а также добавляет в `~/.bashrc`:

| Переменная | Значение | Описание |
|---|---|---|
| `ANSIBLE_CONFIG` | `.../infra/ansible/ansible.cfg` | Путь к конфигу Ansible (обход world-writable) |
| `ANSIBLE_ROLES_PATH` | `.../infra/ansible/roles` | Путь к ролям |
| `ANSIBLE_VAULT_PASSWORD_FILE` | `~/.vault_pass` | Пароль для Ansible Vault |

Переменные скрипта:

| Переменная | Значение по умолчанию | Описание |
|---|---|---|
| `WIN_KEY` | `/mnt/c/Users/telnor/.ssh/GitHub_SSH` | Путь к приватному SSH-ключу в Windows |
| `WSL_DIR` | `$HOME/.ssh` | Директория SSH в WSL |

### 2. Подготовка ВМ

На свежей ВМ (Ubuntu 24.04) запусти скрипт от root:

```bash
bash infra/prepare-vm.sh
```

| Переменная | Значение по умолчанию | Описание |
|---|---|---|
| `USERNAME` | `telnor` | Имя пользователя для подключения |
| `SSH_PUB_KEY` | `ssh-ed25519 AAAA...` | Публичный SSH-ключ пользователя |

Скрипт создаст пользователя с sudo, добавит SSH-ключ и установит зависимости для Ansible.

### 3. Первоначальная настройка (Ansible)

После подготовки ВМ запусти первичный плейбук (подключается на порт 22):

```bash
cd infra/ansible
ansible-playbook -i inventory/hosts.yml playbooks/initial-setup.yml
```

Плейбук настроит SSH (порт 9922, запрет паролей), firewall и Docker.

### 4. Последующие запуски

Все дальнейшие изменения — через основной плейбук (порт 9922):

```bash
cd infra/ansible
ansible-playbook -i inventory/hosts.yml playbooks/setup.yml
```

Плейбук автоматически:
- Синхронизирует код backend/frontend/bot/cron на ВМ (rsync с exclude node_modules/__pycache__)
- Генерирует `.env` из переменных Ansible Vault
- Пересобирает и перезапускает контейнеры при изменениях (build + recreate)

### 5. Селективный деплой через теги

Чтобы не пересобирать все контейнеры при изменении только одного сервиса, используй теги:

```bash
ansible-playbook -i inventory/hosts.yml playbooks/setup.yml --tags bot
```

Доступные теги: `backend`, `frontend`, `bot`, `cron`. Можно комбинировать: `--tags bot,backend`.

| Изменение | Команда |
|---|---|
| Только код бота (Python в `bot/app/`) | `--tags bot` |
| Только backend (Python в `backend/app/`, миграции) | `--tags backend` |
| Только frontend (React) | `--tags frontend` |
| Только cron (расписание, скрипты) | `--tags cron` |
| `docker-compose.yml`, `.env`, traefik | без тегов (полный деплой) |
| Несколько сервисов | `--tags bot,backend` |

Каждый тегированный сервис имеет свой handler (`Recreate bot`, `Recreate backend` и т.д.), который пересобирает и перезапускает только нужный контейнер. Изменения в общих файлах (`docker-compose.yml`, `.env`, `traefik.yml`) триггерят `Recreate all containers`.

Задача `Generate .env from vault variables` помечена тегом `always`, поэтому даже `--tags bot` (или любой другой) регенерирует `.env`, если в vault поменялись переменные. Handler `Recreate all containers` сработает только при реальном изменении содержимого `.env`.

Полезные служебные команды:

```bash
# показать список доступных тегов
ansible-playbook -i inventory/hosts.yml playbooks/setup.yml --list-tags

# увидеть какие задачи будут запущены (план без выполнения)
ansible-playbook -i inventory/hosts.yml playbooks/setup.yml --tags bot --list-tasks

# dry-run: что бы изменилось, без выполнения
ansible-playbook -i inventory/hosts.yml playbooks/setup.yml --tags bot --check
```

### Очистка Docker-образов

При каждом деплое плейбук автоматически выполняет `docker image prune -f` (задача `Prune dangling Docker images` с тегом `always`). Это убирает «осиротевшие» образы после rebuild и не даёт диску переполняться.

### Внутренности handler-ов

Для пересоздания контейнеров используется прямой вызов `docker compose up -d --build --force-recreate <service>` через shell-модуль Ansible. Раньше использовался `community.docker.docker_compose_v2`, но он падает на post-action `compose images --format json`:

```
Error response from daemon: No such image: sha256:290ca7626…
```

Это известный баг модуля при `--build --force-recreate`. Прямой `docker compose` не делает такой post-action и работает стабильно.

Если ошибка всё же появилась (например, после обновлений docker compose) — ручное восстановление:

```bash
ssh -p 9922 -i ~/.ssh/GitHub_SSH telnor@147.45.183.98 'docker image prune -f && cd /opt/home-page && docker compose up -d --build --force-recreate <service>'
```

### Ansible Vault

Чувствительные данные зашифрованы поштучно в `infra/ansible/inventory/group_vars/all/vault.yml`:

| Переменная | Описание | Зашифрована |
|---|---|---|
| `vault_server_ip` | IP-адрес ВМ | да |
| `vault_ssh_key_path` | Путь к приватному SSH-ключу | да |
| `vault_ansible_user` | Имя пользователя для подключения | нет |
| `vault_home_ip` | Домашний IP (для IP-whitelist) | да |
| `vault_postgres_user` | Пользователь PostgreSQL | да |
| `vault_postgres_password` | Пароль PostgreSQL | да |
| `vault_postgres_db` | Имя БД | да |
| `vault_domain` | Домен проекта | нет |
| `vault_acme_email` | Email для Let's Encrypt | нет |
| `vault_jwt_secret` | Секрет для подписи JWT | да |
| `vault_invite_code` | Код для регистрации | да |
| `vault_cron_secret` | Секрет для cron-запросов | да |
| `vault_telegram_bot_token` | Токен Telegram-бота от BotFather | да |
| `vault_telegram_bot_username` | Username Telegram-бота (без `@`) | нет |
| `vault_bot_secret` | Секрет для авторизации бота перед backend | да |
| `vault_uptime_secret` | Секрет для webhook-алертов от HetrixTools | да |
| `vault_yadisk_user` | Логин Яндекс.Диска для бэкапов | да |
| `vault_yadisk_app_password` | Пароль приложения Яндекс.Диска (WebDAV) | да |
| `vault_wg_private_key` | WireGuard PrivateKey (для VPN бота) | да |
| `vault_wg_public_key` | WireGuard PublicKey пира | да |
| `vault_wg_preshared_key` | WireGuard PresharedKey | да |
| `vault_wg_address` | Адрес WireGuard-клиента (`10.x.x.x/24`) | да |
| `vault_wg_endpoint` | Endpoint WireGuard-сервера (`host:port`) | да |
| `vault_google_service_account_b64` | JSON-ключ Google service account в base64 (для Calendar API) | да |
| `vault_calendar_configs` | Список календарей: `[{label, id}, ...]` | нет |

Пароль vault хранится в `infra/ansible/.vault_pass` (не попадает в git).

Шифрование отдельного значения:

```bash
ansible-vault encrypt_string 'значение' --name 'vault_имя_переменной'
```

Просмотр зашифрованного файла:

```bash
ansible-vault view inventory/group_vars/all/vault.yml
```

## Расписание голосования (GMT+3)

Cron-контейнер вызывает backend-эндпоинты по расписанию:

| Время | Действие | Статус меню |
|---|---|---|
| 08:00 | Создать меню + 3 случайных рецепта + утренний дайджест админам с расписанием Google Calendar | `collecting` |
| 13:00 | Финализировать, открыть голосование + уведомление в бот | `voting` |
| 17:00 | Закрыть голосование, определить победителя + уведомление в бот | `closed` |

Admin может выполнять эти действия и вручную (эндпоинты идемпотентны). Уведомления рассылаются через `/notify` эндпоинт бота.

Ежедневно в **03:00 GMT+3** тот же cron выполняет `pg_dump` БД, заливает сжатый архив на Яндекс.Диск через WebDAV и удаляет бэкап старше 14 дней.

## Мониторинг

[HetrixTools](https://hetrixtools.com) (бесплатный тариф) отслеживает:
- Uptime `telnor.ru` (frontend) и `api.telnor.ru/api/health` (backend) с нескольких локаций
- Blacklist: IP ВМ и домен на предмет попадания в антиспам-базы

При падении или попадании в blacklist HetrixTools вызывает webhook бота `bot.telnor.ru/uptime-alert?secret=...`, бот рассылает алерт всем admin-пользователям в Telegram.

## Telegram-бот

Работает в режиме **polling** (Telegram API не блокирует исходящий трафик из bot-контейнера благодаря WireGuard-туннелю до VPS в Германии — используется только для подсетей Telegram, остальной трафик идёт напрямую).

Помимо polling, бот поднимает aiohttp-сервер на порту `8080`:
- `POST /notify` (X-Cron-Secret) — рассылка уведомлений о меню, вызывается cron-контейнером
- `POST /uptime-alert?secret=...` — алерты от HetrixTools админам
- `POST /check-calendar` (X-Cron-Secret) — проверка Google Calendar и рассылка напоминаний; `?digest=true` — утренний дайджест на сегодня и завтра. На каждом 5-минутном тике также проверяется статус сегодняшнего меню — если cron-вызов `/notify` потерялся (бот рестартил, сеть моргнула), уведомление о voting/closed досылается с дедупом по `menu_id`

## Архитектура

Подробные архитектурные решения описаны в [architecture.md](./docs/architecture.md).

## API

Документация API с примерами: [api.md](./docs/api.md).

Swagger UI: [https://api.telnor.ru/docs](https://api.telnor.ru/docs) (доступ ограничен по IP).

## Тестирование

Гайд для тестировщика с тест-кейсами и ручными триггерами: [testing.md](./docs/testing.md).

## Лицензия

MIT
