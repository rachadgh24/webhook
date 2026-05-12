import asyncio

conversations = {}
listeners = []


def get_conversation(phone: str):
    if phone not in conversations:
        conversations[phone] = []
    return conversations[phone]


async def add_message(phone: str, sender: str, text: str):
    msg = {"phone": phone, "sender": sender, "text": text}
    get_conversation(phone).append(msg)
    for queue in listeners:
        await queue.put(msg)
