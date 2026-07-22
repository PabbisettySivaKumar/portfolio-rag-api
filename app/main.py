import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.rag.ingest import ingest_content
from app.rag.neo4j_client import close_driver
from app.rag.observability import flush_langfuse, init_langfuse
from app.routes import chat, feedback, health

logger = logging.getLogger(__name__)


async def _startup_ingest() -> None:
    """Sync content -> Neo4j in the background. Never crashes the app: any
    failure is logged and swallowed so serving continues. The ingest is
    incremental (hash-based), so with no content changes this is a single
    cheap Neo4j round-trip and no embedding calls."""
    try:
        await ingest_content(log=logger)
    except Exception:
        logger.exception("Background content ingestion failed; serving existing data")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_langfuse()
    # Fire-and-forget so uvicorn starts serving immediately.
    ingest_task = asyncio.create_task(_startup_ingest())
    yield
    # Shutdown
    if not ingest_task.done():
        ingest_task.cancel()
    flush_langfuse()
    await close_driver()


app = FastAPI(title="Siva Portfolio RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "running", "service": "Siva Portfolio RAG API"}


app.include_router(health.router)
app.include_router(chat.router)
app.include_router(feedback.router)
