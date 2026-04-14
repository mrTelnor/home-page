# Telegram Bot (Dinner Vote) — Design Spec

## Обзор

Telegram-бот для семейного голосования за ужин. Aiogram 3 (async), отдельный Docker-сервис. Получает обновления через webhook на `bot.telnor.ru`. Общается с backend API (`http://backend:8000`) по внутренней сети Docker.

Привязка аккаунта — только через сайт (Login Widget на /profile). Бот не принимает пароли и коды.

## Архитектура

### Сервис

Отдельный Python-сервис (`bot/`) в Docker Compose. Aiogram 3 поднимает aiohttp-сервер на порту 8080 для приёма webhook-обновлений от Telegram.

- Сеть: `web` (доступ через Traefik + связь с backend)
- Traefik: `bot.telnor.ru` → bot:8080, SSL через Let's Encrypt
- При старте: `set_webhook(url="https://bot.telnor.ru/webhook")`

### Авторизация запросов к API

1. Бот получает `tg_id` из Telegram update
2. Вызывает `POST /api/auth/telegram-login` с заголовком `X-Bot-Secret` → получает JWT
3. Использует JWT как `Authorization: Bearer <token>` для остальных запросов
4. JWT кэшируется в памяти (dict `{tg_id: token}`) на время жизни (7 дней), обновляется при 401

### Неавторизованные пользователи

Если `tg_id` не привязан (telegram-login возвращает 404), бот отвечает:
"Привяжите Telegram-аккаунт на telnor.ru/profile, затем попробуйте снова."

## Команды

| Команда | Описание | Доступность |
|---|---|---|
| `/start` | Приветствие. Если не привязан — ссылка на сайт. Если привязан — имя, статус сегодняшнего меню | всегда |
| `/menu` | Меню дня: список рецептов, статус (сбор / голосование / завершено), победитель | привязанные |
| `/vote` | Голосование inline-кнопками. Если уже голосовал — текущий голос + "Отменить голос". После отмены — кнопки для нового голоса | привязанные, статус "voting" |
| `/suggest` | Предложить рецепт: бот просит ввести название → поиск по подстроке → кнопки совпадений. Нет совпадений — ссылка на сайт для создания | привязанные, статус "collecting" |
| `/recipes` | Список всех рецептов с пагинацией (inline-кнопки, по 10 на страницу) | привязанные |
| `/mute` | Отключить уведомления | привязанные |
| `/unmute` | Включить уведомления | привязанные |
| `/help` | Список команд с описанием | всегда |

### Ошибки

- Не привязан аккаунт → "Привяжите Telegram на telnor.ru/profile"
- `/vote` не в фазе голосования → "Голосование ещё не открыто" / "Голосование уже завершено"
- `/suggest` не в фазе сбора → "Сбор предложений закрыт"
- Нет меню на сегодня → "Меню ещё не создано"

## Flow голосования (`/vote`)

1. Пользователь вызывает `/vote`
2. Бот запрашивает `GET /api/menus/today`
3. Если статус != "voting" → сообщение об ошибке
4. Если `user_voted_recipe_id` != null:
   - Показать "Ваш голос: {название} ✓" + кнопка [Отменить голос]
   - Ниже: inline-кнопки с рецептами (текущий голос отмечен ✓)
5. Если не голосовал:
   - Inline-кнопки с рецептами для выбора
6. Нажатие на рецепт → `POST /api/menus/{id}/vote`
7. Нажатие "Отменить" → `DELETE /api/menus/{id}/vote` → обновить сообщение с новыми кнопками

## Flow предложения рецепта (`/suggest`)

1. Пользователь вызывает `/suggest`
2. Бот проверяет `GET /api/menus/today`, статус == "collecting"
3. Бот отправляет "Введите название рецепта:"
4. Пользователь вводит текст (FSM state: waiting_recipe_name)
5. Бот вызывает `GET /api/recipes/search?q={текст}`
6. Если есть совпадения — inline-кнопки с названиями рецептов
7. Если нет совпадений — "Рецепт не найден. Добавьте его на telnor.ru/recipes/new и попробуйте снова."
8. Пользователь нажимает кнопку → `POST /api/menus/{id}/suggest` с recipe_id
9. Бот подтверждает и рассылает уведомление остальным

## Уведомления

### 4 типа

| Триггер | Сообщение |
|---|---|
| Меню создано (08:00) | "Меню дня готово! Предлагайте свои варианты" + список 3 рецептов |
| Пользователь предложил рецепт | "{Имя} предложил к голосованию: {Название рецепта}" (имя из first_name профиля, fallback — username) |
| Голосование открыто (13:00) | "Голосование открыто! Используйте /vote для выбора ужина" |
| Голосование закрыто (17:00) | "Голосование завершено! Победитель: {Название} ({N} голосов)" + итоги по всем рецептам |

### Механизм рассылки

Cron-контейнер после вызова backend-эндпоинта дополнительно вызывает `POST http://bot:8080/notify` с заголовком `X-Cron-Secret` и JSON:

```json
{"event": "menu_created" | "voting_opened" | "voting_closed"}
```

Бот при получении:
1. Запрашивает `GET /api/auth/users/notifiable` (список пользователей с tg_id и notifications_enabled=true)
2. Запрашивает `GET /api/menus/today` для данных меню
3. Рассылает сообщения каждому пользователю через Telegram API

Уведомление о предложении рецепта — бот рассылает сразу после успешного `/suggest`, без участия cron.

### Настройка per-user

Поле `notifications_enabled: bool DEFAULT TRUE` в таблице `auth.users`. Команды `/mute` и `/unmute` переключают через `PATCH /api/auth/me`.

## Backend-изменения

### Новое поле в модели User

`notifications_enabled: Mapped[bool] = mapped_column(default=True)`

Миграция Alembic: `ALTER TABLE auth.users ADD COLUMN notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE`.

Добавить `notifications_enabled` в `UserResponse` и `UpdateProfileRequest`.

### Новый эндпоинт: GET /api/auth/users/notifiable

Возвращает список пользователей с `tg_id IS NOT NULL AND notifications_enabled = TRUE`.

Защищён заголовком `X-Bot-Secret`.

Ответ:
```json
[{"tg_id": 12345, "first_name": "Никита", "username": "testuser"}]
```

### Новый эндпоинт: GET /api/recipes/search?q=макароны

Поиск рецептов по подстроке в title (ILIKE). Защищён JWT.

Ответ: `list[RecipeResponse]` (тот же формат что у `GET /api/recipes`, но отфильтрованный).

## Структура файлов бота

```
bot/
├── app/
│   ├── __init__.py
│   ├── main.py              # Точка входа: webhook setup, aiohttp сервер
│   ├── config.py             # Настройки (BOT_TOKEN, BOT_SECRET, BACKEND_URL)
│   ├── api_client.py         # HTTP-клиент к backend (login, кэш JWT, запросы)
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py          # /start, /help
│   │   ├── menu.py           # /menu
│   │   ├── vote.py           # /vote + callback отмена/выбор
│   │   ├── suggest.py        # /suggest (FSM: поиск + предложение)
│   │   ├── recipes.py        # /recipes (пагинация)
│   │   └── notifications.py  # /mute, /unmute
│   └── notify.py             # HTTP эндпоинт /notify + логика рассылки
├── requirements.txt          # aiogram>=3.0, aiohttp, httpx
└── Dockerfile
```

## Инфраструктура

### Docker Compose

```yaml
bot:
  build:
    context: ../..
    dockerfile: infra/docker/bot/Dockerfile
  networks: [web]
  environment:
    - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    - BOT_SECRET=${BOT_SECRET}
    - BACKEND_URL=http://backend:8000
    - WEBHOOK_HOST=https://bot.telnor.ru
    - CRON_SECRET=${CRON_SECRET}
  labels:
    - traefik.enable=true
    - traefik.http.routers.bot.rule=Host(`bot.${DOMAIN}`)
    - traefik.http.routers.bot.tls.certresolver=letsencrypt
    - traefik.http.services.bot.loadbalancer.server.port=8080
  depends_on:
    backend:
      condition: service_healthy
```

### Cron — дополнения

После каждого существующего вызова к backend добавить:
```bash
curl -s -X POST http://bot:8080/notify \
  -H "X-Cron-Secret: $CRON_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"event": "menu_created"}'
```

Аналогично для `voting_opened` и `voting_closed`.

### Ansible

Добавить синхронизацию `bot/` на ВМ (rsync, как backend/frontend).

### DNS

A-запись `bot.telnor.ru → 147.45.183.98`.

## Тестирование

- **Backend:** тесты на `GET /api/recipes/search`, `GET /api/auth/users/notifiable`, поле `notifications_enabled` в profile update
- **Bot:** юнит-тесты на `api_client` (mock httpx), тесты handlers через aiogram test utilities
- **CI:** новый workflow `bot.yml` — lint (ruff), тесты (pytest)
