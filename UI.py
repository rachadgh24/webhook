from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from store import conversations, listeners, orders, update_order_status, escalated_phones, set_escalation, add_message
from webhook import send_whatsapp_message
import asyncio, json
from starlette.responses import StreamingResponse

router = APIRouter()

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0b141a;
    color: #e9edef;
    display: flex;
    height: 100vh;
  }

  /* ---- Sidebar ---- */
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

  .contact-list { flex: 1; overflow-y: auto; }

  .contact {
    padding: 14px 16px;
    cursor: pointer;
    border-bottom: 1px solid #1e2a30;
    transition: background 0.15s;
    border-left: 3px solid transparent;
  }

  .contact:hover { background: #202c33; }
  .contact.active { background: #2a3942; }
  .contact.escalated { border-left-color: #e53935; }

  .contact-phone {
    font-size: 14px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .escalated-badge {
    display: inline-block;
    background: #e53935;
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 10px;
  }

  .contact-preview {
    font-size: 12px;
    color: #8696a0;
    margin-top: 4px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  /* ---- Chat area ---- */
  .chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100vh;
    min-width: 0;
  }

  .header {
    background: #202c33;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid #374045;
    flex-shrink: 0;
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
    flex-shrink: 0;
  }

  .header-info { flex: 1; min-width: 0; }
  .header-info h2 { font-size: 16px; font-weight: 500; }

  .escalation-status {
    font-size: 11px;
    font-weight: 600;
    color: #e53935;
    margin-top: 2px;
  }

  .handoff-btn {
    background: #e53935;
    color: #fff;
    border: none;
    padding: 7px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
    flex-shrink: 0;
  }
  .handoff-btn:hover { background: #c62828; }
  .handoff-btn.bot { background: #00a884; }
  .handoff-btn.bot:hover { background: #00876d; }

  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    background: #0b141a;
  }

  /* Admin perspective: customer on left, bot/admin on right */
  .msg {
    max-width: 75%;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 14px;
    line-height: 1.4;
  }

  .from-customer {
    background: #202c33;
    align-self: flex-start;
    border-top-left-radius: 0;
  }

  .from-restaurant {
    background: #005c4b;
    align-self: flex-end;
    border-top-right-radius: 0;
  }

  .msg-label {
    font-size: 10px;
    color: #8696a0;
    margin-bottom: 2px;
  }

  /* ---- Admin reply bar ---- */
  .reply-bar {
    background: #202c33;
    border-top: 1px solid #374045;
    padding: 10px 14px;
    display: none;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }

  .reply-bar.visible { display: flex; }

  .reply-input {
    flex: 1;
    background: #2a3942;
    border: none;
    border-radius: 20px;
    padding: 10px 16px;
    color: #e9edef;
    font-size: 14px;
    outline: none;
  }

  .reply-input::placeholder { color: #8696a0; }

  .reply-send {
    background: #00a884;
    border: none;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: background 0.15s;
  }

  .reply-send:hover { background: #00876d; }

  .reply-send svg { width: 20px; height: 20px; fill: #fff; }

  .empty-state {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #8696a0;
    font-size: 14px;
  }

  /* ---- Orders panel ---- */
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

  .orders-list { flex: 1; overflow-y: auto; padding: 8px; }

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

  .status-pending    { background: #4a3f00; color: #ffd000; }
  .status-confirmed  { background: #003a2e; color: #00c897; }
  .status-preparing  { background: #1a3a5c; color: #4da6ff; }
  .status-on_the_way { background: #3a1a5c; color: #b44dff; }
  .status-delivered  { background: #1a3a1a; color: #4dff4d; }

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
      <div class="escalation-status" id="escalationStatus" style="display:none;">
        &#9888; Waiting for human response
      </div>
    </div>
    <button class="handoff-btn" id="handoffBtn" onclick="toggleHandoff()"></button>
  </div>

  <div class="messages" id="messages">
    <div class="empty-state">Select a conversation</div>
  </div>

  <div class="reply-bar" id="replyBar">
    <input
      class="reply-input"
      id="adminInput"
      placeholder="Reply as restaurant..."
      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendAdminReply();}"
    />
    <button class="reply-send" onclick="sendAdminReply()" title="Send">
      <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg>
    </button>
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
  const escalatedPhones = new Set();
  let activePhone = null;

  const contactList   = document.getElementById("contactList");
  const container     = document.getElementById("messages");
  const chatHeader    = document.getElementById("chatHeader");
  const headerPhone   = document.getElementById("headerPhone");
  const avatarLetter  = document.getElementById("avatarLetter");
  const escalStatus   = document.getElementById("escalationStatus");
  const handoffBtn    = document.getElementById("handoffBtn");
  const replyBar      = document.getElementById("replyBar");
  const adminInput    = document.getElementById("adminInput");

  // --- Audio alert ---
  function playAlert() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [0, 0.2].forEach(delay => {
        const osc  = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = "sine";
        osc.frequency.value = 880;
        gain.gain.setValueAtTime(0, ctx.currentTime + delay);
        gain.gain.linearRampToValueAtTime(0.35, ctx.currentTime + delay + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.25);
        osc.start(ctx.currentTime + delay);
        osc.stop(ctx.currentTime + delay + 0.3);
      });
    } catch (_) {}
  }

  // --- Render sidebar contacts ---
  function renderContacts() {
    contactList.innerHTML = "";
    Object.keys(allConversations).forEach(phone => {
      const msgs   = allConversations[phone];
      const last   = msgs[msgs.length - 1];
      const isEsc  = escalatedPhones.has(phone);

      const div = document.createElement("div");
      div.className = "contact"
        + (phone === activePhone ? " active" : "")
        + (isEsc ? " escalated" : "");

      const phoneDiv = document.createElement("div");
      phoneDiv.className = "contact-phone";
      phoneDiv.textContent = "+" + phone;

      if (isEsc) {
        const badge = document.createElement("span");
        badge.className = "escalated-badge";
        badge.textContent = "ESCALATED";
        phoneDiv.appendChild(badge);
      }

      const previewDiv = document.createElement("div");
      previewDiv.className = "contact-preview";
      previewDiv.textContent = last ? last.text : "";

      div.appendChild(phoneDiv);
      div.appendChild(previewDiv);
      div.onclick = () => selectChat(phone);
      contactList.appendChild(div);
    });
  }

  // --- Render header state ---
  function renderHeader() {
    if (!activePhone) return;
    const isEsc = escalatedPhones.has(activePhone);
    escalStatus.style.display    = isEsc ? "block" : "none";
    handoffBtn.textContent       = isEsc ? "Hand back to bot" : "Take over";
    handoffBtn.className         = "handoff-btn" + (isEsc ? " bot" : "");
    replyBar.className           = "reply-bar" + (isEsc ? " visible" : "");
  }

  // --- Render chat messages (admin perspective) ---
  function renderMessages() {
    if (!activePhone || !allConversations[activePhone]) {
      container.innerHTML = '<div class="empty-state">Select a conversation</div>';
      chatHeader.style.display = "none";
      replyBar.className = "reply-bar";
      return;
    }
    chatHeader.style.display = "flex";
    headerPhone.textContent  = "+" + activePhone;
    avatarLetter.textContent = activePhone.slice(-2);
    renderHeader();

    container.innerHTML = "";
    allConversations[activePhone].forEach(msg => {
      const isCustomer = msg.sender === "user";
      const wrapper = document.createElement("div");
      wrapper.style.display        = "flex";
      wrapper.style.flexDirection  = "column";
      wrapper.style.alignItems     = isCustomer ? "flex-start" : "flex-end";
      wrapper.style.marginBottom   = "4px";

      const label = document.createElement("div");
      label.className   = "msg-label";
      const senderLabel = { user: "Customer", assistant: "Bot", admin: "Admin" };
      label.textContent = senderLabel[msg.sender] || msg.sender;

      const bubble = document.createElement("div");
      bubble.className  = "msg " + (isCustomer ? "from-customer" : "from-restaurant");
      bubble.textContent = msg.text;

      wrapper.appendChild(label);
      wrapper.appendChild(bubble);
      container.appendChild(wrapper);
    });
    container.scrollTop = container.scrollHeight;
  }

  function selectChat(phone) {
    activePhone = phone;
    renderContacts();
    renderMessages();
    loadOrders();
  }

  function addMessage(msg) {
    if (!allConversations[msg.phone]) allConversations[msg.phone] = [];
    allConversations[msg.phone].push(msg);
    renderContacts();
    if (msg.phone === activePhone) renderMessages();
  }

  function handleEscalation(event) {
    const wasEscalated = escalatedPhones.has(event.phone);
    if (event.escalated) {
      escalatedPhones.add(event.phone);
      if (!wasEscalated) playAlert();
    } else {
      escalatedPhones.delete(event.phone);
    }
    renderContacts();
    if (event.phone === activePhone) renderHeader();
  }

  // --- Handoff toggle ---
  function toggleHandoff() {
    if (!activePhone) return;
    const isEsc = escalatedPhones.has(activePhone);
    fetch("/escalate/" + activePhone, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({escalated: !isEsc})
    });
  }

  // --- Admin reply ---
  function sendAdminReply() {
    const text = adminInput.value.trim();
    if (!text || !activePhone) return;
    adminInput.value = "";
    fetch("/admin-reply/" + activePhone, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text})
    });
  }

  // --- Initial load ---
  Promise.all([
    fetch("/history").then(r => r.json()),
    fetch("/escalated").then(r => r.json()),
  ]).then(([hist, esc]) => {
    Object.keys(hist).forEach(phone => { allConversations[phone] = hist[phone]; });
    esc.forEach(phone => escalatedPhones.add(phone));
    renderContacts();
    renderMessages();
  });

  // --- SSE ---
  const events = new EventSource("/events");
  events.onmessage = (e) => {
    const event = JSON.parse(e.data);
    if (event.type === "escalation") {
      handleEscalation(event);
    } else {
      addMessage(event);
      loadOrders();
    }
  };

  // --- Orders panel ---
  const ordersList = document.getElementById("ordersList");
  const NEXT_STATUS = {
    pending: "confirmed",
    confirmed: "preparing",
    preparing: "on_the_way",
    on_the_way: "delivered",
  };

  function loadOrders() {
    fetch("/orders").then(r => r.json()).then(renderOrders);
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
    filtered.slice().reverse().forEach(order => {
      const items = order.items.map(i => i.name + " x" + i.qty).join(", ");
      const next  = NEXT_STATUS[order.status];
      const card  = document.createElement("div");
      card.className = "order-card";
      card.innerHTML =
        '<div class="order-id">'    + order.order_id + '</div>' +
        '<div class="order-items">' + items + '</div>' +
        '<div class="order-total">$' + order.total.toFixed(2) + '</div>' +
        '<div class="order-time">'  + order.created_at + '</div>' +
        '<span class="order-status status-' + order.status + '">' +
          order.status.replace("_", " ") + '</span><br>';
      if (next) {
        const btn = document.createElement("button");
        btn.className = "status-btn";
        btn.textContent = next.replace("_", " ");
        btn.addEventListener("click", () => updateStatus(order.order_id, next));
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

@router.get("/escalated")
async def get_escalated():
    return list(escalated_phones)

@router.post("/escalate/{phone}")
async def set_escalation_endpoint(phone: str, body: dict):
    await set_escalation(phone, bool(body.get("escalated", False)))
    return {"phone": phone, "escalated": phone in escalated_phones}

@router.post("/admin-reply/{phone}")
async def admin_reply(phone: str, body: dict):
    text = body.get("text", "").strip()
    if not text:
        return {"error": "Empty message"}
    await add_message(phone, "admin", text)
    await send_whatsapp_message(phone, text)
    return {"ok": True}

@router.get("/orders")
async def get_orders():
    return list(orders.values())

@router.post("/orders/{order_id}/status")
async def set_order_status(order_id: str, body: dict):
    result = update_order_status(order_id, body["status"])
    if not result:
        return {"error": "Order not found"}
    return result
