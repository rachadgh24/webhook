import asyncio
import logging
from langfuse import observe
from store import _supabase

logger = logging.getLogger(__name__)


@observe
async def log_metric(event: str, phone: str | None = None, **kwargs):
    “””Fire-and-forget metrics write. Never raises â€” a metric failure must not break the main flow.”””
    logger.info(“log_metric start event=%s phone=%s”, event, phone)
    row = {“event”: event, “phone”: phone, **kwargs}
    try:
        await asyncio.to_thread(_supabase.table(“metrics”).insert(row).execute)
    except Exception as exc:
        logger.error(“log_metric error event=%s: %s”, event, exc)
    logger.info(“log_metric done event=%s”, event)

