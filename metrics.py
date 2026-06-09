import asyncio
import logging
from langfuse.decorators import observe
from store import _supabase

logger = logging.getLogger(__name__)


@observe
async def log_metric(event: str, phone: str | None = None, **kwargs):
    """Fire-and-forget metrics write. Never raises — a metric failure must not break the main flow."""
    row = {"event": event, "phone": phone, **kwargs}
    try:
        await asyncio.to_thread(_supabase.table("metrics").insert(row).execute)
    except Exception as exc:
        logger.warning("metrics write failed: %s", exc)
