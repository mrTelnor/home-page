import json
from pathlib import Path

import httpx
import respx

from migrate_obsidian.migrate import migrate_vault

FIXTURES = Path(__file__).parent / "fixtures"


@respx.mock
async def test_migrate_two_notes_one_link():
    posts = {"/notebooks": [], "/notes": [], "/note_links": [], "/tags": [], "/note_tags": []}
    note_ids = {"Hello": "h-1", "Other": "o-1"}

    respx.post("https://backend/api/auth/knowledge-token").mock(
        return_value=httpx.Response(200, json={
            "access_token": "tok", "token_type": "bearer", "expires_in": 86400,
        })
    )

    def notebooks_h(r):
        posts["/notebooks"].append(json.loads(r.content))
        return httpx.Response(201, json=[{"id": "nb-1", "name": "Personal", "slug": "personal"}])

    def notes_h(r):
        d = json.loads(r.content)
        posts["/notes"].append(d)
        return httpx.Response(201, json=[{"id": note_ids[d["title"]],
                                            "title": d["title"], "slug": d["slug"]}])

    def tags_h(r):
        posts["/tags"].append(json.loads(r.content))
        return httpx.Response(201, json=[{"id": "tag-personal", "name": "personal"}])

    def note_tags_h(r):
        posts["/note_tags"].append(json.loads(r.content))
        return httpx.Response(201, json=[])

    def note_links_h(r):
        posts["/note_links"].append(json.loads(r.content))
        return httpx.Response(201, json=[])

    respx.post("https://knowledge/notebooks").mock(side_effect=notebooks_h)
    respx.post("https://knowledge/notes").mock(side_effect=notes_h)
    respx.post("https://knowledge/tags").mock(side_effect=tags_h)
    respx.post("https://knowledge/note_tags").mock(side_effect=note_tags_h)
    respx.post("https://knowledge/note_links").mock(side_effect=note_links_h)

    await migrate_vault(
        vault_path=FIXTURES / "vault",
        knowledge_url="https://knowledge",
        backend_url="https://backend",
        username="u", password="p",
    )

    assert len(posts["/notebooks"]) == 1
    titles = sorted(p["title"] for p in posts["/notes"])
    assert titles == ["Hello", "Other"]
    assert len(posts["/note_links"]) == 1
    assert posts["/note_links"][0]["source_note_id"] == note_ids["Hello"]
    assert posts["/note_links"][0]["target_note_id"] == note_ids["Other"]
