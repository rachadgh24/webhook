import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("AI_KEY"),
    base_url=os.getenv("AI_URL"),
)

chat_histories = {}


async def get_ai_response(phone: str, user_prompt: str) -> str:
    if phone not in chat_histories:
        chat_histories[phone] = []
    history = chat_histories[phone]
    history.append({"role": "user", "content": user_prompt})
    response = client.chat.completions.create(
        model=os.getenv("AI_MODEL"),
        messages=history,
    )
    reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": reply})
    return reply
