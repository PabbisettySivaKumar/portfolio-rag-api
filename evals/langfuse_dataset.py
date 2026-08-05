"""Mirror the local eval set (dataset.json) into Langfuse Datasets.

Two modes:

  --seed  Create/update a Langfuse dataset named "portfolio-rag-eval" with one
          item per case (input = question, expected_output = sources/keywords/
          scope). Idempotent: items are upserted by their case id.

  --run   Execute the real pipeline (guardrail -> embed -> retrieval, plus
          answer generation with --answer) over every dataset item, create one
          trace per item linked to the dataset as a run, and attach numeric
          scores (guardrail, retrieval_recall, precision_at_1, reciprocal_rank,
          answer_grounding). Results appear under the dataset's Runs tab in the
          Langfuse UI, each row linking to its trace.

Requires Langfuse enabled + configured (LANGFUSE_*) and, for --run, the app env
(GEMINI_API_KEY, NEO4J_*). Examples:

    ./venv/bin/python evals/langfuse_dataset.py --seed
    ./venv/bin/python evals/langfuse_dataset.py --run
    ./venv/bin/python evals/langfuse_dataset.py --run --answer
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag import observability as obs  # noqa: E402
from app.rag.guardrails import is_portfolio_question  # noqa: E402
from app.rag.llm import embed_text, generate_answer  # noqa: E402
from app.rag.neo4j_client import close_driver  # noqa: E402
from app.rag.retrieval import search_chunks  # noqa: E402
from app.routes.chat import _build_messages  # noqa: E402

DATASET_FILE = Path(__file__).resolve().parent / "dataset.json"
DATASET_NAME = "portfolio-rag-eval"


def _client():
    """Init Langfuse and return the raw SDK client, or exit if disabled."""
    if not obs.langfuse_enabled():
        raise SystemExit(
            "Langfuse is disabled or not configured. Set LANGFUSE_ENABLED=true "
            "and the LANGFUSE_* keys in .env first."
        )
    obs.init_langfuse()
    client = obs.get_client()
    if client is None:
        raise SystemExit("Langfuse client failed to initialize; check credentials.")
    return client


def seed() -> None:
    client = _client()
    data = json.loads(DATASET_FILE.read_text(encoding="utf-8"))
    cases = data["cases"]

    client.create_dataset(
        name=DATASET_NAME,
        description="Portfolio RAG eval: guardrail + retrieval + answer grounding.",
        metadata={"source": "evals/dataset.json", "num_cases": len(cases)},
    )
    for case in cases:
        client.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=case["id"],  # upsert so re-seeding does not duplicate
            input={"question": case["question"]},
            expected_output={
                "scope": case["scope"],
                "sources": case.get("expected_sources", []),
                "keywords": case.get("expected_keywords", []),
            },
            metadata={"scope": case["scope"]},
        )
    client.flush()
    print(f"Seeded dataset '{DATASET_NAME}' with {len(cases)} items.")


async def run(check_answer: bool) -> None:
    client = _client()
    dataset = client.get_dataset(DATASET_NAME)
    run_name = "eval-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    print(f"Running dataset '{DATASET_NAME}' as run '{run_name}' "
          f"({len(dataset.items)} items)...\n")

    try:
        for item in dataset.items:
            question = item.input["question"] if isinstance(item.input, dict) else item.input
            expected = item.expected_output or {}
            in_scope = expected.get("scope") == "in"
            exp_sources = expected.get("sources", [])
            keywords = expected.get("keywords", [])

            trace = client.trace(name="dataset-eval", input=question, tags=["eval"])
            output: dict = {}
            scores: dict = {}

            # 1. Guardrail
            accepted = await is_portfolio_question(question)
            output["accepted"] = accepted
            scores["guardrail"] = 1.0 if accepted == in_scope else 0.0

            # 2. Retrieval + 3. answer (only for in-scope with expected sources)
            if in_scope:
                embedding = await embed_text(question)
                chunks = await search_chunks(embedding)
                retrieved = [c.source for c in chunks]
                output["retrieved_sources"] = retrieved

                if exp_sources:
                    hit = [s for s in exp_sources if s in retrieved]
                    scores["retrieval_recall"] = len(hit) / len(exp_sources)
                    scores["precision_at_1"] = (
                        1.0 if retrieved and retrieved[0] in exp_sources else 0.0
                    )
                    rr = 0.0
                    for rank, src in enumerate(retrieved, start=1):
                        if src in exp_sources:
                            rr = 1.0 / rank
                            break
                    scores["reciprocal_rank"] = rr

                if check_answer:
                    answer = await generate_answer(_build_messages(question, chunks, []))
                    output["answer"] = answer
                    if keywords:
                        lowered = answer.lower()
                        scores["answer_grounding"] = (
                            1.0 if any(k.lower() in lowered for k in keywords) else 0.0
                        )

            trace.update(output=output)
            item.link(trace, run_name)
            for name, value in scores.items():
                trace.score(name=name, value=value)

            passed = all(v == 1.0 for k, v in scores.items()
                         if k in ("guardrail", "precision_at_1"))
            mark = "PASS" if passed else "----"
            print(f"  [{mark}] {item.id:28} {scores}")
    finally:
        client.flush()
        await close_driver()

    print(f"\nDone. View run '{run_name}' under dataset '{DATASET_NAME}' in Langfuse.")


def main() -> None:
    args = sys.argv[1:]
    if "--seed" in args:
        seed()
    elif "--run" in args:
        asyncio.run(run(check_answer="--answer" in args))
    else:
        raise SystemExit("Usage: langfuse_dataset.py (--seed | --run [--answer])")


if __name__ == "__main__":
    main()
