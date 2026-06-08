import os
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
from tools import TOOL_DEFINITIONS, TOOL_HANDLERS, MENU_PHOTO_MEDIA_ID
from guardrails import classify_input, check_output, check_rate_limit, enforce_output_length
from store import set_escalation, load_chat_history, save_chat_history, get_client

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("AI_KEY"),
    base_url=os.getenv("AI_URL"),
)

SYSTEM_PROMPT = (
    "### CORE MISSION\n"
    "You are a high-efficiency restaurant assistant. Your sole purpose is to handle client requests "
    "(e.g. requesting the catalogue or asking about open hours etc). "
    "You have tools available — use them to look up menu items, prices, hours, and restaurant info.\n\n"
    "### RESPONSE PROTOCOL\n"
    "1. Use your tools to get accurate data, then provide a concise answer. Do NOT try to prolong the conversation.\n"
    "2. Only answer what was asked. Do not volunteer extra information (like delivery details, hours, etc.) unless the client specifically asks.\n\n"
    "### GREETING\n"
    "If the client's name is available in your context and there are no previous assistant messages in this conversation, "
    "open your first reply with a brief greeting: 'Hello [name]!'\n\n"
    "### ORDERING FLOW\n"
    "When a client wants to order:\n"
    "1. Use place_order with the client's phone number and the items they want. The phone number is provided in the system context.\n"
    "2. Summarize the order (items, quantities, total price) and ask the client to confirm.\n"
    "3. When the client confirms, use confirm_order with the order ID.\n"
    "4. After confirming, the tool result will indicate one of two cases:\n"
    "   - No delivery info on file: ask the client for their full name and delivery address in one message. Once they reply, call save_client_info.\n"
    "   - A saved address is shown: ask the client to confirm it (e.g. 'Delivering to [address], correct?'). If they provide a different address, call save_client_info to update it.\n"
    "5. If the client asks about their order, use check_order_status.\n\n"
    "### TONE\n"
    "Professional but not too formal or rude, precise, and brief. No emojis, no personality."
)

MAX_HISTORY_MESSAGES = 10
MAX_TOOL_ROUNDS = 5
SYSTEM_PREFIX_LEN = 2


def _build_client_context(phone: str) -> str:
    context = f"The current client's phone number is: {phone}"
    client = get_client(phone)
    if client:
        context += f"\nClient name: {client['name']}. Saved delivery address: {client['address']}."
    return context


def _trim_history(history: list) -> None:
    """Keep system prefix; cap the rest to MAX_HISTORY_MESSAGES."""
    while len(history) - SYSTEM_PREFIX_LEN > MAX_HISTORY_MESSAGES:
        del history[SYSTEM_PREFIX_LEN]
    while len(history) > SYSTEM_PREFIX_LEN and history[SYSTEM_PREFIX_LEN].get("role") != "user":
        del history[SYSTEM_PREFIX_LEN]


IMAGE_TOOLS = {
    "send_menu_photo": {"media_id": MENU_PHOTO_MEDIA_ID, "caption": "Here's our menu"},
}


async def get_ai_response(phone: str, user_prompt: str):
    rate_refusal = check_rate_limit(phone)
    if rate_refusal:
        return {"text": rate_refusal, "images": []}

    result = await classify_input(user_prompt)
    if result["escalate"]:
        await set_escalation(phone, True)
        return {
            "text": "I'm connecting you with our team right away. A staff member will be with you shortly.",
            "images": [],
        }
    if result["refusal"]:
        return {"text": result["refusal"], "images": []}

    history = load_chat_history(phone)
    if not history:
        history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": _build_client_context(phone)},
        ]
    else:
        # Refresh client context on every turn so name/address changes are reflected immediately.
        history[1] = {"role": "system", "content": _build_client_context(phone)}

    history.append({"role": "user", "content": user_prompt})
    _trim_history(history)
    images_to_send = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = await client.chat.completions.create(
            model=os.getenv("AI_MODEL"),
            messages=history,
            tools=TOOL_DEFINITIONS,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            text = check_output(msg.content) or msg.content
            text = enforce_output_length(text)
            history.append({"role": "assistant", "content": text})
            save_chat_history(phone, history)
            return {"text": text, "images": images_to_send}

        history.append(msg.model_dump(exclude_none=True))

        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            handler = TOOL_HANDLERS.get(fn_name)

            if fn_name in IMAGE_TOOLS:
                images_to_send.append(IMAGE_TOOLS[fn_name])

            if handler:
                result = handler(fn_args)
            else:
                result = f"Unknown tool: {fn_name}"

            history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    fallback = "Sorry, I couldn't process your request. Please try again."
    history.append({"role": "assistant", "content": fallback})
    save_chat_history(phone, history)
    return {"text": fallback, "images": []}
