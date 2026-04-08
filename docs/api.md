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
  "created_at": "2026-04-05T22:05:51.384599Z"
}
```

Ошибки:
- 401 — не авторизован или токен истёк

---

## Recipes

Все эндпоинты требуют авторизации (cookie из `/api/auth/login`).

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

Список всех рецептов с ингредиентами.

```bash
curl https://api.telnor.ru/api/recipes -b cookies.txt
```

Ответ (200): массив `RecipeResponse`.

### GET /api/recipes/{id}

Один рецепт по ID.

```bash
curl https://api.telnor.ru/api/recipes/a1b2c3d4-... -b cookies.txt
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
