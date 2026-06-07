"""note_links + backlinks_view

Revision ID: 005_note_links_and_view
Revises: 004_tags
"""
from typing import Sequence

from alembic import op

revision: str = "005_note_links_and_view"
down_revision: str | Sequence[str] | None = "004_tags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE note_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            target_note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            alias TEXT,
            CONSTRAINT note_links_no_self CHECK (source_note_id <> target_note_id),
            UNIQUE (source_note_id, target_note_id, alias)
        )
    """)
    op.execute("CREATE INDEX idx_note_links_source ON note_links(source_note_id)")
    op.execute("CREATE INDEX idx_note_links_target ON note_links(target_note_id)")
    op.execute("""
        CREATE VIEW backlinks_view AS
        SELECT
            t.slug AS target_slug, t.id AS target_id,
            s.slug AS source_slug, s.id AS source_id,
            s.title AS source_title, l.alias
        FROM note_links l
        JOIN notes s ON s.id = l.source_note_id
        JOIN notes t ON t.id = l.target_note_id
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS backlinks_view")
    op.execute("DROP TABLE IF EXISTS note_links")
