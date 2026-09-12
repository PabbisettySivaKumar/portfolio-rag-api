# App

_Auto-generated feature documentation for `app/`._

## Endpoints

### GET /

Handles `GET /`.

### POST /chat

Facilitates the exchange of messages between users in a conversation.

### GET /config

Retrieves the currently active and resolved configuration for the application or a specific component.

### POST /feedback

Allows users to submit their feedback to the application.

### GET /health

It verifies the application's operational status and availability.

### POST /health/neo4j

This endpoint sends a keepalive signal to the Neo4j database to confirm its availability and maintain an active connection.

### POST /ingest

This endpoint initiates the data ingestion process.

## Functions

### `InMemoryRateLimiter.is_rate_limited`

This function determines if a request has surpassed its allowed frequency within a timeframe, based on in-memory records.

### `RetrievedChunk.snippet`

It returns a concise, representative text excerpt from a retrieved chunk of information.

### `Settings.frontend_origins`

It specifies the allowed web origins (domains/URLs) from which frontend applications can connect to the backend.

### `Settings.validate_keepalive_token`

This function verifies the validity of a token used to maintain an active user session.

### `SimpleLRUCache.get`

Retrieves an item from the cache, marking it as recently used if found.

### `SimpleLRUCache.set`

Adds or updates a key-value pair in the cache, making it the most recently used and potentially evicting the least recently used item if the cache is full.

### `chunk_text`

Breaks down a large text into smaller, more manageable segments or "chunks."

### `client_ip_from_request`

This function extracts the client's IP address from an incoming request.

### `close_driver`

This function shuts down a driver, ending its connection and releasing associated resources.

### `embed_text`

It converts text into a numerical representation that captures its semantic meaning.

### `end_span`

It marks the completion of a tracked operation or time segment.

### `flush_langfuse`

Forces all buffered Langfuse observability and tracing data to be sent to the Langfuse platform immediately.

### `generate_answer`

It creates a relevant response to a given query or input.

### `generate_answer_stream`

`generate_answer_stream()` — see source for details.

### `get_client`

`get_client()` — see source for details.

### `get_driver`

Retrieves a configured driver instance.

### `get_prompt`

`get_prompt()` — see source for details.

### `get_settings`

`get_settings()` — see source for details.

### `ingest_content`

`ingest_content()` — see source for details.

### `init_langfuse`

`init_langfuse()` — see source for details.

### `is_portfolio_question`

`is_portfolio_question()` — see source for details.

### `langfuse_enabled`

`langfuse_enabled()` — see source for details.

### `lifespan`

`lifespan()` — see source for details.

### `llm_metadata`

`llm_metadata()` — see source for details.

### `mask_pii`

`mask_pii()` — see source for details.

### `score_feedback`

`score_feedback()` — see source for details.

### `search_chunks`

`search_chunks()` — see source for details.

### `seed_prompts`

`seed_prompts()` — see source for details.

### `start_span`

`start_span()` — see source for details.

### `start_trace`

`start_trace()` — see source for details.

### `update_trace`

`update_trace()` — see source for details.

## Key internals

- `_build_messages` — called by the public surface.
- `_cache_key` — called by the public surface.
- `_chunk_id` — called by the public surface.
- `_condense_question` — called by the public surface.
- `_ensure_gemini_key` — called by the public surface.
- `_hard_split` — called by the public surface.
- `_keyword_accept` — called by the public surface.
- `_read_documents` — called by the public surface.
- `_redact` — called by the public surface.
- `_require_admin` — called by the public surface.
- `_require_env` — called by the public surface.
- `_sources_from_chunks` — called by the public surface.
- `_split_sections` — called by the public surface.
- `_startup_ingest` — called by the public surface.
- `_stream_completion` — called by the public surface.

## Diagrams

### GET /

```mermaid
sequenceDiagram
    participant Client
    participant read_root
    participant get
    Client->>read_root: GET /
    read_root->>get: get()
```

### POST /feedback

```mermaid
sequenceDiagram
    participant Client
    participant submit_feedback
    participant is_rate_limited
    participant score_feedback
    participant langfuse_enabled
    Client->>submit_feedback: POST /feedback
    submit_feedback->>is_rate_limited: is_rate_limited()
    is_rate_limited->>score_feedback: score_feedback()
    score_feedback->>langfuse_enabled: langfuse_enabled()
```

### GET /health

```mermaid
sequenceDiagram
    participant Client
    participant health_check
    participant get
    Client->>health_check: GET /health
    health_check->>get: get()
```

### POST /health/neo4j

```mermaid
sequenceDiagram
    participant Client
    participant neo4j_keepalive
    participant client_ip_from_request
    participant get
    participant is_rate_limited
    participant get_driver
    Client->>neo4j_keepalive: POST /health/neo4j
    neo4j_keepalive->>client_ip_from_request: client_ip_from_request()
    client_ip_from_request->>get: get()
    get->>is_rate_limited: is_rate_limited()
    is_rate_limited->>get_driver: get_driver()
```

### POST /chat

```mermaid
sequenceDiagram
    participant Client
    participant chat
    participant is_rate_limited
    participant client_ip_from_request
    participant get
    participant start_trace
    participant start_span
    participant end_span
    participant _cache_key
    participant update_trace
    participant _sources_from_chunks
    participant _build_messages
    participant _build_context
    participant get_prompt
    participant generate_answer_stream
    participant _ensure_gemini_key
    participant _stream_completion
    participant _condense_question
    participant generate_answer
    participant is_portfolio_question
    participant _keyword_accept
    participant embed_text
    participant search_chunks
    participant get_driver
    participant llm_metadata
    participant set
    Client->>chat: POST /chat
    chat->>is_rate_limited: is_rate_limited()
    is_rate_limited->>client_ip_from_request: client_ip_from_request()
    client_ip_from_request->>get: get()
    get->>start_trace: start_trace()
    start_trace->>start_span: start_span()
    start_span->>end_span: end_span()
    end_span->>_cache_key: _cache_key()
    _cache_key->>update_trace: update_trace()
    update_trace->>_sources_from_chunks: _sources_from_chunks()
    _sources_from_chunks->>_build_messages: _build_messages()
    _build_messages->>_build_context: _build_context()
    _build_context->>get_prompt: get_prompt()
    get_prompt->>generate_answer_stream: generate_answer_stream()
    generate_answer_stream->>_ensure_gemini_key: _ensure_gemini_key()
    _ensure_gemini_key->>_stream_completion: _stream_completion()
    _stream_completion->>_condense_question: _condense_question()
    _condense_question->>generate_answer: generate_answer()
    generate_answer->>is_portfolio_question: is_portfolio_question()
    is_portfolio_question->>_keyword_accept: _keyword_accept()
    _keyword_accept->>embed_text: embed_text()
    embed_text->>search_chunks: search_chunks()
    search_chunks->>get_driver: get_driver()
    get_driver->>llm_metadata: llm_metadata()
    llm_metadata->>set: set()
```

### GET /config

```mermaid
sequenceDiagram
    participant Client
    participant effective_config
    participant get
    participant _require_admin
    Client->>effective_config: GET /config
    effective_config->>get: get()
    get->>_require_admin: _require_admin()
```

### POST /ingest

```mermaid
sequenceDiagram
    participant Client
    participant trigger_ingest
    participant _require_admin
    participant ingest_content
    participant _require_env
    participant _read_documents
    participant _extract_title
    participant get_driver
    participant set
    participant chunk_text
    participant _split_sections
    participant _hard_split
    participant embed_text
    participant _ensure_gemini_key
    participant _chunk_id
    Client->>trigger_ingest: POST /ingest
    trigger_ingest->>_require_admin: _require_admin()
    _require_admin->>ingest_content: ingest_content()
    ingest_content->>_require_env: _require_env()
    _require_env->>_read_documents: _read_documents()
    _read_documents->>_extract_title: _extract_title()
    _extract_title->>get_driver: get_driver()
    get_driver->>set: set()
    set->>chunk_text: chunk_text()
    chunk_text->>_split_sections: _split_sections()
    _split_sections->>_hard_split: _hard_split()
    _hard_split->>embed_text: embed_text()
    embed_text->>_ensure_gemini_key: _ensure_gemini_key()
    _ensure_gemini_key->>_chunk_id: _chunk_id()
```

### client_ip_from_request()

```mermaid
flowchart TD
    start([client_ip_from_request])
    n0_get[get]
    start --> n0_get
    n0_get --> done([return])
```

### _read_documents()

```mermaid
flowchart TD
    start([_read_documents])
    n0__extract_title[_extract_title]
    start --> n0__extract_title
    n0__extract_title --> done([return])
```

### ingest_content()

```mermaid
flowchart TD
    start([ingest_content])
    n0__require_env[_require_env]
    start --> n0__require_env
    n1__read_documents[_read_documents]
    n0__require_env --> n1__read_documents
    n2_get_driver[get_driver]
    n1__read_documents --> n2_get_driver
    n3_set[set]
    n2_get_driver --> n3_set
    n4_chunk_text[chunk_text]
    n3_set --> n4_chunk_text
    n5_embed_text[embed_text]
    n4_chunk_text --> n5_embed_text
    n6__chunk_id[_chunk_id]
    n5_embed_text --> n6__chunk_id
    n6__chunk_id --> done([return])
```

### search_chunks()

```mermaid
flowchart TD
    start([search_chunks])
    n0_get_driver[get_driver]
    start --> n0_get_driver
    n0_get_driver --> done([return])
```

### is_portfolio_question()

```mermaid
flowchart TD
    start([is_portfolio_question])
    n0__keyword_accept[_keyword_accept]
    start --> n0__keyword_accept
    n1_generate_answer[generate_answer]
    n0__keyword_accept --> n1_generate_answer
    n2_get_prompt[get_prompt]
    n1_generate_answer --> n2_get_prompt
    n2_get_prompt --> done([return])
```

### generate_answer()

```mermaid
flowchart TD
    start([generate_answer])
    n0__ensure_gemini_key[_ensure_gemini_key]
    start --> n0__ensure_gemini_key
    n1_get[get]
    n0__ensure_gemini_key --> n1_get
    n1_get --> done([return])
```

### _stream_completion()

```mermaid
flowchart TD
    start([_stream_completion])
    n0_get[get]
    start --> n0_get
    n0_get --> done([return])
```

### generate_answer_stream()

```mermaid
flowchart TD
    start([generate_answer_stream])
    n0__ensure_gemini_key[_ensure_gemini_key]
    start --> n0__ensure_gemini_key
    n1__stream_completion[_stream_completion]
    n0__ensure_gemini_key --> n1__stream_completion
    n1__stream_completion --> done([return])
```

### chunk_text()

```mermaid
flowchart TD
    start([chunk_text])
    n0__split_sections[_split_sections]
    start --> n0__split_sections
    n1__hard_split[_hard_split]
    n0__split_sections --> n1__hard_split
    n1__hard_split --> done([return])
```

### mask_pii()

```mermaid
flowchart TD
    start([mask_pii])
    n0__redact[_redact]
    start --> n0__redact
    n1_mask_pii[mask_pii]
    n0__redact --> n1_mask_pii
    n1_mask_pii --> done([return])
```

### init_langfuse()

```mermaid
flowchart TD
    start([init_langfuse])
    n0_langfuse_enabled[langfuse_enabled]
    start --> n0_langfuse_enabled
    n0_langfuse_enabled --> done([return])
```

### get_prompt()

```mermaid
flowchart TD
    start([get_prompt])
    n0_get_prompt[get_prompt]
    start --> n0_get_prompt
    n0_get_prompt --> done([return])
```

### seed_prompts()

```mermaid
flowchart TD
    start([seed_prompts])
    n0_get_prompt[get_prompt]
    start --> n0_get_prompt
    n0_get_prompt --> done([return])
```

### _condense_question()

```mermaid
flowchart TD
    start([_condense_question])
    n0_get_prompt[get_prompt]
    start --> n0_get_prompt
    n1_generate_answer[generate_answer]
    n0_get_prompt --> n1_generate_answer
    n1_generate_answer --> done([return])
```
