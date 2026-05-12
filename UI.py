from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from store import conversations, listeners, orders, update_order_status, add_message
import asyncio, json
from starlette.responses import StreamingResponse
from webhook import send_whatsapp_message

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

  .orders-panel {
    width: 300px;
    background: #111b21;
    border-left: 1px solid #374045;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }

  .orders-header {
    background: #202c33;
    padding: 16px;
    font-size: 16px;
    font-weight: 500;
    border-bottom: 1px solid #374045;
  }

  .orders-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  .order-card {
    background: #202c33;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
  }

  .order-id { font-weight: 600; font-size: 13px; color: #00a884; }
  .order-items { font-size: 12px; color: #8696a0; margin: 6px 0; }
  .order-total { font-size: 13px; font-weight: 500; }
  .order-time { font-size: 11px; color: #8696a0; margin-top: 4px; }

  .order-status {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    margin-top: 6px;
  }

  .status-pending { background: #4a3f00; color: #ffd000; }
  .status-confirmed { background: #003a2e; color: #00c897; }
  .status-preparing { background: #1a3a5c; color: #4da6ff; }
  .status-on_the_way { background: #3a1a5c; color: #b44dff; }
  .status-delivered { background: #1a3a1a; color: #4dff4d; }

  .status-btn {
    background: #2a3942;
    border: none;
    color: #e9edef;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    cursor: pointer;
    margin-top: 6px;
    margin-right: 4px;
    transition: background 0.15s;
  }

  .status-btn:hover { background: #374045; }
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

<div class="orders-panel">
  <div class="orders-header">Orders</div>
  <div class="orders-list" id="ordersList">
    <div class="empty-state">No orders yet</div>
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
    loadOrders();
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
    loadOrders();
  };

  const ordersList = document.getElementById("ordersList");
  const NEXT_STATUS = {
    "pending": "confirmed",
    "confirmed": "preparing",
    "preparing": "on_the_way",
    "on_the_way": "delivered"
  };

  function loadOrders() {
    fetch("/orders")
      .then(r => r.json())
      .then(data => renderOrders(data));
  }

  function renderOrders(allOrders) {
    const filtered = activePhone
      ? allOrders.filter(o => o.phone === activePhone)
      : allOrders;
    if (filtered.length === 0) {
      ordersList.innerHTML = '<div class="empty-state">No orders</div>';
      return;
    }
    ordersList.innerHTML = "";
    filtered.reverse().forEach(order => {
      const items = order.items.map(i => i.name + " x" + i.qty).join(", ");
      const next = NEXT_STATUS[order.status];
      const card = document.createElement("div");
      card.className = "order-card";
      card.innerHTML =
        '<div class="order-id">' + order.order_id + '</div>' +
        '<div class="order-items">' + items + '</div>' +
        '<div class="order-total">$' + order.total.toFixed(2) + '</div>' +
        '<div class="order-time">' + order.created_at + '</div>' +
        '<span class="order-status status-' + order.status + '">' + order.status.replace("_", " ") + '</span><br>';
      if (next) {
        const btn = document.createElement("button");
        btn.className = "status-btn";
        btn.textContent = next.replace("_", " ");
        btn.addEventListener("click", function() { updateStatus(order.order_id, next); });
        card.appendChild(btn);
      }
      ordersList.appendChild(card);
    });
  }

  function updateStatus(orderId, newStatus) {
    fetch("/orders/" + orderId + "/status", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({status: newStatus})
    }).then(() => loadOrders());
  }

  loadOrders();
  setInterval(loadOrders, 5000);
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

@router.get("/orders")
async def get_orders():
    return list(orders.values())

STATUS_MESSAGES = {
    "confirmed": "Your order {order_id} has been confirmed and will be prepared shortly.",
    "preparing": "Your order {order_id} is now being prepared.",
    "on_the_way": "Your order {order_id} is on the way!",
    "delivered": "Your order {order_id} has been delivered. Enjoy your meal!",
}

@router.post("/orders/{order_id}/status")
async def set_order_status(order_id: str, body: dict):
    result = update_order_status(order_id, body["status"])
    if not result:
        return {"error": "Order not found"}
    new_status = body["status"]
    if new_status in STATUS_MESSAGES:
        msg_text = STATUS_MESSAGES[new_status].format(order_id=order_id)
        phone = result["phone"]
        await add_message(phone, "assistant", msg_text)
        await send_whatsapp_message(phone, msg_text)
    return result
