import os
import json
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from tools import TOOL_DEFINITIONS, TOOL_HANDLERS, MENU_PHOTO_MEDIA_ID
from guardrails import check_input, check_output, check_rate_limit, enforce_output_length, should_escalate
from store import set_escalation, load_chat_history, save_chat_history

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
    "### ORDERING FLOW\n"
    "When a client wants to order:\n"
    "1. Use place_order with the client's phone number and the items they want. The phone number is provided in the first user message context.\n"
    "2. Summarize the order (items, quantities, total price) and ask the client to confirm.\n"
    "3. When the client confirms, use confirm_order with the order ID.\n"
    "4. If the client asks about their order, use check_order_status.\n\n"
    "### TONE\n"
    "Professional but not too formal or rude, precise, and brief. No emojis, no personality."
)

MAX_HISTORY_MESSAGES = 10
MAX_TOOL_ROUNDS = 5
SYSTEM_PREFIX_LEN = 2


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

    # Run both classifiers in parallel; escalation takes priority over refusal.
    escalate, refusal = await asyncio.gather(
        should_escalate(user_prompt),
        check_input(user_prompt),
    )
    if escalate:
        await set_escalation(phone, True)
        return {
            "text": "I'm connecting you with our team right away. A staff member will be with you shortly.",
            "images": [],
        }
    if refusal:
        return {"text": refusal, "images": []}

    history = load_chat_history(phone)
    if not history:
        history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"The current client's phone number is: {phone}"},
        ]

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
