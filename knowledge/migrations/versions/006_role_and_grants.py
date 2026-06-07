"""knowledge_rw role + grants

Revision ID: 006_role_and_grants
Revises: 005_note_links_and_view
"""
from typing import Sequence

from alembic import op

revision: str = "006_role_and_grants"
down_revision: str | Sequence[str] | None = "005_note_links_and_view"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NOLOGIN: PostgREST switches to this role via SET ROLE based on JWT claim;
    # actual Postgres login happens as the superuser from POSTGRES_USER.
    op.execute("DO $$ BEGIN CREATE ROLE knowledge_rw NOLOGIN; "
               "EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.execute("GRANT USAGE ON SCHEMA public TO knowledge_rw")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO knowledge_rw")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO knowledge_rw")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public "
               "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO knowledge_rw")


def downgrade() -> None:
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM knowledge_rw")
    op.execute("REVOKE ALL ON SCHEMA public FROM knowledge_rw")
    op.execute("DROP ROLE IF EXISTS knowledge_rw")
