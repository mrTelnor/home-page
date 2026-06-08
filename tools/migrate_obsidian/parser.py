"""Parse one Obsidian .md file into a dataclass."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import frontmatter
import yaml

logger = logging.getLogger(__name__)

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]")
_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-zА-Яа-яЁё_][\w/-]*)", re.UNICODE)


def _jsonable(value: Any) -> Any:
    """Convert date/datetime to ISO strings recursively — PyYAML parses
    `created: 2026-05-01` as `datetime.date`, which json.dumps can't serialize.
    Stored as ISO-8601 strings in JSONB; ordering/comparison still works."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


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
    raw = path.read_text(encoding="utf-8")
    try:
        post = frontmatter.loads(raw)
        metadata = _jsonable(dict(post.metadata))
        body = post.content
    except yaml.YAMLError as exc:
        # Invalid YAML frontmatter — import the file as plain markdown without
        # parsed metadata. Better than crashing the whole migration.
        logger.warning("invalid YAML frontmatter in %s, importing as plain: %s",
                       path, exc)
        metadata = {}
        body = raw

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
