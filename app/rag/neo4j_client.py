import logging
from neo4j import AsyncGraphDatabase

from app.config import settings

logger = logging.getLogger(__name__)
_driver = None

# Aura reaps idle connections server-side; validate an idle connection before
# reusing it and recycle connections well before that window so a stale one is
# never handed to a query ("defunct connection" errors). Named so the startup
# log below stays in sync with the values actually applied.
_LIVENESS_CHECK_TIMEOUT = 30
_MAX_CONNECTION_LIFETIME = 300


def get_driver():
    global _driver
    if _driver is None:
        logger.info(
            "Initializing Async Neo4j driver "
            "(liveness_check_timeout=%ss, max_connection_lifetime=%ss)",
            _LIVENESS_CHECK_TIMEOUT,
            _MAX_CONNECTION_LIFETIME,
        )
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
            connection_timeout=10,
            max_transaction_retry_time=5,
            liveness_check_timeout=_LIVENESS_CHECK_TIMEOUT,
            max_connection_lifetime=_MAX_CONNECTION_LIFETIME,
        )
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        logger.info("Closing Async Neo4j GraphDatabase driver instance")
        await _driver.close()
        _driver = None
