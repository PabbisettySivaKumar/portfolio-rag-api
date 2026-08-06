# portfolio-rag-api — Handoff

FastAPI backend powering the RAG chatbot on Siva Kumar's portfolio. Retrieves
from a Neo4j vector index and answers with Gemini (via LiteLLM), with Langfuse
observability. **No LangChain / LangGraph** — the pipeline is a custom async
flow.

## Architecture

```
Next.js frontend (sivakumar.dev)
      │  POST /chat  (ndjson stream)
      ▼
FastAPI (this repo, HF Space)
  rate-limit → condense → cache → guardrail → embed → Neo4j vector search → LLM stream
      │                                   │                    │
   LiteLLM ───────── Gemini          Neo4j Aura           Langfuse (traces, prompts, scores)
```

### `/chat` request flow (`app/routes/chat.py`)
1. **Rate limit** per client IP (20/min) — 429 before any LLM work.
2. **Condense** the question against history (only if history is present).
3. **Cache** lookup on the normalized condensed question (in-memory LRU, 1h TTL).
4. **Guardrail** — `is_portfolio_question`: keyword fast-path, else an LLM scope
   classifier (fails open). Off-topic → canned refusal.
5. **Embed** the condensed question (Gemini embeddings via LiteLLM).
6. **Retrieve** from Neo4j vector index, filtered by `RAG_MIN_SCORE`.
7. **Generate** the answer, streamed as ndjson token events. Result cached.

Everything is grouped into one Langfuse trace with child spans; the stream's
first event carries the `trace_id` so the client can attach `/feedback`.

## Repo layout
| Path | Purpose |
|------|---------|
| `app/main.py` | App wiring, CORS, lifespan (startup ingest + Langfuse init) |
| `app/config.py` | Env-driven settings + tuning defaults |
| `app/routes/chat.py` | `/chat` streaming endpoint + pipeline orchestration |
| `app/routes/feedback.py` | `/feedback` → Langfuse score |
| `app/routes/health.py` | `/health`, `/health/neo4j` (keepalive, token-guarded) |
| `app/routes/admin.py` | `/admin/ingest` (force re-embed), `/admin/config` (diagnostics) — token-guarded |
| `app/rag/llm.py` | LiteLLM chat/embeddings + streaming with fallback model |
| `app/rag/retrieval.py` | Neo4j vector search |
| `app/rag/chunking.py` | Structural (section-aware) markdown chunking |
| `app/rag/ingest.py` | Incremental content→Neo4j sync (hash-based; `force=` re-embeds all) |
| `app/rag/guardrails.py` | Scope guardrail (keyword + LLM classifier) |
| `app/rag/prompts.py` | Prompt defaults + Langfuse-managed prompt registry |
| `app/rag/observability.py` | Langfuse: traces, spans, scores, managed prompts, PII masking |
| `app/rag/cache.py` | In-memory LRU query cache |
| `app/rate_limit.py` | Per-IP limiter + `X-Forwarded-For`-aware client IP helper |
| `content/*.md` | The knowledge base (source of truth for answers) |
| `evals/` | Evaluation harness + dataset (see below) |
| `scripts/` | `ingest.py`, `seed_langfuse_prompts.py` |

## Configuration
`.env` locally (gitignored); **HF Space variables** in production. See
`.env.example`.

**Secrets / environment-specific → set in the Space:**
`GEMINI_API_KEY`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`,
`LANGFUSE_ENABLED`/`LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST`,
`KEEPALIVE_TOKEN` (≥32 chars; guards `/health/neo4j` and `/admin/*`),
`FRONTEND_ORIGIN` (single or comma-separated list — see CORS caveat below).

**Tuning knobs → code defaults in `app/config.py`** (single source of truth;
don't set in the Space): `LITELLM_*` models, `RAG_TOP_K`, `RAG_MIN_SCORE` (0.80,
tuned via the sweep — see below).

## Deployment (Hugging Face Space)
- Space: `psk95/portfolio-rag-api` (Docker SDK, port 7860),
  `https://psk95-portfolio-rag-api.hf.space`. **The git remote IS the Space** —
  `git push origin main` triggers a rebuild.
- **Env-var changes require a Factory reboot** (Settings → Factory reboot). A
  plain restart does not reliably re-inject changed variables.
- Confirm what the running container loaded: `GET /admin/config` with the
  keepalive bearer token (returns non-sensitive effective config).

### ⚠️ CORS does not work on HF Spaces
HF's edge proxy injects permissive CORS on responses, **overriding** the app's
`FRONTEND_ORIGIN` allowlist — any origin is allowed in production regardless of
config. This is a platform limitation, not a bug; the app config is correct and
would apply on a host that owns the edge. **Do not rely on CORS for access
control here.** Abuse is instead capped by per-IP rate limiting on `/chat`.

## Operations
- **Ingest content:** edits to `content/*.md` are re-embedded on next startup
  (incremental, hash-based). To force a full re-chunk/re-embed (e.g. after
  changing chunking or the embedding model):
  `POST /admin/ingest?force=true` with the keepalive token, or
  `./venv/bin/python scripts/ingest.py --force`.
- **Neo4j keepalive:** Aura reaps idle connections. The pool is hardened
  (`liveness_check_timeout`, `max_connection_lifetime`) and a cron pings
  `POST /health/neo4j` to stay warm. Transient resets self-heal via driver retry.
  * **Troubleshooting 401 Unauthorized**: If the GitHub Actions workflow fails with a `401` error, the secret `NEO4J_KEEPALIVE_TOKEN` configured in the frontend repository settings (`siva-portfolio`) does not match the `KEEPALIVE_TOKEN` environment variable set in the Hugging Face Space settings. Both must match exactly (e.g. `aGZt4lRbKeMyfA6dQ7forI1QfDVS81Aw6kdDtpVK6UnRtiLKtLxMASCTv1qKqipE` or your custom token). Keep in mind that the backend requires the header as `Bearer <token>` (which the GitHub Action prepends automatically).
- **Rate limit:** `/chat` is 20 req/min per IP (`app/rate_limit.py`), keyed on
  `X-Forwarded-For`. Per-container, resets on redeploy.
- **Langfuse prompts:** managed in the Langfuse UI (EU). Seed/update from code
  defaults with `./venv/bin/python scripts/seed_langfuse_prompts.py [--force]`.
  Runtime fetch falls back to bundled defaults if Langfuse is down.

## Evaluation (`evals/`)
Curated dataset (`dataset.json`) run three ways:
- `python evals/run_eval.py` — fast local guardrail + retrieval gate (exit code).
  `--answer` also scores answer grounding; `--sweep` tunes `RAG_MIN_SCORE`.
- `python evals/langfuse_dataset.py --seed|--run [--answer]` — in-process run
  recorded as a Langfuse dataset run.
- `python evals/run_eval_http.py` — black-box eval against the deployed Space,
  recorded as a `deployed-*` Langfuse dataset run.

Run `run_eval.py` before/after any change to chunking, thresholds, prompts, or
the embedding model.

## Local dev
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in secrets
uvicorn app.main:app --reload --port 8000
```
