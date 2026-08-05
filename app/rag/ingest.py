from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.rag.chunking import chunk_text
from app.rag.llm import embed_text
from app.rag.neo4j_client import get_driver

logger = logging.getLogger(__name__)

# app/rag/ingest.py -> parents[2] is the backend root (portfolio-rag-api / /app in the image)
BACKEND_DIR = Path(__file__).resolve().parents[2]
CONTENT_DIR = BACKEND_DIR / "content"
INDEX_NAME = "portfolio_chunk_embedding"
CHUNK_LABEL = "DocumentChunk"


@dataclass(frozen=True)
class SourceDocument:
    path: Path
    section: str
    title: str
    text: str


@dataclass(frozen=True)
class EmbeddedChunk:
    id: str
    title: str
    source: str
    section: str
    content: str
    chunk_index: int
    embedding: list[float]


class MissingIngestEnv(RuntimeError):
    """Raised when required env values for ingestion are absent."""


def _require_env() -> None:
    missing = []
    if not settings.gemini_api_key:
        missing.append("GEMINI_API_KEY")
    if not settings.neo4j_uri:
        missing.append("NEO4J_URI")
    if not settings.neo4j_username:
        missing.append("NEO4J_USERNAME")
    if not settings.neo4j_password:
        missing.append("NEO4J_PASSWORD")

    if missing:
        raise MissingIngestEnv(f"Missing required environment values: {', '.join(missing)}")


def _extract_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _read_documents() -> list[SourceDocument]:
    documents: list[SourceDocument] = []

    for path in sorted(CONTENT_DIR.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue

        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue

        title = _extract_title(text) or path.stem.replace("_", " ").title()
        documents.append(
            SourceDocument(path=path, section=path.stem, title=title, text=text)
        )

    if not documents:
        raise MissingIngestEnv(f"No markdown content files found in {CONTENT_DIR}")

    return documents


def _chunk_id(source: str, chunk_index: int, content: str) -> str:
    digest = hashlib.sha256(f"{source}:{chunk_index}:{content}".encode("utf-8")).hexdigest()
    return digest[:24]


async def ingest_content(
    *, force: bool = False, log: logging.Logger | None = None
) -> dict:
    """Sync content/*.md into Neo4j. Incremental by default: only new/modified
    files are re-embedded and deleted files are removed. Uses the shared app
    driver and never closes it, so it is safe to call from within the running
    application.

    With ``force=True`` every file is re-chunked and re-embedded regardless of
    its hash (existing chunks are dropped first). Use this after changing the
    chunking logic or embedding model, when file hashes are unchanged but the
    stored vectors are stale.

    Returns a summary dict. Raises MissingIngestEnv on missing config.
    """
    out = log or logger

    _require_env()
    documents = _read_documents()

    local_hashes = {
        doc.path.name: hashlib.sha256(doc.text.encode("utf-8")).hexdigest()
        for doc in documents
    }

    driver = get_driver()

    # 1. Existing files + hashes already in the database
    try:
        res = await driver.execute_query(
            f"MATCH (c:{CHUNK_LABEL}) RETURN DISTINCT c.source AS source, c.file_hash AS file_hash"
        )
        db_files = {r["source"]: r["file_hash"] for r in res.records if r["source"]}
    except Exception as e:
        out.info("Could not fetch existing hashes (empty DB or missing index?): %s", e)
        db_files = {}

    # 2. Diff local vs database
    local_sources = set(local_hashes.keys())
    db_sources = set(db_files.keys())

    if force:
        # Re-embed every local file and drop everything currently stored
        # (including chunks for any file removed since the last run).
        out.info("Ingestion: force=True; re-embedding all content.")
        to_embed = set(local_sources)
        to_delete = set(db_sources)
    else:
        deleted_sources = db_sources - local_sources
        new_sources = local_sources - db_sources
        modified_sources = {
            source
            for source in (local_sources & db_sources)
            if local_hashes[source] != db_files[source]
        }

        to_embed = new_sources | modified_sources
        to_delete = deleted_sources | modified_sources

    if not to_embed and not to_delete:
        out.info("Ingestion: no content changes detected; database is up to date.")
        return {"changed": False, "embedded": [], "deleted": [], "chunks": 0}

    # 3. Deletions (removed files + the stale copies of modified files)
    if to_delete:
        out.info("Ingestion: deleting chunks for %s", ", ".join(sorted(to_delete)))
        await driver.execute_query(
            f"MATCH (c:{CHUNK_LABEL}) WHERE c.source IN $sources DETACH DELETE c",
            sources=list(to_delete),
        )

    # 4. Insertions + modifications
    written_chunks = 0
    if to_embed:
        out.info("Ingestion: embedding %s", ", ".join(sorted(to_embed)))
        docs_to_embed = [doc for doc in documents if doc.path.name in to_embed]

        chunks: list[EmbeddedChunk] = []
        for doc in docs_to_embed:
            doc_chunks = chunk_text(doc.text)
            for chunk_index, content in enumerate(doc_chunks):
                embedding = await embed_text(content)
                chunks.append(
                    EmbeddedChunk(
                        id=_chunk_id(doc.path.name, chunk_index, content),
                        title=doc.title,
                        source=doc.path.name,
                        section=doc.section,
                        content=content,
                        chunk_index=chunk_index,
                        embedding=embedding,
                    )
                )

        if chunks:
            dimension = len(chunks[0].embedding)
            if dimension <= 0:
                raise MissingIngestEnv("Embedding model returned an empty vector")

            cypher_index = f"""
            CREATE VECTOR INDEX {INDEX_NAME} IF NOT EXISTS
            FOR (c:{CHUNK_LABEL})
            ON (c.embedding)
            OPTIONS {{
              indexConfig: {{
                `vector.dimensions`: $dimension,
                `vector.similarity_function`: 'cosine'
              }}
            }}
            """
            await driver.execute_query(cypher_index, dimension=dimension)
            await driver.execute_query("CALL db.awaitIndexes(300)")

            rows = [
                {
                    "id": chunk.id,
                    "title": chunk.title,
                    "source": chunk.source,
                    "section": chunk.section,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "embedding": chunk.embedding,
                    "file_hash": local_hashes[chunk.source],
                }
                for chunk in chunks
            ]

            cypher_write = f"""
            UNWIND $rows AS row
            CREATE (c:{CHUNK_LABEL})
            SET
              c.id = row.id,
              c.title = row.title,
              c.source = row.source,
              c.section = row.section,
              c.content = row.content,
              c.chunk_index = row.chunk_index,
              c.embedding = row.embedding,
              c.file_hash = row.file_hash,
              c.ingested_at = datetime()
            """
            await driver.execute_query(cypher_write, rows=rows)
            written_chunks = len(chunks)

    out.info(
        "Ingestion complete: embedded=%s deleted=%s chunks=%s",
        sorted(to_embed),
        sorted(to_delete),
        written_chunks,
    )
    return {
        "changed": True,
        "embedded": sorted(to_embed),
        "deleted": sorted(to_delete),
        "chunks": written_chunks,
    }
