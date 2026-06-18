from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
CONTENT_DIR = BACKEND_DIR / "content"
INDEX_NAME = "portfolio_chunk_embedding"
CHUNK_LABEL = "DocumentChunk"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.chdir(BACKEND_DIR)

from app.config import settings  # noqa: E402
from app.rag.chunking import chunk_text  # noqa: E402
from app.rag.llm import embed_text  # noqa: E402
from app.rag.neo4j_client import get_driver  # noqa: E402


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
        joined = ", ".join(missing)
        raise SystemExit(f"Missing required environment values: {joined}")


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
            SourceDocument(
                path=path,
                section=path.stem,
                title=title,
                text=text,
            )
        )

    if not documents:
        raise SystemExit(f"No markdown content files found in {CONTENT_DIR}")

    return documents


def _extract_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _chunk_id(source: str, chunk_index: int, content: str) -> str:
    digest = hashlib.sha256(f"{source}:{chunk_index}:{content}".encode("utf-8")).hexdigest()
    return digest[:24]


def _embed_documents(documents: list[SourceDocument]) -> list[EmbeddedChunk]:
    embedded: list[EmbeddedChunk] = []

    for document in documents:
        chunks = chunk_text(document.text)
        print(f"Chunking {document.path.name}: {len(chunks)} chunk(s)")

        for chunk_index, content in enumerate(chunks):
            print(f"Embedding {document.path.name} chunk {chunk_index + 1}/{len(chunks)}")
            embedded.append(
                EmbeddedChunk(
                    id=_chunk_id(document.path.name, chunk_index, content),
                    title=document.title,
                    source=document.path.name,
                    section=document.section,
                    content=content,
                    chunk_index=chunk_index,
                    embedding=embed_text(content),
                )
            )

    if not embedded:
        raise SystemExit("No chunks were generated for ingestion")

    return embedded


def _create_vector_index(dimension: int) -> None:
    cypher = f"""
    CREATE VECTOR INDEX {INDEX_NAME} IF NOT EXISTS
    FOR (c:{CHUNK_LABEL})
    ON (c.embedding)
    OPTIONS {{
      indexConfig: {{
        `vector.dimensions`: {dimension},
        `vector.similarity_function`: 'cosine'
      }}
    }}
    """

    with get_driver() as driver:
        with driver.session() as session:
            session.run(f"DROP INDEX {INDEX_NAME} IF EXISTS")
            session.run(cypher)
            session.run("CALL db.awaitIndexes(300)")


def _write_chunks(chunks: list[EmbeddedChunk]) -> None:
    rows = [
        {
            "id": chunk.id,
            "title": chunk.title,
            "source": chunk.source,
            "section": chunk.section,
            "content": chunk.content,
            "chunk_index": chunk.chunk_index,
            "embedding": chunk.embedding,
        }
        for chunk in chunks
    ]

    cypher = f"""
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
      c.ingested_at = datetime()
    """

    with get_driver() as driver:
        with driver.session() as session:
            session.run(f"MATCH (c:{CHUNK_LABEL}) DETACH DELETE c")
            session.run(cypher, rows=rows)


def main() -> None:
    _require_env()
    documents = _read_documents()
    chunks = _embed_documents(documents)
    dimension = len(chunks[0].embedding)

    if dimension <= 0:
        raise SystemExit("Embedding model returned an empty vector")

    print(f"Creating Neo4j vector index '{INDEX_NAME}' with dimension {dimension}")
    _create_vector_index(dimension)

    print(f"Writing {len(chunks)} chunk(s) to Neo4j")
    _write_chunks(chunks)

    print("Ingestion complete")


if __name__ == "__main__":
    main()
