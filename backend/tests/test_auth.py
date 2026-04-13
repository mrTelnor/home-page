from httpx import AsyncClient

from app.db.models.user import User


# ---------- REGISTER ----------

async def test_register_success(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "password123", "invite_code": "test-invite"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["role"] == "user"
    assert "id" in data


async def test_register_invalid_invite_code(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "password123", "invite_code": "wrong"},
    )
    assert response.status_code == 403


async def test_register_duplicate_username(client: AsyncClient, test_user: User):
    response = await client.post(
        "/api/auth/register",
        json={"username": "testuser", "password": "password123", "invite_code": "test-invite"},
    )
    assert response.status_code == 409


async def test_register_case_insensitive(client: AsyncClient, test_user: User):
    # Пользователь testuser уже есть; пытаемся с TestUser
    response = await client.post(
        "/api/auth/register",
        json={"username": "TestUser", "password": "password123", "invite_code": "test-invite"},
    )
    assert response.status_code == 409


async def test_register_short_password(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "short", "invite_code": "test-invite"},
    )
    assert response.status_code == 422


# ---------- LOGIN ----------

async def test_login_success(client: AsyncClient, test_user: User):
    response = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "test12345"},
    )
    assert response.status_code == 200
    assert "access_token" in response.cookies


async def test_login_case_insensitive(client: AsyncClient, test_user: User):
    response = await client.post(
        "/api/auth/login",
        json={"username": "TestUser", "password": "test12345"},
    )
    assert response.status_code == 200


async def test_login_wrong_password(client: AsyncClient, test_user: User):
    response = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "wrong"},
    )
    assert response.status_code == 401


async def test_login_unknown_user(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"username": "ghost", "password": "test12345"},
    )
    assert response.status_code == 401


# ---------- ME ----------

async def test_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(authed_client: AsyncClient):
    response = await authed_client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "user"
    assert data["tg_id"] is None


# ---------- LOGOUT ----------

async def test_logout(authed_client: AsyncClient):
    response = await authed_client.post("/api/auth/logout")
    assert response.status_code == 200


# ---------- CHANGE PASSWORD ----------

async def test_change_password_success(authed_client: AsyncClient):
    response = await authed_client.post(
        "/api/auth/change-password",
        json={"old_password": "test12345", "new_password": "newpassword123"},
    )
    assert response.status_code == 200

    # Старый пароль больше не работает
    login_old = await authed_client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "test12345"},
    )
    assert login_old.status_code == 401

    # Новый работает
    login_new = await authed_client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "newpassword123"},
    )
    assert login_new.status_code == 200


async def test_change_password_wrong_old(authed_client: AsyncClient):
    response = await authed_client.post(
        "/api/auth/change-password",
        json={"old_password": "wrong", "new_password": "newpassword123"},
    )
    assert response.status_code == 401


async def test_change_password_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/auth/change-password",
        json={"old_password": "a", "new_password": "newpassword123"},
    )
    assert response.status_code == 401


# ---------- PATCH /me (update profile) ----------

async def test_update_profile(authed_client: AsyncClient):
    response = await authed_client.patch(
        "/api/auth/me",
        json={
            "first_name": "Никита",
            "birthday": "1990-05-15",
            "is_volkov": True,
            "gender": "male",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Никита"
    assert data["birthday"] == "1990-05-15"
    assert data["is_volkov"] is True
    assert data["gender"] == "male"


async def test_update_profile_partial(authed_client: AsyncClient):
    await authed_client.patch("/api/auth/me", json={"first_name": "Никита", "is_volkov": True})
    response = await authed_client.patch("/api/auth/me", json={"gender": "male"})
    data = response.json()
    assert data["first_name"] == "Никита"
    assert data["is_volkov"] is True
    assert data["gender"] == "male"


async def test_update_profile_requires_auth(client: AsyncClient):
    response = await client.patch("/api/auth/me", json={"first_name": "X"})
    assert response.status_code == 401
