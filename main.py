import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from webhook import router as webhook_router
from UI import router as ui_router
from store import get_stale_escalations, set_escalation

logger = logging.getLogger(__name__)

AUTO_DEESCALATE_MINUTES = 15
AUTO_DEESCALATE_POLL_SECONDS = 60


async def _auto_deescalation_loop():
    while True:
        await asyncio.sleep(AUTO_DEESCALATE_POLL_SECONDS)
        try:
            stale = get_stale_escalations(AUTO_DEESCALATE_MINUTES)
            for phone in stale:
                await set_escalation(phone, False)
                logger.info("Auto de-escalated %s after %d min of inactivity", phone, AUTO_DEESCALATE_MINUTES)
        except Exception as ex:
            logger.error("Auto de-escalation error: %s", ex)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_auto_deescalation_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)
app.include_router(webhook_router)
app.include_router(ui_router)
