"""Tiny retry helper for transient failures (network blips, connect timeouts).

Deterministic exponential backoff, no dependency. Retries only the exception types the
caller names — never a blanket catch, so real errors (bad SQL, missing file) fail fast.
"""

import logging
import time

logger = logging.getLogger(__name__)


def with_retry(fn, *, attempts: int = 3, base_delay: float = 1.0,
               exceptions: tuple = (Exception,), what: str = "operation"):
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except exceptions as exc:
            last = exc
            if attempt == attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("%s failed (attempt %d/%d): %s — retrying in %.1fs",
                           what, attempt, attempts, exc, delay)
            time.sleep(delay)
    raise last
