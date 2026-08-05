---
title: Siva Portfolio RAG API
emoji: 🤖
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Siva Portfolio RAG API

FastAPI backend powering the RAG chatbot on
[sivakumar.dev](https://www.sivakumar.dev). It answers questions about Siva Kumar's
experience, projects, and skills by retrieving from a Neo4j vector index and
generating with Gemini (via LiteLLM), streamed to the client. Deployed as a
Hugging Face Space at `https://psk95-portfolio-rag-api.hf.space`.

## Stack
- **FastAPI** — streaming NDJSON `/chat` API
- **LiteLLM → Gemini** — chat + embeddings (provider-agnostic; no LangChain/LangGraph)
- **Neo4j Aura** — vector index (`DocumentChunk` / `portfolio_chunk_embedding`)
- **Langfuse** — tracing, managed prompts, dataset evals, PII masking

## Pipeline (`/chat`)
Rate-limit → condense (if history) → cache → LLM scope guardrail → embed →
Neo4j vector search (filtered by `RAG_MIN_SCORE`) → stream answer. Knowledge base
is `content/*.md`, synced to Neo4j on startup (incremental, hash-based).

## API
| Method & path | Description |
|---------------|-------------|
| `GET /health` | Liveness check |
| `POST /chat` | Streaming RAG chat (NDJSON); rate-limited 20/min per IP |
| `POST /feedback` | Record a thumbs up/down Langfuse score for a trace |
| `POST /health/neo4j` | Token-guarded Neo4j keepalive |
| `POST /admin/ingest` | Token-guarded content re-ingest (`?force=true` re-embeds all) |
| `GET /admin/config` | Token-guarded; returns non-sensitive effective config |

## Quickstart (local)
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in secrets
uvicorn app.main:app --reload --port 8000
curl http://127.0.0.1:8000/health
```

## Configuration
Secrets and environment-specific values (`GEMINI_API_KEY`, `NEO4J_*`,
`LANGFUSE_*`, `KEEPALIVE_TOKEN`, `FRONTEND_ORIGIN`) come from the environment;
tuning knobs (`RAG_TOP_K`, `RAG_MIN_SCORE`, model ids) have code defaults in
`app/config.py`. See `.env.example`.

> **Note:** on Hugging Face Spaces the platform proxy injects permissive CORS
> that overrides `FRONTEND_ORIGIN`, so origin lockdown isn't enforced in prod —
> `/chat` rate limiting is the abuse control. Env-var changes need a Factory
> reboot to take effect.

## Evaluation
```bash
python evals/run_eval.py            # guardrail + retrieval gate (exit code)
python evals/run_eval.py --sweep    # tune RAG_MIN_SCORE from data
python evals/run_eval_http.py       # black-box eval against the deployed Space
```

See **[HANDOFF.md](HANDOFF.md)** for architecture, deployment, and operations detail.
