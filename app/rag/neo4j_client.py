import logging
from neo4j import AsyncGraphDatabase

from app.config import settings

logger = logging.getLogger(__name__)
_driver = None


def get_driver():
    global _driver
    if _driver is None:
        logger.info("Initializing Async Neo4j GraphDatabase driver instance")
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
            connection_timeout=10,
            max_transaction_retry_time=5,
            # Aura reaps idle connections server-side; validate an idle connection
            # before reusing it and recycle connections well before that window so
            # a stale one is never handed to a query ("defunct connection" errors).
            liveness_check_timeout=30,
            max_connection_lifetime=300,
        )
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        logger.info("Closing Async Neo4j GraphDatabase driver instance")
        await _driver.close()
        _driver = None
