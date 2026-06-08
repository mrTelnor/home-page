"""CLI: python -m migrate_obsidian <vault-path> [opts]"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from migrate_obsidian.migrate import migrate_vault


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault", type=Path)
    parser.add_argument("--knowledge-url", default="https://knowledge.telnor.ru")
    parser.add_argument("--backend-url", default="https://api.telnor.ru")
    parser.add_argument("--username", default=os.environ.get("KNOWLEDGE_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("KNOWLEDGE_PASSWORD"))
    args = parser.parse_args(argv)
    if not args.username or not args.password:
        print("ERROR: provide --username/--password or KNOWLEDGE_USERNAME/PASSWORD env",
              file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(migrate_vault(
        vault_path=args.vault,
        knowledge_url=args.knowledge_url, backend_url=args.backend_url,
        username=args.username, password=args.password,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
