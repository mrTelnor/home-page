# knowledge-mcp

MCP server exposing personal knowledge base (Postgres + PostgREST) to Claude Desktop.

## Install

```
pip install -e .
```

## Configure Claude Desktop

`%APPDATA%\Claude\claude_desktop_config.json` (or platform equivalent):

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "knowledge-mcp",
      "env": {
        "KNOWLEDGE_URL": "https://knowledge.telnor.ru",
        "KNOWLEDGE_BACKEND_URL": "https://api.telnor.ru",
        "KNOWLEDGE_USERNAME": "<admin>",
        "KNOWLEDGE_PASSWORD": "<pass>"
      }
    }
  }
}
```

Tools exposed:
- `list_notebooks`, `create_notebook`
- `search_notes`, `get_note`, `list_notes`
- `create_note`, `update_note`, `delete_note`
- `get_backlinks`
