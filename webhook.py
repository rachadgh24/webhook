import hashlib
import hmac
import json
import logging
import os
import time
import httpx
from cachetools import TTLCache
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Query, Response, HTTPException
from dotenv import load_dotenv
from langfuse import observe
from agent import get_ai_response
from store import add_message, get_delivery_log, log_delivery, is_escalated
from metrics import log_metric

load_dotenv()

logger = logging.getLogger(__name__)
processed_messages = TTLCache(maxsize=10_000, ttl=600)
http_client = httpx.AsyncClient()

router = APIRouter()


@router.on_event("shutdown")
async def shutdown_http_client():
    await http_client.aclose()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
META_APP_SECRET = os.getenv("META_APP_SECRET")


def verify_x_hub_signature_256(body: bytes, signature_header: str | None, app_secret: str | None) -> bool:
    if not signature_header or not app_secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header.removeprefix("sha256=")
    digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


async def verify_meta_webhook(request: Request) -> bytes:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_x_hub_signature_256(body, signature, META_APP_SECRET):
        raise HTTPException(status_code=401, detail="Invalid or missing signature")
    return body


def _missing_whatsapp_config():
    missing = []
    if not PHONE_NUMBER_ID:
        missing.append("PHONE_NUMBER_ID")
    if not WHATSAPP_TOKEN:
        missing.append("WHATSAPP_TOKEN")
    return missing


@observe
async def _send_whatsapp_payload(to_phone: str, payload: dict, stage: str):
    missing = _missing_whatsapp_config()
    if missing:
        detail = f"Missing env vars: {', '.join(missing)}"
        await log_delivery(stage, to_phone, ok=False, detail=detail)
        print(f"ERROR {stage}: {detail}")
        return False

    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    response = await http_client.post(url, json=payload, headers=headers)

    ok = response.is_success
    detail = response.text
    await log_delivery(stage, to_phone, ok=ok, status_code=response.status_code, detail=detail)
    print(f"{stage}: to={to_phone} status={response.status_code} body={response.text}")
    return ok


@observe
async def send_whatsapp_message(to_phone: str, text: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    return await _send_whatsapp_payload(to_phone, payload, "whatsapp_text_send")


@observe
async def send_whatsapp_image(to_phone: str, media_id: str, caption: str = ""):
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "image",
        "image": {"id": media_id, "caption": caption},
    }
    return await _send_whatsapp_payload(to_phone, payload, "whatsapp_image_send")


@observe
async def process_inbound_message(sender_phone: str, msg: dict):
    if msg.get("type") == "text":
        user_text = msg["text"]["body"]
        await add_message(sender_phone, "user", user_text)
        await log_delivery("inbound_stored", sender_phone, ok=True, detail=user_text[:120])
        if is_escalated(sender_phone):
            await log_delivery("escalated_silence", sender_phone, ok=True, detail="human handoff active")
            return
        try:
            t0 = time.monotonic()
            result = await get_ai_response(sender_phone, user_text)
            latency_ms = int((time.monotonic() - t0) * 1000)
            await log_metric("message_latency", phone=sender_phone, value_ms=latency_ms)
            await log_delivery("ai_response", sender_phone, ok=True, detail=result["text"][:120])

            await add_message(sender_phone, "assistant", result["text"])
            await send_whatsapp_message(sender_phone, result["text"])

            for img in result["images"]:
                await add_message(sender_phone, "assistant", f"[Photo: {img['caption']}]")
                await send_whatsapp_image(sender_phone, img["media_id"], img["caption"])
        except Exception as ex:
            detail = f"{type(ex).__name__}: {ex}"
            await log_delivery("agent_error", sender_phone, ok=False, detail=detail)
            print(f"ERROR in agent: {detail}")
            error_reply = "Sorry, something went wrong. Please try again."
            await add_message(sender_phone, "assistant", error_reply)
            await send_whatsapp_message(sender_phone, error_reply)
    else:
        reply = "I can only process text messages. Please send your request as text."
        await add_message(sender_phone, "assistant", reply)
        await log_delivery("non_text_message", sender_phone, ok=True, detail=msg.get("type", "unknown"))
        await send_whatsapp_message(sender_phone, reply)


@router.get("/webhook")
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge")
):
    """Handles the initial verification from Meta."""
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("WEBHOOK_VERIFIED")

        return Response(content=challenge, media_type="text/plain")
    
    raise HTTPException(status_code=403, detail="Verification failed")

@router.get("/debug/delivery")
async def delivery_debug():
    return {
        "phone_number_id_set": bool(PHONE_NUMBER_ID),
        "whatsapp_token_set": bool(WHATSAPP_TOKEN),
        "attempts": get_delivery_log(),
    }


@router.post("/webhook")
async def receive_messages(
    background_tasks: BackgroundTasks,
    body: bytes = Depends(verify_meta_webhook),
):
    """Acknowledge Meta webhooks quickly; process messages in the background."""
    payload = json.loads(body)
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                wamid = msg.get("id")
                if wamid and wamid in processed_messages:
                    logger.warning("Duplicate webhook message ignored: wamid=%s", wamid)
                    continue

                if wamid:
                    processed_messages[wamid] = True

                background_tasks.add_task(process_inbound_message, msg["from"], msg)

    return {"status": "success"}
