import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("AI_KEY"),
    base_url=os.getenv("AI_URL"),
)

chat_history = []

async def get_ai_response(user_prompt: str) -> str:
    chat_history.append({"role": "user", "content": user_prompt})
    response = client.chat.completions.create(
        model=os.getenv("AI_MODEL"),
        messages=chat_history,
    )
    reply = response.choices[0].message.content
    chat_history.append({"role": "assistant", "content": reply})
    return reply

