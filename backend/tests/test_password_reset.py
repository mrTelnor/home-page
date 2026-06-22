import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models.password_reset import PasswordResetToken
from app.db.models.user import User
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
