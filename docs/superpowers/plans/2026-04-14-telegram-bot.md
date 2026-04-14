# Telegram Bot (Dinner Vote) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an Aiogram 3 Telegram bot that lets family members view menus, vote for dinner, suggest recipes, and receive notifications — all through Telegram.

**Architecture:** Separate Python service (`bot/`) communicating with existing FastAPI backend via HTTP. Webhook-based (bot.telnor.ru via Traefik). Backend gets two new endpoints (recipe search, notifiable users list) and a new `notifications_enabled` field on User model. Cron container triggers bot notifications after each menu lifecycle event.

**Tech Stack:** Aiogram 3, aiohttp, httpx, Python 3.12, Docker, Traefik

---

## File Structure

### New files (bot service)

| File | Responsibility |
|---|---|
| `bot/app/__init__.py` | Package marker |
| `bot/app/config.py` | Settings from env vars (BOT_TOKEN, BOT_SECRET, BACKEND_URL, etc.) |
| `bot/app/api_client.py` | HTTP client to backend with JWT caching, login, authenticated requests |
| `bot/app/main.py` | Aiogram webhook setup, aiohttp server on :8080, /notify endpoint |
| `bot/app/handlers/__init__.py` | Register all routers |
| `bot/app/handlers/start.py` | /start, /help commands |
| `bot/app/handlers/menu.py` | /menu command |
| `bot/app/handlers/vote.py` | /vote command + inline callbacks for vote/cancel |
| `bot/app/handlers/suggest.py` | /suggest command with FSM (search + select) |
| `bot/app/handlers/recipes.py` | /recipes command with pagination |
| `bot/app/handlers/notifications.py` | /mute, /unmute commands |
| `bot/app/notify.py` | Notification dispatch logic (build messages, broadcast) |
| `bot/requirements.txt` | Dependencies |
| `bot/Dockerfile` | Container build |
| `bot/pyproject.toml` | Ruff config, pytest config |

### Modified files (backend)

| File | Change |
|---|---|
| `backend/app/db/models/user.py` | Add `notifications_enabled` field |
| `backend/alembic/versions/004_add_notifications_enabled.py` | Migration |
| `backend/app/schemas/auth.py` | Add `notifications_enabled` to UserResponse + UpdateProfileRequest |
| `backend/app/services/auth.py` | Add `get_notifiable_users()` |
| `backend/app/api/auth.py` | Add `GET /auth/users/notifiable` |
| `backend/app/services/recipe.py` | Add `search_recipes()` |
| `backend/app/api/recipes.py` | Add `GET /recipes/search?q=` |
| `backend/tests/test_recipes.py` | Tests for search endpoint |
| `backend/tests/test_auth.py` | Tests for notifiable + notifications_enabled |

### Modified files (infrastructure)

| File | Change |
|---|---|
| `infra/docker/docker-compose.yml` | Add bot service |
| `infra/docker/cron/crontab` | Add notify calls after each menu event |
| `infra/ansible/roles/app/tasks/main.yml` | Add bot sync task |
| `infra/ansible/roles/app/templates/env.j2` | Add WEBHOOK_HOST |
| `.github/workflows/bot.yml` | CI for bot (lint + tests) |

---

### Task 1: Backend — Add `notifications_enabled` field + migration

**Files:**
- Modify: `backend/app/db/models/user.py`
- Create: `backend/alembic/versions/004_add_notifications_enabled.py`
- Modify: `backend/app/schemas/auth.py`

- [ ] **Step 1: Add field to User model**

In `backend/app/db/models/user.py`, add after line 22 (`gender` field):

```python
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 2: Create Alembic migration**

Create `backend/alembic/versions/004_add_notifications_enabled.py`:

```python
"""add notifications_enabled to users

Revision ID: 004
Revises: 003
Create Date: 2026-04-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "notifications_enabled", schema="auth")
```

- [ ] **Step 3: Update schemas**

In `backend/app/schemas/auth.py`, add `notifications_enabled` to `UserResponse` (after `gender` field):

```python
    notifications_enabled: bool = True
```

In `UpdateProfileRequest`, add:

```python
    notifications_enabled: bool | None = None
```

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `pytest` in CI (push to verify)

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models/user.py backend/alembic/versions/004_add_notifications_enabled.py backend/app/schemas/auth.py
git commit -m "feat: добавлено поле notifications_enabled в модель User"
```

---

### Task 2: Backend — `GET /api/auth/users/notifiable` endpoint

**Files:**
- Modify: `backend/app/services/auth.py`
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/schemas/auth.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Add schema**

In `backend/app/schemas/auth.py`, add:

```python
class NotifiableUserResponse(BaseModel):
    tg_id: int
    first_name: str | None = None
    username: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Add service function**

In `backend/app/services/auth.py`, add:

```python
async def get_notifiable_users(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(User.tg_id.is_not(None), User.notifications_enabled.is_(True))
    )
    return list(result.scalars().all())
```

- [ ] **Step 3: Add endpoint**

In `backend/app/api/auth.py`, add import of `get_notifiable_users` and `NotifiableUserResponse`. Then add the endpoint:

```python
@router.get("/users/notifiable", response_model=list[NotifiableUserResponse])
async def notifiable_users(
    session: DbSession,
    x_bot_secret: Annotated[str | None, Header()] = None,
):
    if x_bot_secret != settings.bot_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_ALLOWED)

    users = await get_notifiable_users(session)
    return users
```

- [ ] **Step 4: Write tests**

In `backend/tests/test_auth.py`, add:

```python
# ---------- NOTIFIABLE USERS ----------

async def test_notifiable_users(authed_client: AsyncClient, admin_client: AsyncClient):
    """Users with tg_id and notifications_enabled=True are returned."""
    # Link telegram to admin
    import hashlib, hmac, time
    BOT_TOKEN = "test-bot-token"
    payload = {"id": 11111, "first_name": "Admin", "auth_date": int(time.time())}
    check_string = "\n".join(f"{k}={payload[k]}" for k in sorted(payload.keys()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    payload["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    await admin_client.post("/api/auth/telegram-verify", json=payload)

    response = await authed_client.get(
        "/api/auth/users/notifiable",
        headers={"X-Bot-Secret": "test-bot-secret"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tg_id"] == 11111


async def test_notifiable_users_wrong_secret(authed_client: AsyncClient):
    response = await authed_client.get(
        "/api/auth/users/notifiable",
        headers={"X-Bot-Secret": "wrong"},
    )
    assert response.status_code == 403


async def test_notifiable_users_muted_excluded(admin_client: AsyncClient):
    """Users with notifications_enabled=False are excluded."""
    import hashlib, hmac, time
    BOT_TOKEN = "test-bot-token"
    payload = {"id": 22222, "first_name": "Admin", "auth_date": int(time.time())}
    check_string = "\n".join(f"{k}={payload[k]}" for k in sorted(payload.keys()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    payload["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    await admin_client.post("/api/auth/telegram-verify", json=payload)

    # Mute notifications
    await admin_client.patch("/api/auth/me", json={"notifications_enabled": False})

    response = await admin_client.get(
        "/api/auth/users/notifiable",
        headers={"X-Bot-Secret": "test-bot-secret"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 0
```

- [ ] **Step 5: Run tests**

Run: `pytest -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/auth.py backend/app/api/auth.py backend/app/schemas/auth.py backend/tests/test_auth.py
git commit -m "feat: эндпоинт GET /api/auth/users/notifiable"
```

---

### Task 3: Backend — `GET /api/recipes/search?q=` endpoint

**Files:**
- Modify: `backend/app/services/recipe.py`
- Modify: `backend/app/api/recipes.py`
- Test: `backend/tests/test_recipes.py`

- [ ] **Step 1: Add service function**

In `backend/app/services/recipe.py`, add:

```python
async def search_recipes(session: AsyncSession, query: str) -> list[Recipe]:
    result = await session.execute(
        select(Recipe)
        .where(Recipe.title.ilike(f"%{query}%"))
        .options(selectinload(Recipe.ingredients))
        .order_by(Recipe.title)
    )
    return list(result.scalars().all())
```

- [ ] **Step 2: Add endpoint**

In `backend/app/api/recipes.py`, add import of `search_recipes`. Then add endpoint **before** the `/{recipe_id}` route (otherwise FastAPI will interpret "search" as a recipe_id):

```python
@router.get("/search", response_model=list[RecipeResponse])
async def search(q: str, session: DbSession, user: CurrentUser):
    _ = user
    return await search_recipes(session, q)
```

- [ ] **Step 3: Write tests**

In `backend/tests/test_recipes.py`, add:

```python
# ---------- SEARCH ----------

async def test_search_recipes(authed_client: AsyncClient):
    await authed_client.post("/api/recipes", json=_sample_recipe_payload("Макароны по-флотски"))
    await authed_client.post("/api/recipes", json=_sample_recipe_payload("Макароны с сосисками"))
    await authed_client.post("/api/recipes", json=_sample_recipe_payload("Борщ"))

    response = await authed_client.get("/api/recipes/search?q=макароны")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    titles = {r["title"] for r in data}
    assert "Макароны по-флотски" in titles
    assert "Макароны с сосисками" in titles


async def test_search_recipes_no_results(authed_client: AsyncClient):
    response = await authed_client.get("/api/recipes/search?q=несуществующий")
    assert response.status_code == 200
    assert len(response.json()) == 0


async def test_search_recipes_requires_auth(client: AsyncClient):
    response = await client.get("/api/recipes/search?q=test")
    assert response.status_code == 401
```

- [ ] **Step 4: Run tests**

Run: `pytest -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/recipe.py backend/app/api/recipes.py backend/tests/test_recipes.py
git commit -m "feat: эндпоинт GET /api/recipes/search для поиска по названию"
```

---

### Task 4: Bot — Config, dependencies, Dockerfile

**Files:**
- Create: `bot/app/__init__.py`
- Create: `bot/app/config.py`
- Create: `bot/requirements.txt`
- Create: `bot/Dockerfile`
- Create: `bot/pyproject.toml`

- [ ] **Step 1: Create `bot/app/__init__.py`**

Empty file.

- [ ] **Step 2: Create `bot/app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    bot_secret: str
    backend_url: str = "http://backend:8000"
    webhook_host: str = "https://bot.telnor.ru"
    webhook_path: str = "/webhook"
    cron_secret: str
    port: int = 8080

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 3: Create `bot/requirements.txt`**

```
aiogram>=3.15
aiohttp>=3.11
httpx>=0.28
pydantic-settings>=2.0
```

- [ ] **Step 4: Create `bot/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

CMD ["python", "-m", "app.main"]
```

- [ ] **Step 5: Create `bot/pyproject.toml`**

```toml
[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP"]
ignore = ["E501"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 6: Commit**

```bash
git add bot/
git commit -m "feat(bot): scaffold — config, Dockerfile, dependencies"
```

---

### Task 5: Bot — API client with JWT caching

**Files:**
- Create: `bot/app/api_client.py`

- [ ] **Step 1: Create `bot/app/api_client.py`**

```python
import httpx

from app.config import settings

NOT_LINKED_MSG = "Привяжите Telegram-аккаунт на telnor.ru/profile, затем попробуйте снова."


class ApiClient:
    def __init__(self) -> None:
        self._tokens: dict[int, str] = {}
        self._http = httpx.AsyncClient(base_url=settings.backend_url, timeout=10)

    async def close(self) -> None:
        await self._http.aclose()

    async def login(self, tg_id: int) -> str | None:
        """Get JWT for a Telegram user. Returns None if user not linked."""
        resp = await self._http.post(
            "/api/auth/telegram-login",
            json={"tg_id": tg_id},
            headers={"X-Bot-Secret": settings.bot_secret},
        )
        if resp.status_code == 404:
            self._tokens.pop(tg_id, None)
            return None
        resp.raise_for_status()
        token = resp.json()["access_token"]
        self._tokens[tg_id] = token
        return token

    async def _get_token(self, tg_id: int) -> str | None:
        if tg_id in self._tokens:
            return self._tokens[tg_id]
        return await self.login(tg_id)

    async def request(self, method: str, path: str, tg_id: int, **kwargs) -> httpx.Response | None:
        """Make authenticated request. Returns None if user not linked."""
        token = await self._get_token(tg_id)
        if token is None:
            return None

        headers = {"Authorization": f"Bearer {token}"}
        resp = await self._http.request(method, path, headers=headers, **kwargs)

        if resp.status_code == 401:
            token = await self.login(tg_id)
            if token is None:
                return None
            headers = {"Authorization": f"Bearer {token}"}
            resp = await self._http.request(method, path, headers=headers, **kwargs)

        return resp

    async def get(self, path: str, tg_id: int, **kwargs) -> httpx.Response | None:
        return await self.request("GET", path, tg_id, **kwargs)

    async def post(self, path: str, tg_id: int, **kwargs) -> httpx.Response | None:
        return await self.request("POST", path, tg_id, **kwargs)

    async def patch(self, path: str, tg_id: int, **kwargs) -> httpx.Response | None:
        return await self.request("PATCH", path, tg_id, **kwargs)

    async def delete(self, path: str, tg_id: int, **kwargs) -> httpx.Response | None:
        return await self.request("DELETE", path, tg_id, **kwargs)

    async def get_notifiable_users(self) -> list[dict]:
        resp = await self._http.get(
            "/api/auth/users/notifiable",
            headers={"X-Bot-Secret": settings.bot_secret},
        )
        resp.raise_for_status()
        return resp.json()


api = ApiClient()
```

- [ ] **Step 2: Commit**

```bash
git add bot/app/api_client.py
git commit -m "feat(bot): API client с JWT кэшированием"
```

---

### Task 6: Bot — Main entry point (webhook + /notify)

**Files:**
- Create: `bot/app/main.py`
- Create: `bot/app/notify.py`
- Create: `bot/app/handlers/__init__.py`

- [ ] **Step 1: Create `bot/app/handlers/__init__.py`**

```python
from aiogram import Router

from app.handlers.start import router as start_router
from app.handlers.menu import router as menu_router
from app.handlers.vote import router as vote_router
from app.handlers.suggest import router as suggest_router
from app.handlers.recipes import router as recipes_router
from app.handlers.notifications import router as notifications_router

main_router = Router()
main_router.include_router(start_router)
main_router.include_router(menu_router)
main_router.include_router(vote_router)
main_router.include_router(suggest_router)
main_router.include_router(recipes_router)
main_router.include_router(notifications_router)
```

- [ ] **Step 2: Create `bot/app/notify.py`**

```python
import logging

from aiogram import Bot

from app.api_client import api

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "collecting": "Сбор предложений",
    "voting": "Голосование",
    "closed": "Завершено",
}


async def broadcast(bot: Bot, text: str) -> None:
    """Send text to all notifiable users."""
    users = await api.get_notifiable_users()
    for user in users:
        try:
            await bot.send_message(chat_id=user["tg_id"], text=text)
        except Exception:
            logger.warning("Failed to send to tg_id=%s", user["tg_id"])


async def notify_menu_created(bot: Bot) -> None:
    """Notify about new daily menu."""
    # Use bot_secret to get menu without user auth
    resp = await api._http.get(
        "/api/menus/today",
        headers={"X-Bot-Secret": api._http.headers.get("X-Bot-Secret", "")},
    )
    # We need an authed request — use any notifiable user or skip
    users = await api.get_notifiable_users()
    if not users:
        return

    first_tg_id = users[0]["tg_id"]
    resp = await api.get("/api/menus/today", first_tg_id)
    if resp is None or resp.status_code != 200:
        return

    menu = resp.json()
    recipes = "\n".join(f"  • {r['title']}" for r in menu["recipes"])
    text = f"🍽 Меню дня готово! Предлагайте свои варианты.\n\nРецепты:\n{recipes}\n\nИспользуйте /suggest"
    await broadcast(bot, text)


async def notify_voting_opened(bot: Bot) -> None:
    """Notify that voting is open."""
    text = "🗳 Голосование открыто! Используйте /vote для выбора ужина."
    await broadcast(bot, text)


async def notify_voting_closed(bot: Bot) -> None:
    """Notify about voting results."""
    users = await api.get_notifiable_users()
    if not users:
        return

    first_tg_id = users[0]["tg_id"]
    resp = await api.get("/api/menus/today", first_tg_id)
    if resp is None or resp.status_code != 200:
        return

    menu = resp.json()
    winner_id = menu.get("winner_recipe_id")
    results = []
    winner_title = "Не определён"
    for r in sorted(menu["recipes"], key=lambda x: x["votes_count"], reverse=True):
        mark = " 🏆" if r["recipe_id"] == winner_id else ""
        results.append(f"  • {r['title']} — {r['votes_count']} гол.{mark}")
        if r["recipe_id"] == winner_id:
            winner_title = r["title"]

    text = f"🎉 Голосование завершено!\n\nПобедитель: {winner_title}\n\n" + "\n".join(results)
    await broadcast(bot, text)


async def notify_recipe_suggested(bot: Bot, suggester_name: str, recipe_title: str, exclude_tg_id: int) -> None:
    """Notify that someone suggested a recipe."""
    users = await api.get_notifiable_users()
    text = f"📝 {suggester_name} предложил к голосованию: {recipe_title}"
    for user in users:
        if user["tg_id"] == exclude_tg_id:
            continue
        try:
            await bot.send_message(chat_id=user["tg_id"], text=text)
        except Exception:
            logger.warning("Failed to send to tg_id=%s", user["tg_id"])


EVENT_HANDLERS = {
    "menu_created": notify_menu_created,
    "voting_opened": notify_voting_opened,
    "voting_closed": notify_voting_closed,
}
```

- [ ] **Step 3: Create `bot/app/main.py`**

```python
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.api_client import api
from app.config import settings
from app.handlers import main_router
from app.notify import EVENT_HANDLERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    webhook_url = f"{settings.webhook_host}{settings.webhook_path}"
    await bot.set_webhook(webhook_url)
    logger.info("Webhook set: %s", webhook_url)


async def on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()
    await api.close()
    logger.info("Shutdown complete")


async def handle_notify(request: web.Request) -> web.Response:
    cron_secret = request.headers.get("X-Cron-Secret")
    if cron_secret != settings.cron_secret:
        return web.json_response({"error": "forbidden"}, status=403)

    data = await request.json()
    event = data.get("event")
    handler = EVENT_HANDLERS.get(event)
    if handler is None:
        return web.json_response({"error": f"unknown event: {event}"}, status=400)

    bot: Bot = request.app["bot"]
    await handler(bot)
    return web.json_response({"ok": True})


def main() -> None:
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(main_router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app["bot"] = bot

    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=settings.webhook_path)

    app.router.add_post("/notify", handle_notify)

    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Commit**

```bash
git add bot/app/main.py bot/app/notify.py bot/app/handlers/__init__.py
git commit -m "feat(bot): main entry point с webhook и /notify эндпоинтом"
```

---

### Task 7: Bot — /start and /help handlers

**Files:**
- Create: `bot/app/handlers/start.py`

- [ ] **Step 1: Create `bot/app/handlers/start.py`**

```python
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from app.api_client import api, NOT_LINKED_MSG

router = Router()

HELP_TEXT = (
    "Команды:\n"
    "/menu — меню дня\n"
    "/vote — голосовать за ужин\n"
    "/suggest — предложить рецепт\n"
    "/recipes — список рецептов\n"
    "/mute — отключить уведомления\n"
    "/unmute — включить уведомления\n"
    "/help — эта справка"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.get("/api/auth/me", tg_id)

    if resp is None:
        await message.answer(f"Добро пожаловать!\n\n{NOT_LINKED_MSG}")
        return

    user = resp.json()
    name = user.get("first_name") or user["username"]
    await message.answer(f"Привет, {name}!\n\n{HELP_TEXT}")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
```

- [ ] **Step 2: Commit**

```bash
git add bot/app/handlers/start.py
git commit -m "feat(bot): /start и /help команды"
```

---

### Task 8: Bot — /menu handler

**Files:**
- Create: `bot/app/handlers/menu.py`

- [ ] **Step 1: Create `bot/app/handlers/menu.py`**

```python
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.api_client import api, NOT_LINKED_MSG

router = Router()

STATUS_LABELS = {
    "collecting": "Сбор предложений",
    "voting": "Голосование",
    "closed": "Завершено",
}


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.get("/api/menus/today", tg_id)

    if resp is None:
        await message.answer(NOT_LINKED_MSG)
        return

    if resp.status_code == 404:
        await message.answer("Меню ещё не создано.")
        return

    menu = resp.json()
    status_label = STATUS_LABELS.get(menu["status"], menu["status"])
    recipes = "\n".join(f"  • {r['title']}" for r in menu["recipes"])

    text = f"📋 Меню дня ({status_label})\n\n{recipes}"

    if menu["status"] == "closed" and menu.get("winner_recipe_id"):
        winner = next((r for r in menu["recipes"] if r["recipe_id"] == menu["winner_recipe_id"]), None)
        if winner:
            text += f"\n\n🏆 Победитель: {winner['title']}"

    await message.answer(text)
```

- [ ] **Step 2: Commit**

```bash
git add bot/app/handlers/menu.py
git commit -m "feat(bot): /menu команда"
```

---

### Task 9: Bot — /vote handler with cancel

**Files:**
- Create: `bot/app/handlers/vote.py`

- [ ] **Step 1: Create `bot/app/handlers/vote.py`**

```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.api_client import api, NOT_LINKED_MSG

router = Router()


def build_vote_keyboard(menu: dict) -> InlineKeyboardMarkup:
    user_voted = menu.get("user_voted_recipe_id")
    buttons = []
    for r in menu["recipes"]:
        mark = " ✓" if r["recipe_id"] == user_voted else ""
        buttons.append([InlineKeyboardButton(
            text=f"{r['title']}{mark}",
            callback_data=f"vote:{menu['id']}:{r['recipe_id']}",
        )])
    if user_voted:
        buttons.append([InlineKeyboardButton(
            text="❌ Отменить голос",
            callback_data=f"cancel_vote:{menu['id']}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("vote"))
async def cmd_vote(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.get("/api/menus/today", tg_id)

    if resp is None:
        await message.answer(NOT_LINKED_MSG)
        return

    if resp.status_code == 404:
        await message.answer("Меню ещё не создано.")
        return

    menu = resp.json()
    if menu["status"] != "voting":
        label = "ещё не открыто" if menu["status"] == "collecting" else "уже завершено"
        await message.answer(f"Голосование {label}.")
        return

    user_voted = menu.get("user_voted_recipe_id")
    if user_voted:
        voted_title = next((r["title"] for r in menu["recipes"] if r["recipe_id"] == user_voted), "?")
        text = f"🗳 Ваш голос: {voted_title} ✓\n\nВыберите другой рецепт или отмените голос:"
    else:
        text = "🗳 Голосование открыто! Выберите рецепт:"

    await message.answer(text, reply_markup=build_vote_keyboard(menu))


@router.callback_query(F.data.startswith("vote:"))
async def cb_vote(callback: CallbackQuery) -> None:
    _, menu_id, recipe_id = callback.data.split(":")
    tg_id = callback.from_user.id

    resp = await api.post(f"/api/menus/{menu_id}/vote", tg_id, json={"recipe_id": recipe_id})
    if resp is None:
        await callback.answer(NOT_LINKED_MSG)
        return

    if resp.status_code == 409:
        await callback.answer("Вы уже голосовали. Сначала отмените голос.")
        return

    if resp.status_code != 200:
        await callback.answer("Ошибка голосования.")
        return

    menu = resp.json()
    voted_title = next((r["title"] for r in menu["recipes"] if r["recipe_id"] == recipe_id), "?")
    await callback.message.edit_text(
        f"🗳 Ваш голос: {voted_title} ✓\n\nВыберите другой рецепт или отмените голос:",
        reply_markup=build_vote_keyboard(menu),
    )
    await callback.answer("Голос принят!")


@router.callback_query(F.data.startswith("cancel_vote:"))
async def cb_cancel_vote(callback: CallbackQuery) -> None:
    _, menu_id = callback.data.split(":")
    tg_id = callback.from_user.id

    resp = await api.delete(f"/api/menus/{menu_id}/vote", tg_id)
    if resp is None:
        await callback.answer(NOT_LINKED_MSG)
        return

    menu = resp.json()
    await callback.message.edit_text(
        "🗳 Голос отменён. Выберите рецепт:",
        reply_markup=build_vote_keyboard(menu),
    )
    await callback.answer("Голос отменён.")
```

- [ ] **Step 2: Commit**

```bash
git add bot/app/handlers/vote.py
git commit -m "feat(bot): /vote с inline-кнопками и отменой голоса"
```

---

### Task 10: Bot — /suggest handler with FSM

**Files:**
- Create: `bot/app/handlers/suggest.py`

- [ ] **Step 1: Create `bot/app/handlers/suggest.py`**

```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.api_client import api, NOT_LINKED_MSG

router = Router()


class SuggestStates(StatesGroup):
    waiting_recipe_name = State()


@router.message(Command("suggest"))
async def cmd_suggest(message: Message, state: FSMContext) -> None:
    tg_id = message.from_user.id
    resp = await api.get("/api/menus/today", tg_id)

    if resp is None:
        await message.answer(NOT_LINKED_MSG)
        return

    if resp.status_code == 404:
        await message.answer("Меню ещё не создано.")
        return

    menu = resp.json()
    if menu["status"] != "collecting":
        await message.answer("Сбор предложений закрыт.")
        return

    await state.set_state(SuggestStates.waiting_recipe_name)
    await state.update_data(menu_id=menu["id"])
    await message.answer("Введите название рецепта:")


@router.message(SuggestStates.waiting_recipe_name)
async def on_recipe_name(message: Message, state: FSMContext) -> None:
    tg_id = message.from_user.id
    query = message.text.strip()
    data = await state.get_data()
    menu_id = data["menu_id"]

    resp = await api.get(f"/api/recipes/search?q={query}", tg_id)
    if resp is None:
        await state.clear()
        await message.answer(NOT_LINKED_MSG)
        return

    recipes = resp.json()
    if not recipes:
        await state.clear()
        await message.answer(
            "Рецепт не найден.\n\nДобавьте его на telnor.ru/recipes/new и попробуйте снова."
        )
        return

    buttons = [
        [InlineKeyboardButton(
            text=r["title"],
            callback_data=f"suggest:{menu_id}:{r['id']}",
        )]
        for r in recipes[:10]
    ]
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="suggest_cancel")])

    await state.clear()
    await message.answer(
        "Выберите рецепт:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("suggest:"))
async def cb_suggest(callback: CallbackQuery) -> None:
    _, menu_id, recipe_id = callback.data.split(":")
    tg_id = callback.from_user.id

    resp = await api.post(f"/api/menus/{menu_id}/suggest", tg_id, json={"recipe_id": recipe_id})
    if resp is None:
        await callback.answer(NOT_LINKED_MSG)
        return

    if resp.status_code == 409:
        await callback.answer("Этот рецепт уже в меню.")
        await callback.message.delete()
        return

    if resp.status_code == 400:
        await callback.answer(resp.json().get("detail", "Ошибка"))
        await callback.message.delete()
        return

    if resp.status_code != 200:
        await callback.answer("Ошибка.")
        return

    # Find suggested recipe title from response
    menu = resp.json()
    suggested = next((r for r in menu["recipes"] if r["recipe_id"] == recipe_id), None)
    title = suggested["title"] if suggested else "рецепт"

    await callback.message.edit_text(f"✅ {title} добавлен в меню!")
    await callback.answer()

    # Notify other users
    from app.notify import notify_recipe_suggested
    me_resp = await api.get("/api/auth/me", tg_id)
    if me_resp and me_resp.status_code == 200:
        user = me_resp.json()
        name = user.get("first_name") or user["username"]
        await notify_recipe_suggested(callback.bot, name, title, tg_id)


@router.callback_query(F.data == "suggest_cancel")
async def cb_suggest_cancel(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer("Отменено.")
```

- [ ] **Step 2: Commit**

```bash
git add bot/app/handlers/suggest.py
git commit -m "feat(bot): /suggest с FSM поиском и inline-выбором"
```

---

### Task 11: Bot — /recipes handler with pagination

**Files:**
- Create: `bot/app/handlers/recipes.py`

- [ ] **Step 1: Create `bot/app/handlers/recipes.py`**

```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.api_client import api, NOT_LINKED_MSG

router = Router()

PAGE_SIZE = 10


def build_recipes_keyboard(recipes: list[dict], page: int) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_recipes = recipes[start:end]

    buttons = [[InlineKeyboardButton(text=r["title"], callback_data=f"recipe_noop")] for r in page_recipes]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"recipes_page:{page - 1}"))
    if end < len(recipes):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"recipes_page:{page + 1}"))
    if nav:
        buttons.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("recipes"))
async def cmd_recipes(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.get("/api/recipes", tg_id)

    if resp is None:
        await message.answer(NOT_LINKED_MSG)
        return

    recipes = resp.json()
    if not recipes:
        await message.answer("Рецептов пока нет.")
        return

    total = len(recipes)
    await message.answer(
        f"📖 Рецепты ({total}):",
        reply_markup=build_recipes_keyboard(recipes, 0),
    )


@router.callback_query(F.data.startswith("recipes_page:"))
async def cb_recipes_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    tg_id = callback.from_user.id

    resp = await api.get("/api/recipes", tg_id)
    if resp is None:
        await callback.answer(NOT_LINKED_MSG)
        return

    recipes = resp.json()
    await callback.message.edit_reply_markup(reply_markup=build_recipes_keyboard(recipes, page))
    await callback.answer()


@router.callback_query(F.data == "recipe_noop")
async def cb_recipe_noop(callback: CallbackQuery) -> None:
    await callback.answer()
```

- [ ] **Step 2: Commit**

```bash
git add bot/app/handlers/recipes.py
git commit -m "feat(bot): /recipes с пагинацией"
```

---

### Task 12: Bot — /mute and /unmute handlers

**Files:**
- Create: `bot/app/handlers/notifications.py`

- [ ] **Step 1: Create `bot/app/handlers/notifications.py`**

```python
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.api_client import api, NOT_LINKED_MSG

router = Router()


@router.message(Command("mute"))
async def cmd_mute(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.patch("/api/auth/me", tg_id, json={"notifications_enabled": False})

    if resp is None:
        await message.answer(NOT_LINKED_MSG)
        return

    await message.answer("🔇 Уведомления отключены. Используйте /unmute чтобы включить.")


@router.message(Command("unmute"))
async def cmd_unmute(message: Message) -> None:
    tg_id = message.from_user.id
    resp = await api.patch("/api/auth/me", tg_id, json={"notifications_enabled": True})

    if resp is None:
        await message.answer(NOT_LINKED_MSG)
        return

    await message.answer("🔔 Уведомления включены.")
```

- [ ] **Step 2: Commit**

```bash
git add bot/app/handlers/notifications.py
git commit -m "feat(bot): /mute и /unmute команды"
```

---

### Task 13: Infrastructure — Docker Compose, Cron, Ansible

**Files:**
- Modify: `infra/docker/docker-compose.yml`
- Modify: `infra/docker/cron/crontab`
- Modify: `infra/ansible/roles/app/tasks/main.yml`
- Modify: `infra/ansible/roles/app/templates/env.j2`

- [ ] **Step 1: Add bot service to docker-compose.yml**

After the `cron` service block (line 102), add:

```yaml
  bot:
    build:
      context: ./bot
    container_name: bot
    restart: unless-stopped
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      BOT_SECRET: ${BOT_SECRET}
      BACKEND_URL: http://backend:8000
      WEBHOOK_HOST: https://bot.${DOMAIN}
      CRON_SECRET: ${CRON_SECRET}
    networks:
      - web
    depends_on:
      backend:
        condition: service_healthy
    labels:
      - traefik.enable=true
      - traefik.http.routers.bot.rule=Host(`bot.${DOMAIN}`)
      - traefik.http.routers.bot.entrypoints=websecure
      - traefik.http.routers.bot.tls.certresolver=letsencrypt
      - traefik.http.services.bot.loadbalancer.server.port=8080
      - traefik.docker.network=web
```

- [ ] **Step 2: Update crontab**

Replace the contents of `infra/docker/cron/crontab` with:

```
# Создать меню на сегодня (8:00 GMT+3 = 05:00 UTC)
0 5 * * * curl -s -X POST http://backend:8000/api/menus/create-daily -H "X-Cron-Secret: $CRON_SECRET" -H "Content-Type: application/json" -d '{}' >> /var/log/cron.log 2>&1 && curl -s -X POST http://bot:8080/notify -H "X-Cron-Secret: $CRON_SECRET" -H "Content-Type: application/json" -d '{"event":"menu_created"}' >> /var/log/cron.log 2>&1

# Финализировать список (13:00 GMT+3 = 10:00 UTC)
0 10 * * * curl -s -X POST http://backend:8000/api/menus/finalize -H "X-Cron-Secret: $CRON_SECRET" -H "Content-Type: application/json" -d '{}' >> /var/log/cron.log 2>&1 && curl -s -X POST http://bot:8080/notify -H "X-Cron-Secret: $CRON_SECRET" -H "Content-Type: application/json" -d '{"event":"voting_opened"}' >> /var/log/cron.log 2>&1

# Закрыть голосование (17:00 GMT+3 = 14:00 UTC)
0 14 * * * curl -s -X POST http://backend:8000/api/menus/close-voting -H "X-Cron-Secret: $CRON_SECRET" -H "Content-Type: application/json" -d '{}' >> /var/log/cron.log 2>&1 && curl -s -X POST http://bot:8080/notify -H "X-Cron-Secret: $CRON_SECRET" -H "Content-Type: application/json" -d '{"event":"voting_closed"}' >> /var/log/cron.log 2>&1
```

- [ ] **Step 3: Add bot sync to Ansible tasks**

In `infra/ansible/roles/app/tasks/main.yml`, add after the frontend sync block (after line 61):

```yaml
- name: Sync bot source
  ansible.posix.synchronize:
    src: "{{ inventory_dir }}/../../../bot/"
    dest: /opt/home-page/bot/
    dest_port: "{{ ansible_port | int }}"
    delete: true
    rsync_opts:
      - "--exclude=__pycache__"
      - "--exclude=.pytest_cache"
  notify: Recreate containers
```

- [ ] **Step 4: Add WEBHOOK_HOST to env.j2**

In `infra/ansible/roles/app/templates/env.j2`, add at the end:

```
WEBHOOK_HOST=https://bot.{{ vault_domain }}
```

- [ ] **Step 5: Commit**

```bash
git add infra/docker/docker-compose.yml infra/docker/cron/crontab infra/ansible/roles/app/tasks/main.yml infra/ansible/roles/app/templates/env.j2
git commit -m "infra: добавлен bot сервис в Docker Compose, cron, Ansible"
```

---

### Task 14: CI — Bot workflow

**Files:**
- Create: `.github/workflows/bot.yml`

- [ ] **Step 1: Create `.github/workflows/bot.yml`**

```yaml
name: Bot CI

on:
  push:
    branches: [main]
    paths:
      - "bot/**"
      - ".github/workflows/bot.yml"
  pull_request:
    paths:
      - "bot/**"
      - ".github/workflows/bot.yml"

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"

jobs:
  lint:
    runs-on: ubuntu-latest

    defaults:
      run:
        working-directory: bot

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install ruff
        run: pip install ruff

      - name: Lint
        run: ruff check app
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/bot.yml
git commit -m "ci: добавлен Bot CI workflow (lint)"
```

---

### Task 15: Backend — Update `get_current_user` to support Bearer token

The bot sends JWT as `Authorization: Bearer <token>`, but `get_current_user` only reads from cookies. Fix this.

**Files:**
- Modify: `backend/app/core/dependencies.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Update dependency**

In `backend/app/core/dependencies.py`, modify `get_current_user` to also accept Bearer token:

```python
async def get_current_user(
    session: DbSession,
    access_token: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token = access_token
    if token is None and authorization and authorization.startswith("Bearer "):
        token = authorization[7:]

    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_jwt(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = await get_user_by_id(session, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
```

- [ ] **Step 2: Write test**

In `backend/tests/test_auth.py`, add:

```python
# ---------- BEARER TOKEN AUTH ----------

async def test_me_with_bearer_token(client: AsyncClient, test_user: User):
    """Bot-style auth: get JWT from telegram-login, use as Bearer token."""
    import hashlib, hmac, time
    BOT_TOKEN = "test-bot-token"
    BOT_SECRET = "test-bot-secret"

    # Link tg_id to test_user
    await client.post("/api/auth/login", json={"username": "testuser", "password": "test12345"})
    payload = {"id": 77777, "first_name": "Test", "auth_date": int(time.time())}
    check_string = "\n".join(f"{k}={payload[k]}" for k in sorted(payload.keys()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    payload["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    await client.post("/api/auth/telegram-verify", json=payload)

    # Get token via telegram-login
    resp = await client.post(
        "/api/auth/telegram-login",
        headers={"X-Bot-Secret": BOT_SECRET},
        json={"tg_id": 77777},
    )
    token = resp.json()["access_token"]

    # Use Bearer token (no cookies)
    from httpx import ASGITransport, AsyncClient as HC
    from app.main import app
    from app.core.dependencies import get_db
    transport = ASGITransport(app=app)
    async with HC(transport=transport, base_url="http://test") as bearer_client:
        app.dependency_overrides[get_db] = lambda: client._transport  # reuse
        me_resp = await bearer_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "testuser"
```

Actually, let me simplify this test — use the existing client fixture approach:

```python
async def test_me_with_bearer_token(client: AsyncClient, test_user: User):
    """Bot-style: telegram-login returns JWT, usable as Bearer token."""
    import hashlib, hmac, time
    BOT_TOKEN = "test-bot-token"
    BOT_SECRET = "test-bot-secret"

    # Login and link tg_id
    await client.post("/api/auth/login", json={"username": "testuser", "password": "test12345"})
    payload = {"id": 77777, "first_name": "Test", "auth_date": int(time.time())}
    check_string = "\n".join(f"{k}={payload[k]}" for k in sorted(payload.keys()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    payload["hash"] = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    await client.post("/api/auth/telegram-verify", json=payload)

    # Get JWT via telegram-login
    login_resp = await client.post(
        "/api/auth/telegram-login",
        headers={"X-Bot-Secret": BOT_SECRET},
        json={"tg_id": 77777},
    )
    token = login_resp.json()["access_token"]

    # Clear cookies, use Bearer header only
    client.cookies.clear()
    me_resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "testuser"
```

- [ ] **Step 3: Run tests**

Run: `pytest -v`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/dependencies.py backend/tests/test_auth.py
git commit -m "feat: поддержка Bearer token в get_current_user для бота"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|---|---|
| Webhook on bot.telnor.ru | Task 6 (main.py), Task 13 (docker-compose + traefik labels) |
| Auth via telegram-login + JWT cache | Task 5 (api_client) |
| Not linked → message | Task 5 (NOT_LINKED_MSG), used in all handlers |
| /start, /help | Task 7 |
| /menu | Task 8 |
| /vote with cancel | Task 9 |
| /suggest with FSM search | Task 10 |
| /recipes with pagination | Task 11 |
| /mute, /unmute | Task 12 |
| notifications_enabled field + migration | Task 1 |
| GET /auth/users/notifiable | Task 2 |
| GET /recipes/search?q= | Task 3 |
| 4 notification types | Task 6 (notify.py) |
| Cron triggers /notify | Task 13 (crontab) |
| Docker Compose bot service | Task 13 |
| Ansible sync | Task 13 |
| CI workflow | Task 14 |
| Bearer token support | Task 15 |
| Error messages (not voting, not collecting, no menu) | Tasks 8, 9, 10 |

### Missing from original spec — found during review

- Bearer token support in `get_current_user` was not in the spec but is required for the bot to work (bot sends JWT in header, not cookie). Added as Task 15.
