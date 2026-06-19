from __future__ import annotations

import asyncio
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
from app.rag.neo4j_client import close_driver, get_driver  # noqa: E402


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


async def main() -> None:
    _require_env()
    documents = _read_documents()

    # Calculate content hashes for local documents
    local_hashes = {}
    for doc in documents:
        local_hashes[doc.path.name] = hashlib.sha256(doc.text.encode("utf-8")).hexdigest()

    driver = get_driver()

    # 1. Fetch existing files and hashes from the database
    print("Fetching existing file hashes from Neo4j...")
    try:
        res = await driver.execute_query(
            f"MATCH (c:{CHUNK_LABEL}) RETURN DISTINCT c.source AS source, c.file_hash AS file_hash"
        )
        db_files = {r["source"]: r["file_hash"] for r in res.records if r["source"]}
    except Exception as e:
        print(f"Notice: Failed to fetch hashes (database might be empty or index doesn't exist yet): {e}")
        db_files = {}

    # 2. Determine changes: new, modified, or deleted files
    local_sources = set(local_hashes.keys())
    db_sources = set(db_files.keys())

    deleted_sources = db_sources - local_sources
    new_sources = local_sources - db_sources
    modified_sources = {
        source for source in (local_sources & db_sources)
        if local_hashes[source] != db_files[source]
    }

    to_embed = new_sources | modified_sources
    to_delete = deleted_sources | modified_sources

    if not to_embed and not to_delete:
        print("No changes detected. Database is up to date!")
        await close_driver()
        return

    # 3. Handle deletions
    if to_delete:
        print(f"Deleting existing database chunks for: {', '.join(to_delete)}")
        await driver.execute_query(
            f"MATCH (c:{CHUNK_LABEL}) WHERE c.source IN $sources DETACH DELETE c",
            sources=list(to_delete),
        )

    # 4. Handle insertions and modifications
    if to_embed:
        print(f"Embedding and writing updates for: {', '.join(to_embed)}")
        docs_to_embed = [doc for doc in documents if doc.path.name in to_embed]

        chunks: list[EmbeddedChunk] = []
        for doc in docs_to_embed:
            doc_chunks = chunk_text(doc.text)
            print(f"Chunking {doc.path.name}: {len(doc_chunks)} chunk(s)")

            for chunk_index, content in enumerate(doc_chunks):
                print(f"Embedding {doc.path.name} chunk {chunk_index + 1}/{len(doc_chunks)}")
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
                raise SystemExit("Embedding model returned an empty vector")

            # Ensure vector index exists
            print(f"Ensuring Neo4j vector index '{INDEX_NAME}' with dimension {dimension}")
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

            # Write the chunks to Neo4j
            print(f"Writing {len(chunks)} chunk(s) to Neo4j...")
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

    print("Ingestion complete successfully.")
    await close_driver()


if __name__ == "__main__":
    asyncio.run(main())
