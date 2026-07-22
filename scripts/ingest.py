"""CLI entrypoint for content ingestion.

Thin wrapper around app.rag.ingest.ingest_content(). Run manually with:

    ./venv/bin/python scripts/ingest.py

The core logic lives in app/rag/ingest.py so it can also be invoked from the
running application (see app/main.py lifespan).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag.ingest import MissingIngestEnv, ingest_content  # noqa: E402
from app.rag.neo4j_client import close_driver  # noqa: E402


async def main() -> None:
    try:
        summary = await ingest_content()
    except MissingIngestEnv as e:
        raise SystemExit(str(e))
    finally:
        await close_driver()

    if summary["changed"]:
        print(
            f"Ingestion complete. embedded={summary['embedded']} "
            f"deleted={summary['deleted']} chunks={summary['chunks']}"
        )
    else:
        print("No changes detected. Database is up to date!")


if __name__ == "__main__":
    asyncio.run(main())
