import os
import httpx
from fastapi import APIRouter, Request, Query, Response, HTTPException
from dotenv import load_dotenv
from agent import get_ai_response
from store import add_message

load_dotenv()

router = APIRouter()

VERIFY_TOKEN = "my_secret_token_toto123"
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")


async def send_whatsapp_message(to_phone: str, text: str):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        print("WhatsApp API response:", response.status_code, response.text)

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

@router.post("/webhook")
async def receive_messages(request: Request):
    """Handles incoming data/messages from Meta."""
    payload = await request.json()
    entry = payload.get("entry", [])
    for e in entry:
        for change in e.get("changes", []):
            messages = change.get("value", {}).get("messages", [])
            for msg in messages:
                if msg.get("type") == "text":
                    sender_phone = msg["from"]
                    user_text = msg["text"]["body"]
                    await add_message("user", user_text)
                    ai_reply = await get_ai_response(user_text)
                    await add_message("assistant", ai_reply)
                    await send_whatsapp_message(sender_phone, ai_reply)
    return {"status": "success"}