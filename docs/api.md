# API Documentation

Swagger UI: `https://api.telnor.ru/docs` (доступ ограничен по IP)

Base URL: `https://api.telnor.ru/api`

---

## Health

### GET /api/health

Проверка состояния сервиса и подключения к БД.

```bash
curl https://api.telnor.ru/api/health
```

Ответ (200):
```json
{"status": "ok"}
```

---

## Auth

### POST /api/auth/register

Регистрация нового пользователя. Требуется инвайт-код.

```bash
curl -X POST https://api.telnor.ru/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "ivan", "password": "mypassword", "invite_code": "КОД"}'
```

Ответ (201):
```json
{
  "id": "4fe43be5-3b64-4660-9f16-b2e62dd7440d",
  "username": "ivan",
  "role": "user",
  "created_at": "2026-04-05T22:05:51.384599Z"
}
```

Ошибки:
- 403 — неверный инвайт-код
- 409 — username уже занят

### POST /api/auth/login

Логин. JWT токен (7 дней) устанавливается в httpOnly cookie.

```bash
curl -X POST https://api.telnor.ru/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "ivan", "password": "mypassword"}' \
  -c cookies.txt
```

Ответ (200):
```json
{"message": "ok"}
```

Ошибки:
- 401 — неверный логин или пароль

### POST /api/auth/logout

Удаление cookie. Требуется авторизация.

```bash
curl -X POST https://api.telnor.ru/api/auth/logout -b cookies.txt
```

Ответ (200):
```json
{"message": "ok"}
```

### GET /api/auth/me

Текущий пользователь. Требуется авторизация.

```bash
curl https://api.telnor.ru/api/auth/me -b cookies.txt
```

Ответ (200):
```json
{
  "id": "4fe43be5-3b64-4660-9f16-b2e62dd7440d",
  "username": "ivan",
  "role": "user",
  "created_at": "2026-04-05T22:05:51.384599Z",
  "tg_id": null,
  "first_name": "Иван",
  "birthday": "1990-05-15",
  "is_volkov": true,
  "gender": "male",
  "notifications_enabled": true
}
```

Ошибки:
- 401 — не авторизован или токен истёк

### PATCH /api/auth/me

Обновить личные данные текущего пользователя. Все поля опциональные — обновляются только переданные.

```bash
curl -X PATCH https://api.telnor.ru/api/auth/me \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"first_name": "Никита", "birthday": "1990-05-15", "is_volkov": true, "gender": "male"}'
```

Поля:
- `first_name`: string | null (max 50)
- `birthday`: string (ISO date `YYYY-MM-DD`) | null
- `is_volkov`: boolean
- `gender`: `"male"` | `"female"` | null
- `notifications_enabled`: boolean (управление уведомлениями бота)

Ответ (200): обновлённый `UserResponse`.

### POST /api/auth/telegram-verify

Привязать Telegram к текущему пользователю через данные от Login Widget.

```bash
curl -X POST https://api.telnor.ru/api/auth/telegram-verify \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"id": 123456, "first_name": "Иван", "auth_date": 1700000000, "hash": "..."}'
```

Ответ (200): обновлённый `UserResponse` с `tg_id`.

Ошибки:
- 401 — неверная подпись или протухшая
- 409 — Telegram уже привязан к другому пользователю

### POST /api/auth/telegram-unlink

Отвязать Telegram от текущего пользователя.

```bash
curl -X POST https://api.telnor.ru/api/auth/telegram-unlink -b cookies.txt
```

Ответ (200): `UserResponse` с `tg_id: null`.

### POST /api/auth/change-password

Сменить пароль.

```bash
curl -X POST https://api.telnor.ru/api/auth/change-password \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"old_password": "old", "new_password": "newpassword"}'
```

Ответ (200): `{"message": "ok"}`.

Ошибки:
- 401 — неверный текущий пароль

### POST /api/auth/telegram-login

Выдать JWT боту для пользователя по `tg_id`. Требует заголовок `X-Bot-Secret`.

```bash
curl -X POST https://api.telnor.ru/api/auth/telegram-login \
  -H "Content-Type: application/json" \
  -H "X-Bot-Secret: $BOT_SECRET" \
  -d '{"tg_id": 123456}'
```

Ответ (200): `{"access_token": "..."}`.

Ошибки:
- 403 — неверный секрет
- 404 — пользователь не найден

### GET /api/auth/users/notifiable

Список пользователей с привязанным Telegram и включёнными уведомлениями. Для бота.

```bash
curl https://api.telnor.ru/api/auth/users/notifiable \
  -H "X-Bot-Secret: $BOT_SECRET"
```

Ответ (200):
```json
[
  {"tg_id": 123456, "first_name": "Никита", "username": "testuser"}
]
```

Ошибки:
- 403 — неверный секрет

### GET /api/auth/users/admins

Список admin-пользователей с привязанным Telegram. Используется ботом для отправки алертов от HetrixTools.

```bash
curl https://api.telnor.ru/api/auth/users/admins \
  -H "X-Bot-Secret: $BOT_SECRET"
```

Ответ (200):
```json
[
  {"tg_id": 123456, "first_name": "Никита", "username": "admin"}
]
```

Ошибки:
- 403 — неверный секрет

---

## Recipes

`GET /api/recipes`, `GET /api/recipes/{id}`, `GET /api/recipes/search` — **публичные** (гостевой доступ).
`POST`, `PUT`, `DELETE` — требуют авторизации (cookie или `Authorization: Bearer <token>`).

### GET /api/recipes/search?q=

Поиск рецептов по подстроке в названии (ILIKE). Публично.

```bash
curl "https://api.telnor.ru/api/recipes/search?q=макароны"
```

Ответ (200): массив `RecipeResponse` (тот же формат что у `GET /api/recipes`).

### POST /api/recipes

Создать рецепт с ингредиентами. `author_id` берётся из JWT.

```bash
curl -X POST https://api.telnor.ru/api/recipes \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "title": "Борщ",
    "description": "Классический борщ",
    "servings": 4,
    "ingredients": [
      {"name": "Свёкла", "amount": "2", "unit": "шт"},
      {"name": "Картофель", "amount": "3", "unit": "шт"},
      {"name": "Капуста", "amount": "300", "unit": "г"}
    ]
  }'
```

Ответ (201):
```json
{
  "id": "a1b2c3d4-...",
  "title": "Борщ",
  "description": "Классический борщ",
  "servings": 4,
  "author_id": "4fe43be5-...",
  "ingredients": [
    {"id": "...", "name": "Свёкла", "amount": "2", "unit": "шт"},
    {"id": "...", "name": "Картофель", "amount": "3", "unit": "шт"},
    {"id": "...", "name": "Капуста", "amount": "300", "unit": "г"}
  ],
  "created_at": "2026-04-06T...",
  "updated_at": "2026-04-06T..."
}
```

### GET /api/recipes

Список всех рецептов с ингредиентами. Публично.

```bash
curl https://api.telnor.ru/api/recipes
```

Ответ (200): массив `RecipeResponse`.

### GET /api/recipes/{id}

Один рецепт по ID. Публично.

```bash
curl https://api.telnor.ru/api/recipes/a1b2c3d4-...
```

Ответ (200): `RecipeResponse`.

Ошибки:
- 404 — рецепт не найден

### PUT /api/recipes/{id}

Обновить рецепт. Доступно автору или admin. Если передан `ingredients` — полная замена.

```bash
curl -X PUT https://api.telnor.ru/api/recipes/a1b2c3d4-... \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "title": "Борщ украинский",
    "servings": 6,
    "ingredients": [
      {"name": "Свёкла", "amount": "3", "unit": "шт"},
      {"name": "Картофель", "amount": "4", "unit": "шт"}
    ]
  }'
```

Ответ (200): обновлённый `RecipeResponse`.

Ошибки:
- 403 — нет прав (не автор и не admin)
- 404 — рецепт не найден

### DELETE /api/recipes/{id}

Удалить рецепт. Доступно автору или admin. Нельзя удалить рецепт в активном голосовании.

```bash
curl -X DELETE https://api.telnor.ru/api/recipes/a1b2c3d4-... -b cookies.txt
```

Ответ: 204 No Content.

Ошибки:
- 403 — нет прав
- 404 — рецепт не найден
- 409 — рецепт используется в активном голосовании

---

## Menus

Эндпоинты управления ежедневным меню и голосованием.

Статусы меню: `collecting` → `voting` → `closed`

Авторизация cron-запросов: заголовок `X-Cron-Secret`.

`MenuResponse` содержит:
- `user_voted_recipe_id` — ID рецепта, за который проголосовал текущий пользователь (null если не голосовал)
- `total_votes` — общее количество голосов в меню

### POST /api/menus/create-daily

Создать меню на день. 3 случайных рецепта добавляются автоматически. Доступно admin или cron.

```bash
curl -X POST https://api.telnor.ru/api/menus/create-daily \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{}'
```

С указанием даты (admin):

```bash
curl -X POST https://api.telnor.ru/api/menus/create-daily \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"date": "2026-04-10"}'
```

Ответ (201): `MenuResponse` с 3 случайными рецептами, статус `collecting`.

Ошибки:
- 403 — нет прав (не admin и не cron)
- 409 — меню на эту дату уже существует

### POST /api/menus/{id}/suggest

Предложить рецепт в меню. 1 предложение на пользователя, admin до 3. Только в статусе `collecting`.

```bash
curl -X POST https://api.telnor.ru/api/menus/{menu_id}/suggest \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"recipe_id": "92e6062a-..."}'
```

Ответ (200): обновлённый `MenuResponse`.

Ошибки:
- 400 — меню не принимает предложения (не `collecting`) или лимит предложений
- 404 — меню или рецепт не найден
- 409 — рецепт уже в меню

### POST /api/menus/finalize

Финализировать список, открыть голосование. Доступно admin или cron. Идемпотентно.

```bash
curl -X POST https://api.telnor.ru/api/menus/finalize \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{}'
```

Ответ (200): `MenuResponse` со статусом `voting`.

Ошибки:
- 403 — нет прав
- 404 — меню не найдено

### POST /api/menus/{id}/vote

Проголосовать за рецепт. Один голос на пользователя на меню. Только в статусе `voting`.

```bash
curl -X POST https://api.telnor.ru/api/menus/{menu_id}/vote \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"recipe_id": "92e6062a-..."}'
```

Ответ (200): `MenuResponse` с обновлённым `votes_count`.

Ошибки:
- 400 — голосование не открыто или рецепт не в меню
- 404 — меню не найдено
- 409 — уже голосовал

### DELETE /api/menus/{id}/vote

Отменить голос текущего пользователя. Только в статусе `voting`. Идемпотентно.

```bash
curl -X DELETE https://api.telnor.ru/api/menus/{menu_id}/vote -b cookies.txt
```

Ответ (200): `MenuResponse` с обновлёнными голосами.

Ошибки:
- 400 — голосование не открыто
- 404 — меню не найдено

### POST /api/menus/close-voting

Закрыть голосование, определить победителя. Доступно admin или cron. Идемпотентно.

```bash
curl -X POST https://api.telnor.ru/api/menus/close-voting \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{}'
```

Ответ (200): `MenuResponse` со статусом `closed` и `winner_recipe_id`.

Ошибки:
- 400 — меню не в статусе `voting`
- 403 — нет прав
- 404 — меню не найдено

### GET /api/menus/today

Меню на сегодня.

```bash
curl https://api.telnor.ru/api/menus/today -b cookies.txt
```

Ответ (200): `MenuResponse`.

Ошибки:
- 404 — меню на сегодня не создано

### GET /api/menus

История всех меню.

```bash
curl https://api.telnor.ru/api/menus -b cookies.txt
```

Ответ (200): массив `MenuResponse`.

### GET /api/menus/{id}

Конкретное меню с рецептами и голосами.

```bash
curl https://api.telnor.ru/api/menus/{menu_id} -b cookies.txt
```

Ответ (200): `MenuResponse`.

Ошибки:
- 404 — меню не найдено

### DELETE /api/menus/{id}

Удалить меню. Только admin. Для тестирования.

```bash
curl -X DELETE https://api.telnor.ru/api/menus/{menu_id} -b cookies.txt
```

Ответ: 204 No Content.

Ошибки:
- 403 — не admin
- 404 — меню не найдено

---

## Bot Notifications (внутренний API)

Бот принимает POST-запросы на `/notify` для рассылки уведомлений. Эндпоинт доступен только из Docker-сети (cron-контейнер вызывает автоматически по расписанию).

Ручное тестирование с ВМ:

```bash
docker exec cron sh -c 'curl -s -X POST http://bot:8080/notify \
  -H "X-Cron-Secret: $CRON_SECRET" \
  -H "Content-Type: application/json" \
  -d "{\"event\":\"menu_created\"}"'
```

События:
- `menu_created` — меню дня создано (08:00)
- `voting_opened` — голосование открыто (13:00)
- `voting_closed` — голосование завершено, победитель определён (17:00)

### POST https://bot.telnor.ru/uptime-alert?secret=...

Webhook для HetrixTools. Секрет передаётся в query-параметре `?secret=...`. Бот парсит payload и рассылает алерт всем admin-пользователям в Telegram.

Формат payload от HetrixTools (JSON):
```json
{
  "monitor_name": "Home Page Frontend",
  "monitor_target": "https://telnor.ru",
  "monitor_status": "offline"
}
```

Значения `monitor_status`:
- `online` → 🟢 UP
- `offline` → 🔴 DOWN
- `maintenance` → 🔧 MAINTENANCE

Ошибки:
- 403 — неверный secret
