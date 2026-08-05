"""Offline evaluation harness for the portfolio RAG pipeline.

Runs the curated cases in dataset.json against the real pipeline components
(guardrail -> embed -> retrieval, and optionally answer generation) and reports:

  * guardrail accuracy  - in-scope questions accepted, out-of-scope rejected
  * retrieval recall     - every expected source file is retrieved
  * precision@1          - the top-ranked chunk comes from an expected source
  * MRR                  - mean reciprocal rank of the first expected source
  * answer grounding     - (with --answer) the answer mentions an expected fact

Exits non-zero when guardrail accuracy or retrieval recall fall below threshold,
so it can gate changes to chunking, thresholds, prompts, or the embedding model.

Requires the same env as the app (GEMINI_API_KEY, NEO4J_*). Run with:

    ./venv/bin/python evals/run_eval.py            # guardrail + retrieval
    ./venv/bin/python evals/run_eval.py --answer   # also score generated answers
    ./venv/bin/python evals/run_eval.py --sweep    # tune RAG_MIN_SCORE from data
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag.guardrails import is_portfolio_question  # noqa: E402
from app.rag.llm import embed_text, generate_answer  # noqa: E402
from app.rag.neo4j_client import close_driver  # noqa: E402
from app.rag.retrieval import search_chunks  # noqa: E402
from app.routes.chat import _build_messages  # noqa: E402

DATASET = Path(__file__).resolve().parent / "dataset.json"

# Gating thresholds. Retrieval-quality regressions below these fail the run.
GUARDRAIL_THRESHOLD = 0.90
RECALL_THRESHOLD = 0.85

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _mark(ok: bool | None) -> str:
    if ok is None:
        return f"{DIM} -- {RESET}"
    return f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"


async def _eval_case(case: dict, *, check_answer: bool) -> dict:
    question = case["question"]
    in_scope = case["scope"] == "in"
    expected = case.get("expected_sources", [])

    result: dict = {
        "id": case["id"],
        "scope": case["scope"],
        "guardrail_ok": None,
        "recall_ok": None,
        "p_at_1_ok": None,
        "reciprocal_rank": 0.0,
        "answer_ok": None,
        "missing_sources": [],
    }

    # 1. Guardrail: in-scope must be accepted, out-of-scope rejected.
    accepted = await is_portfolio_question(question)
    result["guardrail_ok"] = accepted == in_scope

    # Out-of-scope questions stop at the guardrail in the real pipeline.
    if not in_scope:
        return result

    # 2. Retrieval (skipped for meta questions with no expected source).
    embedding = await embed_text(question)
    chunks = await search_chunks(embedding)
    retrieved = [chunk.source for chunk in chunks]

    if expected:
        missing = [src for src in expected if src not in retrieved]
        result["missing_sources"] = missing
        result["recall_ok"] = not missing
        result["p_at_1_ok"] = bool(retrieved) and retrieved[0] in expected
        for rank, src in enumerate(retrieved, start=1):
            if src in expected:
                result["reciprocal_rank"] = 1.0 / rank
                break

    # 3. Answer grounding (optional): reuse the real prompt + context builder.
    if check_answer:
        keywords = case.get("expected_keywords", [])
        messages = _build_messages(question, chunks, [])
        answer = await generate_answer(messages)
        lowered = answer.lower()
        result["answer_ok"] = (
            any(kw.lower() in lowered for kw in keywords) if keywords else None
        )

    return result


async def sweep() -> None:
    """Sweep RAG_MIN_SCORE over a range and report recall / precision@1 at each,
    so the threshold is chosen from data instead of guessed. Retrieves each case
    once unfiltered, then applies candidate thresholds offline."""
    from app.config import settings

    thresholds = [round(0.50 + 0.05 * i, 2) for i in range(8)]  # 0.50 .. 0.85
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = [c for c in data["cases"]
             if c["scope"] == "in" and c.get("expected_sources")]

    print(f"Sweeping RAG_MIN_SCORE over {thresholds}\n"
          f"on {len(cases)} retrieval cases (top_k={settings.rag_top_k}, "
          f"current min_score={settings.rag_min_score})...\n")

    # Collect candidate (source, score) per case once, unfiltered by min_score.
    original = settings.rag_min_score
    settings.rag_min_score = 0.0
    per_case: list[tuple[list[str], list[tuple[str, float]]]] = []
    try:
        for case in cases:
            embedding = await embed_text(case["question"])
            chunks = await search_chunks(embedding)
            per_case.append(
                (case["expected_sources"], [(c.source, c.score) for c in chunks])
            )
    finally:
        settings.rag_min_score = original
        await close_driver()

    header = f"{'min_score':11}{'recall':9}{'p@1':9}{'avg_chunks':12}{'empty_cases':12}"
    print(header + "\n" + "-" * len(header))
    n = len(per_case)
    for t in thresholds:
        recalls = p1s = empties = 0
        counts = 0
        for expected, cand in per_case:
            passed = [src for src, score in cand if score >= t]
            counts += len(passed)
            empties += 0 if passed else 1
            recalls += all(e in passed for e in expected)
            p1s += bool(passed) and passed[0] in expected
        marker = f"  {YELLOW}<- current{RESET}" if abs(t - original) < 1e-9 else ""
        print(f"{t:<11.2f}{recalls / n:>7.0%}  {p1s / n:>7.0%}  "
              f"{counts / n:>10.1f}  {empties:>10}{marker}")

    # Highest threshold that still keeps every expected source (per source, the
    # best-scoring chunk of that source is what must survive the cut).
    per_source_best = []
    for expected, cand in per_case:
        for e in expected:
            scores = [score for src, score in cand if src == e]
            per_source_best.append(max(scores) if scores else 0.0)
    safe_t = min(per_source_best) if per_source_best else 0.0

    print("\n=== Recommendation ===")
    print(f"Max min_score keeping 100% recall: {safe_t:.3f}")
    if original <= safe_t:
        print(f"{GREEN}Current {original} is SAFE{RESET} "
              f"(headroom {safe_t - original:.3f} before a relevant chunk is dropped).")
    else:
        print(f"{RED}Current {original} is TOO HIGH{RESET} — it drops relevant "
              f"chunks; lower it to <= {safe_t:.3f}.")
    print("Prefer the highest min_score that holds recall at 100% with few empty "
          "cases: that maximizes precision without missing answers.")


async def main() -> None:
    if "--sweep" in sys.argv[1:]:
        await sweep()
        return

    check_answer = "--answer" in sys.argv[1:]

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = data["cases"]

    print(f"Running {len(cases)} eval cases"
          f"{' (with answer grounding)' if check_answer else ''}...\n")

    try:
        results = [await _eval_case(c, check_answer=check_answer) for c in cases]
    finally:
        await close_driver()

    header = f"{'id':28} {'scope':6} {'guard':6} {'recall':7} {'p@1':5} {'rr':5}"
    if check_answer:
        header += f" {'answer':6}"
    print(header)
    print("-" * len(header))
    for r in results:
        row = (
            f"{r['id']:28} {r['scope']:6} "
            f"{_mark(r['guardrail_ok']):>14} "
            f"{_mark(r['recall_ok']):>16} "
            f"{_mark(r['p_at_1_ok']):>14} "
            f"{r['reciprocal_rank']:.2f}"
        )
        if check_answer:
            row += f"  {_mark(r['answer_ok']):>14}"
        print(row)
        if r["missing_sources"]:
            print(f"{'':28} {YELLOW}missing: {r['missing_sources']}{RESET}")

    # Aggregate metrics.
    guard = [r["guardrail_ok"] for r in results if r["guardrail_ok"] is not None]
    recall = [r["recall_ok"] for r in results if r["recall_ok"] is not None]
    p1 = [r["p_at_1_ok"] for r in results if r["p_at_1_ok"] is not None]
    rr = [r["reciprocal_rank"] for r in results if r["recall_ok"] is not None]
    ans = [r["answer_ok"] for r in results if r["answer_ok"] is not None]

    guard_acc = sum(guard) / len(guard) if guard else 1.0
    recall_rate = sum(recall) / len(recall) if recall else 1.0
    p1_rate = sum(p1) / len(p1) if p1 else 1.0
    mrr = sum(rr) / len(rr) if rr else 1.0

    print("\n=== Summary ===")
    print(f"Guardrail accuracy : {guard_acc:.0%}  ({sum(guard)}/{len(guard)})  "
          f"[threshold {GUARDRAIL_THRESHOLD:.0%}]")
    print(f"Retrieval recall   : {recall_rate:.0%}  ({sum(recall)}/{len(recall)})  "
          f"[threshold {RECALL_THRESHOLD:.0%}]")
    print(f"Precision@1        : {p1_rate:.0%}  ({sum(p1)}/{len(p1)})")
    print(f"MRR                : {mrr:.2f}")
    if ans:
        print(f"Answer grounding   : {sum(ans) / len(ans):.0%}  ({sum(ans)}/{len(ans)})")

    passed = guard_acc >= GUARDRAIL_THRESHOLD and recall_rate >= RECALL_THRESHOLD
    print(f"\n{GREEN}OVERALL: PASS{RESET}" if passed else f"\n{RED}OVERALL: FAIL{RESET}")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
