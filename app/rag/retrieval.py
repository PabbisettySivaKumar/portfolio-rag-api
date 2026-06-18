from dataclasses import dataclass

from app.config import settings
from app.rag.neo4j_client import get_driver


@dataclass(frozen=True)
class RetrievedChunk:
    title: str
    content: str
    source: str
    section: str
    score: float

    @property
    def snippet(self) -> str:
        normalized = " ".join(self.content.split())
        if len(normalized) <= 260:
            return normalized
        return f"{normalized[:257].rstrip()}..."


def search_chunks(query_embedding: list[float]) -> list[RetrievedChunk]:
    cypher = """
    CALL db.index.vector.queryNodes('portfolio_chunk_embedding', $top_k, $embedding)
    YIELD node, score
    RETURN
      node.title AS title,
      node.content AS content,
      node.source AS source,
      node.section AS section,
      score
    ORDER BY score DESC
    """

    with get_driver() as driver:
        records = driver.execute_query(
            cypher,
            top_k=settings.rag_top_k,
            embedding=query_embedding,
        ).records

    chunks = [
        RetrievedChunk(
            title=record["title"] or "Portfolio source",
            content=record["content"] or "",
            source=record["source"] or "",
            section=record["section"] or "",
            score=float(record["score"] or 0),
        )
        for record in records
    ]

    return [chunk for chunk in chunks if chunk.score >= settings.rag_min_score]
