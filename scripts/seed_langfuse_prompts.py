"""CLI to seed Langfuse Prompt Management with the bundled default prompts.

Run once after enabling Langfuse to create the managed prompts:

    ./venv/bin/python scripts/seed_langfuse_prompts.py

Existing prompts are left untouched. Pass --force to push the current bundled
defaults as a new "production" version of every prompt (use after editing the
defaults in app/rag/prompts.py):

    ./venv/bin/python scripts/seed_langfuse_prompts.py --force

Once seeded, edit the prompts in the Langfuse UI; the running app picks up
changes within the prompt cache TTL (see observability._PROMPT_CACHE_TTL_SECONDS)
and falls back to the bundled defaults whenever Langfuse is unavailable.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag import observability as obs  # noqa: E402


def main() -> None:
    force = "--force" in sys.argv[1:]

    if not obs.langfuse_enabled():
        raise SystemExit(
            "Langfuse is disabled or not configured. Set LANGFUSE_ENABLED=true and "
            "the LANGFUSE_* keys in .env before seeding."
        )

    obs.init_langfuse()
    try:
        summary = obs.seed_prompts(force=force)
    finally:
        obs.flush_langfuse()

    print(
        f"Seeded Langfuse prompts. created={summary['created']} "
        f"skipped={summary['skipped']}"
        + ("" if not force else "  (--force: all created as new versions)")
    )


if __name__ == "__main__":
    main()
