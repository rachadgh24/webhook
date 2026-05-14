import os
import httpx
from fastapi import APIRouter, Request, Query, Response, HTTPException
from dotenv import load_dotenv
from agent import get_ai_response
from store import add_message, delivery_log, log_delivery

load_dotenv()

router = APIRouter()

VERIFY_TOKEN = "my_secret_token_toto123"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")



def _missing_whatsapp_config():
    missing = []
    if not PHONE_NUMBER_ID:
        missing.append("PHONE_NUMBER_ID")
    if not WHATSAPP_TOKEN:
        missing.append("WHATSAPP_TOKEN")
    return missing


async def _send_whatsapp_payload(to_phone: str, payload: dict, stage: str):
    missing = _missing_whatsapp_config()
    if missing:
        detail = f"Missing env vars: {', '.join(missing)}"
        log_delivery(stage, to_phone, ok=False, detail=detail)
        print(f"ERROR {stage}: {detail}")
        return False

    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)

    ok = response.is_success
    detail = response.text
    log_delivery(stage, to_phone, ok=ok, status_code=response.status_code, detail=detail)
    print(f"{stage}: to={to_phone} status={response.status_code} body={response.text}")
    return ok


async def send_whatsapp_message(to_phone: str, text: str):
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    return await _send_whatsapp_payload(to_phone, payload, "whatsapp_text_send")


async def send_whatsapp_image(to_phone: str, media_id: str, caption: str = ""):
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "image",
        "image": {"id": media_id, "caption": caption},
    }
    return await _send_whatsapp_payload(to_phone, payload, "whatsapp_image_send")

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
        "attempts": list(reversed(delivery_log)),
    }


@router.post("/webhook")
async def receive_messages(request: Request):
    """Handles incoming data/messages from Meta."""
    payload = await request.json()
    log_delivery("webhook_received", ok=True, detail=f"object={payload.get('object')}")
    handled = False
    entry = payload.get("entry", [])
    for e in entry:
        for change in e.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            if not messages:
                field = change.get("field", "unknown")
                log_delivery("no_inbound_messages", ok=True, detail=f"field={field}")
                continue

            for msg in messages:
                handled = True
                sender_phone = msg["from"]
                if msg.get("type") == "text":
                    user_text = msg["text"]["body"]
                    await add_message(sender_phone, "user", user_text)
                    log_delivery("inbound_stored", sender_phone, ok=True, detail=user_text[:120])
                    try:
                        result = await get_ai_response(sender_phone, user_text)
                        log_delivery("ai_response", sender_phone, ok=True, detail=result["text"][:120])

                        await add_message(sender_phone, "assistant", result["text"])
                        await send_whatsapp_message(sender_phone, result["text"])

                        for img in result["images"]:
                            await add_message(sender_phone, "assistant", f"[Photo: {img['caption']}]")
                            await send_whatsapp_image(sender_phone, img["media_id"], img["caption"])
                    except Exception as ex:
                        detail = f"{type(ex).__name__}: {ex}"
                        log_delivery("agent_error", sender_phone, ok=False, detail=detail)
                        print(f"ERROR in agent: {detail}")
                        error_reply = "Sorry, something went wrong. Please try again."
                        await add_message(sender_phone, "assistant", error_reply)
                        await send_whatsapp_message(sender_phone, error_reply)
                else:
                    reply = "I can only process text messages. Please send your request as text."
                    await add_message(sender_phone, "assistant", reply)
                    log_delivery("non_text_message", sender_phone, ok=True, detail=msg.get("type", "unknown"))
                    await send_whatsapp_message(sender_phone, reply)

    if not handled:
        log_delivery("no_handled_messages", ok=True, detail="Webhook payload had no message events")
    return {"status": "success"}