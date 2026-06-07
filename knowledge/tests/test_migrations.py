from sqlalchemy import text


async def test_notebooks_table_columns(db_session):
    result = await db_session.execute(text("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='notebooks'
    """))
    cols = {r[0]: r[1] for r in result.all()}
    assert cols["id"] == "uuid"
    assert cols["slug"] == "text"
    assert cols["parent_id"] == "uuid"


async def test_notebooks_parent_fk(db_session):
    await db_session.execute(text("INSERT INTO notebooks (name, slug) VALUES ('r', 'r')"))
    await db_session.execute(text("""
        INSERT INTO notebooks (name, slug, parent_id)
        VALUES ('c', 'r/c', (SELECT id FROM notebooks WHERE slug='r'))
    """))
    result = await db_session.execute(text(
        "SELECT count(*) FROM notebooks WHERE parent_id IS NOT NULL"
    ))
    assert result.scalar() == 1
    await db_session.rollback()
