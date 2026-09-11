# App

_Auto-generated feature documentation for `app/`._

## Endpoints

### GET /

The "read_root" App endpoint retrieves the root-level data or configuration.

### POST /chat

The "chat" app endpoint facilitates real-time text-based communication between users.

### GET /config

The "effective_config" app endpoint retrieves and returns the current configuration settings that are in effect for an application or system.

### POST /feedback

The "submit_feedback" app endpoint allows users to send feedback for improvement or reporting issues.

### GET /health

The "health_check" app endpoint is used to verify the operational status of the application or service it belongs to.

### POST /health/neo4j

The `neo4j_keepalive` app endpoint is designed to maintain and verify the active connection between a client and a Neo4j database server by sending periodic keep-alive signals.

### POST /ingest

The `trigger_ingest` app endpoint is designed to initiate data ingestion processes.

## Functions

### `InMemoryRateLimiter.is_rate_limited`

The `is_rate_limited` function checks if an action should be rate-limited based on in-memory counters and timestamps.

### `RetrievedChunk.snippet`

RetrievedChunk.snippet is a function that extracts and returns a specific segment or "chunk" of text from a larger body of text, often used for previewing or displaying parts of documents or content.

### `Settings.frontend_origins`

This App function manages and configures allowed frontend origins for security settings.

### `Settings.validate_keepalive_token`

The Settings.validate_keepalive_token function checks if the keep-alive token is valid and updates its expiration time accordingly.

### `SimpleLRUCache.get`

The `SimpleLRUCache.get` function retrieves an item from the cache using its key, updating the cache's order to maintain the most recently used items at the front.

### `SimpleLRUCache.set`

The `SimpleLRUCache.set` function adds or updates an entry in the cache using the specified key and value, adhering to the Least Recently Used (LRU) eviction policy.

### `chunk_text`

The chunk_text function splits text into smaller segments or chunks based on specified parameters such as character count or number of words.

### `client_ip_from_request`

The `client_ip_from_request` function extracts and returns the IP address of the client making the request.

### `close_driver`

The `close_driver` function terminates or stops a driver process.

### `embed_text`

The "embed_text" app function converts text into numerical vectors that represent its meaning for tasks like search and recommendation.

### `end_span`

The "end_span" function marks the conclusion of a span or segment in a process or data flow.

### `flush_langfuse`

The `flush_langfuse` app function is designed to clear or reset the Langfuse database, ensuring that all data is removed and starting fresh.

### `generate_answer`

The "generate_answer" app function creates responses to user queries or prompts based on its programmed algorithms and data.

### `generate_answer_stream`

The `generate_answer_stream` function generates a stream of answers to a given question or prompt in real-time.

### `get_client`

The `get_client` function retrieves a client object for making API requests.

### `get_driver`

The `get_driver` function retrieves a database driver based on specified connection details.

### `get_prompt`

The `get_prompt` function retrieves and returns a prompt based on specified criteria or parameters.

### `get_settings`

The `get_settings` function retrieves user preferences or application configuration settings.

### `ingest_content`

The ingest_content app function processes and imports new data into a system for further analysis or storage.

### `init_langfuse`

The `init_langfuse` function initializes the Langfuse library for language model evaluation and monitoring.

### `is_portfolio_question`

The `is_portfolio_question` function checks if a given question is related to a portfolio.

### `langfuse_enabled`

The `langfuse_enabled` function checks if language fusion is enabled in the system.

### `lifespan`

The Lifespan app tracks and monitors an individual's health metrics to predict and manage their longevity.

### `llm_metadata`

The llm_metadata app function retrieves and displays metadata related to language models.

### `mask_pii`

The `mask_pii` app function masks personally identifiable information (PII) in data to protect user privacy.

### `score_feedback`

The `score_feedback` app function evaluates and assigns scores to user feedback based on predefined criteria or algorithms.

### `search_chunks`

The "search_chunks" app function searches for specific data within pre-defined chunks of information.

### `seed_prompts`

The seed_prompts app generates and curates initial prompts for creative writing or content creation tasks.

### `start_span`

The `start_span` function initializes and starts a new tracing span in an application's execution flow.

### `start_trace`

The "start_trace" function initiates a performance tracing session to monitor and analyze application behavior.

### `update_trace`

The "update_trace" app function updates and tracks user activity logs in real-time.

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

### search_chunks()

```mermaid
flowchart TD
    start([search_chunks])
    n0_get_driver[get_driver]
    start --> n0_get_driver
    n0_get_driver --> done([return])
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
