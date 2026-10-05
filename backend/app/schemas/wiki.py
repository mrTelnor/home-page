import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class WikiHealthResponse(BaseModel):
    status: Literal["ok", "unavailable", "disabled"]


class WikiNotebookNode(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None
    # Заметок непосредственно в блокноте
    note_count: int
    # Заметок в блокноте и во всех вложенных
    total_note_count: int
    children: list["WikiNotebookNode"] = []


class WikiNotebookRef(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class WikiNoteSummary(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    notebook_id: uuid.UUID | None
    metadata: dict[str, Any]
    tags: list[str]
    updated_at: datetime


class WikiNoteLink(BaseModel):
    """Ссылка между заметками: для исходящих — цель, для обратных — источник."""

    slug: str
    title: str
    alias: str | None


class WikiNoteDetail(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    content: str
    metadata: dict[str, Any]
    notebook: WikiNotebookRef | None
    tags: list[str]
    links: list[WikiNoteLink]
    backlinks: list[WikiNoteLink]
    created_at: datetime
    updated_at: datetime
