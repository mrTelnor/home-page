"""notebooks

Revision ID: 002_notebooks
Revises: 001_initial
"""
from typing import Sequence

from alembic import op

revision: str = "002_notebooks"
down_revision: str | Sequence[str] | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute("""
        CREATE TABLE notebooks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            parent_id UUID REFERENCES notebooks(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_notebooks_parent ON notebooks(parent_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notebooks")
