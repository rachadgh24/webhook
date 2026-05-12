from fastapi import APIRouter, Request, Query, Response, HTTPException
from agent import get_ai_response
from store import add_message

router = APIRouter()

VERIFY_TOKEN = "my_secret_token_toto123"

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
                    user_text = msg["text"]["body"]
                    await add_message("user", user_text)
                    ai_reply = await get_ai_response(user_text)
                    await add_message("assistant", ai_reply)
                    print("AI Reply:", ai_reply)
    return {"status": "success"}