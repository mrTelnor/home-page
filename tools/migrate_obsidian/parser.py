"""Parse one Obsidian .md file into a dataclass."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]")
_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-zА-Яа-яЁё_][\w/-]*)", re.UNICODE)


@dataclass
class Link:
    target: str
    alias: str | None


@dataclass
class ParsedNote:
    title: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)


def parse_note(path: Path) -> ParsedNote:
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    metadata = dict(post.metadata)
    body = post.content

    tags: list[str] = []
    fm_tags = metadata.pop("tags", None) or []
    if isinstance(fm_tags, str):
        fm_tags = [fm_tags]
    tags.extend(fm_tags)
    for m in _TAG_RE.finditer(body):
        if m.group(1) not in tags:
            tags.append(m.group(1))

    links = [
        Link(
            target=m.group(1).strip(),
            alias=m.group(2).strip() if m.group(2) else None,
        )
        for m in _WIKILINK_RE.finditer(body)
    ]

    return ParsedNote(
        title=path.stem, content=body, metadata=metadata, tags=tags, links=links,
    )
