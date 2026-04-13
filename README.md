# 🍽️ Home Page

Семейный домашний сервис. Первое приложение — **Dinner Vote**: голосование за ужин через веб-интерфейс (позже — через Telegram-бота).

**Прод:** [telnor.ru](https://telnor.ru)

## Возможности

- 📖 **База рецептов** — добавление, редактирование, удаление рецептов с ингредиентами. Пересчёт ингредиентов под произвольное количество порций
- 🗳️ **Голосование за ужин** — ежедневно по расписанию (8:00 GMT+3) создаётся меню из 3 случайных рецептов, члены семьи могут предлагать свои варианты и голосовать. В 17:00 определяется победитель
- 📜 **История голосований** — прошлые меню с результатами
- 🔐 **Авторизация** — регистрация по инвайт-коду, JWT в httpOnly cookie
- 👤 **Личный кабинет** — смена пароля, привязка Telegram через Login Widget
- 🌐 **Веб-интерфейс** — адаптивный UI с тёмной темой

## Стек технологий

| Слой | Технологии |
|---|---|
| Бэкенд | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2 |
| База данных | PostgreSQL 16 (схемы `auth`, `dinner`) |
| Фронтенд | React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Zustand |
| Автоматизация | Cron-контейнер (Alpine + curl) для ежедневного цикла голосования |
| Инфраструктура | Docker, Docker Compose, Traefik v3 (Let's Encrypt), Ansible |
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
├── infra/
│   ├── ansible/          # Playbooks, roles, inventory
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   ├── cron/         # Cron-контейнер для расписания голосования
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
| `traefik.telnor.ru` | Traefik dashboard | только с домашнего IP |
| `portainer.telnor.ru` | Portainer UI | только с домашнего IP |

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
- Синхронизирует код backend/frontend/cron на ВМ (rsync с exclude node_modules/__pycache__)
- Генерирует `.env` из переменных Ansible Vault
- Пересобирает и перезапускает контейнеры при изменениях (build + recreate)

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
| 08:00 | Создать меню + 3 случайных рецепта | `collecting` |
| 13:00 | Финализировать, открыть голосование | `voting` |
| 17:00 | Закрыть голосование, определить победителя | `closed` |

Admin может выполнять эти действия и вручную (эндпоинты идемпотентны).

## Архитектура

Подробные архитектурные решения описаны в [architecture.md](./docs/architecture.md).

## API

Документация API с примерами: [api.md](./docs/api.md).

Swagger UI: [https://api.telnor.ru/docs](https://api.telnor.ru/docs) (доступ ограничен по IP).

## Лицензия

MIT
