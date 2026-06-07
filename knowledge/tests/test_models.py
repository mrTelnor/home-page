from sqlalchemy import select

from knowledge.models import Base  # noqa: F401 — sanity import
from knowledge.models.entities import Notebook, Note, Tag


async def test_notebook_roundtrip(db_session):
    nb = Notebook(name="My", slug="my")
    db_session.add(nb)
    await db_session.flush()
    fetched = (await db_session.execute(select(Notebook).where(Notebook.slug == "my"))).scalar_one()
    assert fetched.name == "My"
    await db_session.rollback()


async def test_note_roundtrip(db_session):
    nb = Notebook(name="N", slug="n")
    db_session.add(nb)
    await db_session.flush()
    note = Note(notebook_id=nb.id, title="Hello", slug="n/hello", content="body")
    db_session.add(note)
    await db_session.flush()
    fetched = (await db_session.execute(select(Note).where(Note.slug == "n/hello"))).scalar_one()
    assert fetched.title == "Hello"
    assert fetched.content == "body"
    await db_session.rollback()
