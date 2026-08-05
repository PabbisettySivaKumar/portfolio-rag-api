"""Black-box eval of the DEPLOYED service over HTTP.

Unlike run_eval.py (which calls the pipeline in-process), this hits the live
/chat endpoint over the network and scores the actual streamed responses, so it
exercises the deployed code, config, and infrastructure end to end.

By default it also records the results as a Langfuse dataset run named
"deployed-<timestamp>" under the "portfolio-rag-eval" dataset, linking each prod
trace (the trace_id the /chat stream returns) and attaching scores, so local and
deployed runs sit side by side in the Langfuse UI. Pass --no-langfuse to skip.

    ./venv/bin/python evals/run_eval_http.py
    ./venv/bin/python evals/run_eval_http.py --url https://my-space.hf.space
    ./venv/bin/python evals/run_eval_http.py --no-langfuse
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.rag import observability as obs  # noqa: E402
from app.rag.guardrails import OUT_OF_SCOPE_RESPONSE  # noqa: E402
from app.routes.chat import NO_CONTEXT_RESPONSE  # noqa: E402

DATASET_FILE = Path(__file__).resolve().parent / "dataset.json"
CONTENT_DIR = BACKEND_DIR / "content"
DATASET_NAME = "portfolio-rag-eval"
DEFAULT_URL = "https://psk95-portfolio-rag-api.hf.space"

GUARDRAIL_THRESHOLD = 0.90
RECALL_THRESHOLD = 0.85
REFUSALS = {OUT_OF_SCOPE_RESPONSE.strip(), NO_CONTEXT_RESPONSE.strip()}

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _mark(ok: bool | None) -> str:
    if ok is None:
        return f"{DIM} -- {RESET}"
    return f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"


def _source_title_map() -> dict[str, str]:
    """Map content filename -> its markdown H1 title (as returned in /chat sources)."""
    mapping: dict[str, str] = {}
    for path in CONTENT_DIR.glob("*.md"):
        if path.name.lower() == "readme.md":
            continue
        title = path.stem.replace("_", " ").title()
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("# "):
                title = line.strip()[2:].strip()
                break
        mapping[path.name] = title
    return mapping


def _call_chat(base_url: str, question: str) -> dict:
    """POST /chat and parse the ndjson stream into trace_id / sources / answer."""
    payload = json.dumps({"message": question, "history": []}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    trace_id, sources, tokens = None, [], []
    with urllib.request.urlopen(req, timeout=90) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            evt = json.loads(line)
            if evt["type"] == "trace":
                trace_id = evt["trace_id"]
            elif evt["type"] == "sources":
                sources = evt["sources"]
            elif evt["type"] == "token":
                tokens.append(evt["content"])
            elif evt["type"] == "error":
                tokens.append(evt["content"])
    return {"trace_id": trace_id, "sources": sources, "answer": "".join(tokens)}


def main() -> None:
    args = sys.argv[1:]
    base_url = DEFAULT_URL
    if "--url" in args:
        base_url = args[args.index("--url") + 1]
    use_langfuse = "--no-langfuse" not in args

    title_map = _source_title_map()
    cases = json.loads(DATASET_FILE.read_text(encoding="utf-8"))["cases"]

    lf_client, lf_items, run_name = None, {}, None
    if use_langfuse and obs.langfuse_enabled():
        obs.init_langfuse()
        lf_client = obs.get_client()
        if lf_client is not None:
            lf_items = {it.id: it for it in lf_client.get_dataset(DATASET_NAME).items}
            run_name = "deployed-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    print(f"Evaluating deployed service at {base_url}"
          f"{f' (Langfuse run {run_name})' if run_name else ''}\n")

    header = f"{'id':28} {'scope':6} {'guard':6} {'recall':7} {'p@1':5} {'answer':6}"
    print(header + "\n" + "-" * len(header))

    results = []
    for case in cases:
        in_scope = case["scope"] == "in"
        expected = case.get("expected_sources", [])
        keywords = case.get("expected_keywords", [])
        exp_titles = {title_map.get(s, s) for s in expected}

        try:
            resp = _call_chat(base_url, case["question"])
        except Exception as e:
            print(f"{case['id']:28} {case['scope']:6} {RED}request failed: {e}{RESET}")
            results.append({"guard": False, "recall": None, "answer": None})
            continue

        answer = resp["answer"].strip()
        got_titles = [s["title"] for s in resp["sources"]]
        refused = answer in REFUSALS

        # Guardrail: out-of-scope must be refused; in-scope must not be refused.
        guard_ok = refused if not in_scope else not refused

        recall_ok = p1_ok = answer_ok = None
        scores = {"guardrail": 1.0 if guard_ok else 0.0}
        if in_scope and expected:
            hit = [t for t in exp_titles if t in got_titles]
            recall_ok = len(hit) == len(exp_titles)
            p1_ok = bool(got_titles) and got_titles[0] in exp_titles
            scores["retrieval_recall"] = len(hit) / len(exp_titles)
            scores["precision_at_1"] = 1.0 if p1_ok else 0.0
        if in_scope and keywords:
            low = answer.lower()
            answer_ok = any(k.lower() in low for k in keywords)
            scores["answer_grounding"] = 1.0 if answer_ok else 0.0

        results.append({"guard": guard_ok, "recall": recall_ok, "answer": answer_ok})
        print(f"{case['id']:28} {case['scope']:6} "
              f"{_mark(guard_ok):>14} {_mark(recall_ok):>16} "
              f"{_mark(p1_ok):>14} {_mark(answer_ok):>14}")

        # Link the prod trace into the dataset run and attach scores.
        if lf_client is not None and resp["trace_id"] and case["id"] in lf_items:
            try:
                trace_ref = lf_client.trace(id=resp["trace_id"])
                lf_items[case["id"]].link(trace_ref, run_name)
                for name, value in scores.items():
                    lf_client.score(trace_id=resp["trace_id"], name=name, value=value)
            except Exception as e:
                print(f"{'':28} {YELLOW}langfuse link failed: {e}{RESET}")

    if lf_client is not None:
        lf_client.flush()

    guard = [r["guard"] for r in results if r["guard"] is not None]
    recall = [r["recall"] for r in results if r["recall"] is not None]
    ans = [r["answer"] for r in results if r["answer"] is not None]
    guard_acc = sum(guard) / len(guard) if guard else 0.0
    recall_rate = sum(recall) / len(recall) if recall else 1.0

    print("\n=== Summary (deployed) ===")
    print(f"Guardrail accuracy : {guard_acc:.0%}  ({sum(guard)}/{len(guard)})  "
          f"[threshold {GUARDRAIL_THRESHOLD:.0%}]")
    print(f"Retrieval recall   : {recall_rate:.0%}  ({sum(recall)}/{len(recall)})  "
          f"[threshold {RECALL_THRESHOLD:.0%}]")
    if ans:
        print(f"Answer grounding   : {sum(ans) / len(ans):.0%}  ({sum(ans)}/{len(ans)})")
    if run_name:
        print(f"Langfuse run       : {run_name} (dataset {DATASET_NAME})")

    passed = guard_acc >= GUARDRAIL_THRESHOLD and recall_rate >= RECALL_THRESHOLD
    print(f"\n{GREEN}OVERALL: PASS{RESET}" if passed else f"\n{RED}OVERALL: FAIL{RESET}")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
