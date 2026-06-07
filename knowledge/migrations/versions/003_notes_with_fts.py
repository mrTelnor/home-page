"""notes with FTS

Revision ID: 003_notes_with_fts
Revises: 002_notebooks
"""
from typing import Sequence

from alembic import op

revision: str = "003_notes_with_fts"
down_revision: str | Sequence[str] | None = "002_notebooks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE notes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            notebook_id UUID REFERENCES notebooks(id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL DEFAULT '',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            search_vector TSVECTOR,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_notes_notebook ON notes(notebook_id)")
    op.execute("CREATE INDEX idx_notes_metadata ON notes USING GIN(metadata)")
    op.execute("CREATE INDEX idx_notes_search ON notes USING GIN(search_vector)")

    op.execute("""
        CREATE OR REPLACE FUNCTION notes_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('simple', coalesce(NEW.content, '')), 'B');
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_notes_search_vector
        BEFORE INSERT OR UPDATE OF title, content ON notes
        FOR EACH ROW EXECUTE FUNCTION notes_search_vector_update()
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notes")
    op.execute("DROP FUNCTION IF EXISTS notes_search_vector_update")
