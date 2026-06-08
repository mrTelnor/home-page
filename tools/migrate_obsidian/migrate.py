"""Two-pass migration: walk vault → INSERT notebooks → INSERT notes → INSERT links."""
from __future__ import annotations

import logging
from pathlib import Path

from migrate_obsidian.auth import TokenManager
from migrate_obsidian.client import PostgRESTClient
from migrate_obsidian.parser import parse_note
from migrate_obsidian.slugify import slugify

logger = logging.getLogger(__name__)


async def migrate_vault(*, vault_path: Path, knowledge_url: str,
                        backend_url: str, username: str, password: str) -> None:
    tm = TokenManager(backend_url=backend_url, username=username, password=password)
    client = PostgRESTClient(base_url=knowledge_url, token_manager=tm)
    try:
        notebooks_by_folder: dict[str, str] = {}
        for folder in sorted(p for p in vault_path.iterdir() if p.is_dir()):
            slug = slugify(folder.name)
            nb = await client.create_notebook(name=folder.name, slug=slug)
            notebooks_by_folder[folder.name] = nb["id"]
            logger.info("created notebook %r", folder.name)

        title_to_id: dict[str, str] = {}
        notes_to_link: list[tuple[str, list]] = []

        for md_file in sorted(vault_path.rglob("*.md")):
            try:
                folder = md_file.relative_to(vault_path).parts[0]
            except (IndexError, ValueError):
                continue
            if folder not in notebooks_by_folder:
                continue
            parsed = parse_note(md_file)
            slug = f"{slugify(folder)}/{slugify(parsed.title)}"
            note = await client.create_note(
                notebook_id=notebooks_by_folder[folder],
                title=parsed.title, slug=slug,
                content=parsed.content, metadata=parsed.metadata,
                tags=parsed.tags,
            )
            title_to_id[parsed.title] = note["id"]
            notes_to_link.append((note["id"], parsed.links))
            logger.info("created note %r", parsed.title)

        for source_id, links in notes_to_link:
            for link in links:
                target_id = title_to_id.get(link.target)
                if target_id is None:
                    logger.warning("unresolved link %s → %r", source_id, link.target)
                    continue
                await client.create_link(
                    source_id=source_id, target_id=target_id, alias=link.alias,
                )
    finally:
        await client.aclose()
        await tm.aclose()
