import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import generate_reset_token, hash_reset_token
from app.db.models.password_reset import PasswordResetToken
from app.db.models.user import User
from app.services import password_reset as pr
from tests.conftest import TestSessionMaker, _create_user_standalone


async def test_password_reset_token_persists():
    user = await _create_user_standalone("tok_user")
    async with TestSessionMaker() as session:
        token = PasswordResetToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash="a" * 64,
            channel="email",
            expires_at=datetime.now(UTC) + timedelta(minutes=60),
        )
        session.add(token)
        await session.commit()
        rows = (await session.execute(select(PasswordResetToken))).scalars().all()
        assert len(rows) == 1
        assert rows[0].used_at is None


async def test_user_has_password_changed_at_column():
    user = await _create_user_standalone("pca_user")
    assert user.password_changed_at is None


def test_token_hash_is_not_raw_and_stable():
    raw = generate_reset_token()
    h = hash_reset_token(raw)
    assert raw != h
    assert len(h) == 64
    assert hash_reset_token(raw) == h


async def test_create_and_get_valid_token():
    user = await _create_user_standalone("crt_user")
    async with TestSessionMaker() as session:
        u = await session.get(User, user.id)
        raw, expires_at = await pr.create_reset_token(session, u, "email")
        assert expires_at > datetime.now(UTC)
        token = await pr.get_valid_token(session, raw)
        assert token is not None
        assert token.user_id == user.id


async def test_new_token_invalidates_previous():
    user = await _create_user_standalone("inv_user")
    async with TestSessionMaker() as session:
        u = await session.get(User, user.id)
        raw1, _ = await pr.create_reset_token(session, u, "email")
        raw2, _ = await pr.create_reset_token(session, u, "email")
        assert await pr.get_valid_token(session, raw1) is None
        assert await pr.get_valid_token(session, raw2) is not None


async def test_expired_token_is_invalid():
    user = await _create_user_standalone("exp_user")
    async with TestSessionMaker() as session:
        u = await session.get(User, user.id)
        raw = generate_reset_token()
        session.add(PasswordResetToken(
            id=uuid.uuid4(), user_id=u.id, token_hash=hash_reset_token(raw),
            channel="email", expires_at=datetime.now(UTC) - timedelta(minutes=1),
        ))
        await session.commit()
        assert await pr.get_valid_token(session, raw) is None


async def test_throttle_after_5_requests():
    user = await _create_user_standalone("thr_user")
    async with TestSessionMaker() as session:
        u = await session.get(User, user.id)
        for _ in range(5):
            await pr.create_reset_token(session, u, "email")
        assert await pr.is_throttled(session, u) is True
