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

### Ansible Vault

Чувствительные данные зашифрованы поштучно в `infra/ansible/inventory/group_vars/all/vault.yml`:

| Переменная | Описание | Зашифрована |
|---|---|---|
| `vault_server_ip` | IP-адрес ВМ | да |
| `vault_ssh_key_path` | Путь к приватному SSH-ключу | да |
| `vault_ansible_user` | Имя пользователя для подключения | нет |

Пароль vault хранится в `infra/ansible/.vault_pass` (не попадает в git). Скрипт `setup-wsl-ssh.sh` копирует его в WSL и добавляет `ANSIBLE_VAULT_PASSWORD_FILE` в `~/.bashrc`.

Шифрование отдельного значения:

```bash
ansible-vault encrypt_string 'значение' --name 'vault_имя_переменной'
```

Просмотр зашифрованного файла:

```bash
ansible-vault view inventory/group_vars/all/vault.yml
```

После этого CI/CD (GitHub Actions) автоматически деплоит новые версии при пуше в `main`.

## Архитектура

Подробные архитектурные решения описаны в [architecture.md](./docs/architecture.md).

## Лицензия

MIT
