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


async def test_notes_columns(db_session):
    result = await db_session.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='notes'
    """))
    cols = {r[0] for r in result.all()}
    assert cols >= {"id", "notebook_id", "title", "slug", "content",
                    "metadata", "search_vector", "created_at", "updated_at"}


async def test_fts_trigger_updates_search_vector(db_session):
    await db_session.execute(text("INSERT INTO notebooks (name, slug) VALUES ('nb', 'nb')"))
    await db_session.execute(text("""
        INSERT INTO notes (notebook_id, title, slug, content)
        VALUES ((SELECT id FROM notebooks WHERE slug='nb'),
                'Hello World', 'nb/hello', 'тестовое содержимое')
    """))
    vec = (await db_session.execute(text(
        "SELECT search_vector::text FROM notes WHERE slug='nb/hello'"
    ))).scalar()
    assert vec is not None
    assert "hello" in vec.lower()
    assert "содерж" in vec.lower()
    await db_session.rollback()


async def test_tags_many_to_many(db_session):
    await db_session.execute(text("INSERT INTO notebooks (name, slug) VALUES ('nb', 'nb')"))
    await db_session.execute(text("""
        INSERT INTO notes (notebook_id, title, slug)
        VALUES ((SELECT id FROM notebooks WHERE slug='nb'), 'n1', 'nb/n1')
    """))
    await db_session.execute(text("INSERT INTO tags (name) VALUES ('work'), ('idea')"))
    await db_session.execute(text("""
        INSERT INTO note_tags (note_id, tag_id)
        SELECT n.id, t.id FROM notes n CROSS JOIN tags t WHERE n.slug='nb/n1'
    """))
    assert (await db_session.execute(text("SELECT count(*) FROM note_tags"))).scalar() == 2
    await db_session.rollback()
