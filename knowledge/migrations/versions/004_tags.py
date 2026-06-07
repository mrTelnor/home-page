"""tags

Revision ID: 004_tags
Revises: 003_notes_with_fts
"""
from typing import Sequence

from alembic import op

revision: str = "004_tags"
down_revision: str | Sequence[str] | None = "003_notes_with_fts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE tags (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL UNIQUE
        )
    """)
    op.execute("""
        CREATE TABLE note_tags (
            note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        )
    """)
    op.execute("CREATE INDEX idx_note_tags_tag ON note_tags(tag_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS note_tags")
    op.execute("DROP TABLE IF EXISTS tags")
