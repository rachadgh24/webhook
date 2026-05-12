from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from store import conversation, listeners
import asyncio, json
from starlette.responses import StreamingResponse

router = APIRouter()

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chat</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0b141a;
    color: #e9edef;
    display: flex;
    justify-content: center;
    height: 100vh;
  }

  .chat-container {
    width: 100%;
    max-width: 500px;
    display: flex;
    flex-direction: column;
    height: 100vh;
  }

  .header {
    background: #202c33;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid #374045;
  }

  .avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: #00a884;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 18px;
  }

  .header-info h2 { font-size: 16px; font-weight: 500; }
  .header-info span { font-size: 12px; color: #8696a0; }

  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    background: #0b141a;
  }

  .msg {
    max-width: 75%;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 14px;
    line-height: 1.4;
    position: relative;
  }

  .msg .time {
    font-size: 11px;
    color: #8696a0;
    float: right;
    margin-left: 8px;
    margin-top: 4px;
  }

  .incoming {
    background: #202c33;
    align-self: flex-start;
    border-top-left-radius: 0;
  }

  .outgoing {
    background: #005c4b;
    align-self: flex-end;
    border-top-right-radius: 0;
  }

</style>
</head>
<body>

<div class="chat-container">
  <div class="header">
    <div class="avatar">T</div>
    <div class="header-info">
      <h2>Toto</h2>
      <span>online</span>
    </div>
  </div>

  <div class="messages" id="messages"></div>
</div>

<script>
  const messages = [];
  const container = document.getElementById("messages");

  function render() {
    container.innerHTML = "";
    messages.forEach(msg => {
      const div = document.createElement("div");
      const type = msg.sender === "user" ? "outgoing" : "incoming";
      div.className = "msg " + type;
      div.innerHTML = msg.text;
      container.appendChild(div);
    });
    container.scrollTop = container.scrollHeight;
  }

  fetch("/history")
    .then(r => r.json())
    .then(data => { data.forEach(m => messages.push(m)); render(); });

  const events = new EventSource("/events");
  events.onmessage = (e) => {
    messages.push(JSON.parse(e.data));
    render();
  };
</script>

</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def chat_ui():
    return HTML

@router.get("/events")
async def sse():
    queue = asyncio.Queue()
    listeners.append(queue)
    
    async def stream():
        try:
            while True:
                msg = await queue.get()
                yield f"data: {json.dumps(msg)}\n\n"
        finally:
            listeners.remove(queue)
    
    return StreamingResponse(stream(), media_type="text/event-stream")

@router.get("/history")
async def history():
    return conversation