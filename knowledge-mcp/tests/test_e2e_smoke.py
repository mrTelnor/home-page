"""Skip-by-default smoke test against production knowledge.telnor.ru.
Set KNOWLEDGE_USERNAME, KNOWLEDGE_PASSWORD env vars to enable."""
import os

import pytest

from knowledge_mcp.auth import TokenManager
from knowledge_mcp.client import KnowledgeClient


@pytest.mark.skipif(
    not (os.environ.get("KNOWLEDGE_USERNAME") and os.environ.get("KNOWLEDGE_PASSWORD")),
    reason="set KNOWLEDGE_USERNAME/PASSWORD to run e2e tests against production",
)
async def test_real_list_notebooks():
    tm = TokenManager(
        backend_url=os.environ.get("KNOWLEDGE_BACKEND_URL", "https://api.telnor.ru"),
        username=os.environ["KNOWLEDGE_USERNAME"],
        password=os.environ["KNOWLEDGE_PASSWORD"],
    )
    client = KnowledgeClient(
        base_url=os.environ.get("KNOWLEDGE_URL", "https://knowledge.telnor.ru"),
        token_manager=tm,
    )
    try:
        notebooks = await client.list_notebooks()
        assert isinstance(notebooks, list)
    finally:
        await client.aclose()
        await tm.aclose()
