import asyncio

conversation = []
listeners = []

async def add_message(sender: str, text: str):
    msg = {"sender": sender, "text": text}
    conversation.append(msg)
    for queue in listeners:
        await queue.put(msg)