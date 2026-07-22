from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.rag.neo4j_client import close_driver
from app.rag.observability import flush_langfuse, init_langfuse
from app.routes import chat, feedback, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_langfuse()
    yield
    # Shutdown
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
