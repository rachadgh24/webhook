from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from store import conversations, listeners
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
    height: 100vh;
  }

  .sidebar {
    width: 300px;
    background: #111b21;
    border-right: 1px solid #374045;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }

  .sidebar-header {
    background: #202c33;
    padding: 16px;
    font-size: 16px;
    font-weight: 500;
    border-bottom: 1px solid #374045;
  }

  .contact-list {
    flex: 1;
    overflow-y: auto;
  }

  .contact {
    padding: 14px 16px;
    cursor: pointer;
    border-bottom: 1px solid #1e2a30;
    transition: background 0.15s;
  }

  .contact:hover { background: #202c33; }

  .contact.active { background: #2a3942; }

  .contact-phone {
    font-size: 14px;
    font-weight: 500;
  }

  .contact-preview {
    font-size: 12px;
    color: #8696a0;
    margin-top: 4px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .chat-container {
    flex: 1;
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

  .empty-state {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #8696a0;
    font-size: 14px;
  }
</style>
</head>
<body>

<div class="sidebar">
  <div class="sidebar-header">Conversations</div>
  <div class="contact-list" id="contactList"></div>
</div>

<div class="chat-container">
  <div class="header" id="chatHeader" style="display:none;">
    <div class="avatar" id="avatarLetter"></div>
    <div class="header-info">
      <h2 id="headerPhone"></h2>
    </div>
  </div>

  <div class="messages" id="messages">
    <div class="empty-state">Select a conversation</div>
  </div>
</div>

<script>
  const allConversations = {};
  let activePhone = null;

  const contactList = document.getElementById("contactList");
  const container = document.getElementById("messages");
  const chatHeader = document.getElementById("chatHeader");
  const headerPhone = document.getElementById("headerPhone");
  const avatarLetter = document.getElementById("avatarLetter");

  function renderContacts() {
    contactList.innerHTML = "";
    const phones = Object.keys(allConversations);
    phones.forEach(phone => {
      const msgs = allConversations[phone];
      const last = msgs[msgs.length - 1];
      const div = document.createElement("div");
      div.className = "contact" + (phone === activePhone ? " active" : "");
      div.innerHTML =
        '<div class="contact-phone">+' + phone + '</div>' +
        '<div class="contact-preview">' + (last ? last.text : "") + '</div>';
      div.onclick = () => selectChat(phone);
      contactList.appendChild(div);
    });
  }

  function renderMessages() {
    if (!activePhone || !allConversations[activePhone]) {
      container.innerHTML = '<div class="empty-state">Select a conversation</div>';
      chatHeader.style.display = "none";
      return;
    }
    chatHeader.style.display = "flex";
    headerPhone.textContent = "+" + activePhone;
    avatarLetter.textContent = activePhone.slice(-2);

    container.innerHTML = "";
    allConversations[activePhone].forEach(msg => {
      const div = document.createElement("div");
      const type = msg.sender === "user" ? "outgoing" : "incoming";
      div.className = "msg " + type;
      div.textContent = msg.text;
      container.appendChild(div);
    });
    container.scrollTop = container.scrollHeight;
  }

  function selectChat(phone) {
    activePhone = phone;
    renderContacts();
    renderMessages();
  }

  function addIncoming(msg) {
    if (!allConversations[msg.phone]) {
      allConversations[msg.phone] = [];
    }
    allConversations[msg.phone].push(msg);
    renderContacts();
    if (msg.phone === activePhone) {
      renderMessages();
    }
  }

  fetch("/history")
    .then(r => r.json())
    .then(data => {
      Object.keys(data).forEach(phone => {
        allConversations[phone] = data[phone];
      });
      renderContacts();
      renderMessages();
    });

  const events = new EventSource("/events");
  events.onmessage = (e) => {
    addIncoming(JSON.parse(e.data));
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
    return conversations
