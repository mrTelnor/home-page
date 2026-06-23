import uuid

from httpx import AsyncClient

from tests.conftest import _create_user_standalone


async def test_admin_lists_users_with_flags(admin_client: AsyncClient):
    await _create_user_standalone("with_tg", tg_id=42)
    await _create_user_standalone("with_mail", email="m@x.com")
    resp = await admin_client.get("/api/auth/admin/users")
    assert resp.status_code == 200
    by_name = {u["username"]: u for u in resp.json()}
    assert by_name["with_tg"]["has_telegram"] is True
    assert by_name["with_tg"]["has_email"] is False
    assert by_name["with_mail"]["has_email"] is True


async def test_non_admin_forbidden(authed_client: AsyncClient):
    resp = await authed_client.get("/api/auth/admin/users")
    assert resp.status_code == 403


async def test_admin_generates_reset_link(admin_client: AsyncClient):
    target = await _create_user_standalone("victim")
    resp = await admin_client.post(f"/api/auth/admin/users/{target.id}/reset-link")
    assert resp.status_code == 200
    body = resp.json()
    assert "/reset-password?token=" in body["link"]
    assert "expires_at" in body
    # ссылка рабочая
    raw = body["link"].split("token=")[1]
    confirm = await admin_client.post(
        "/api/auth/password-reset/confirm",
        json={"token": raw, "new_password": "adminset123"},
    )
    assert confirm.status_code == 200


async def test_admin_reset_link_unknown_user_404(admin_client: AsyncClient):
    resp = await admin_client.post(f"/api/auth/admin/users/{uuid.uuid4()}/reset-link")
    assert resp.status_code == 404
