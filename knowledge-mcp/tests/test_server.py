from unittest.mock import MagicMock

from knowledge_mcp.client import KnowledgeClient
from knowledge_mcp.server import build_server


async def test_server_registers_expected_tools():
    """FastMCP-based server: list_tools() returns 9 expected tools."""
    # Inject a dummy client so build_server doesn't try to read env
    mock_client = MagicMock(spec=KnowledgeClient)
    server = build_server(client=mock_client)
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "list_notebooks", "create_notebook",
        "search_notes", "get_note", "list_notes",
        "create_note", "update_note", "delete_note",
        "get_backlinks",
    }
