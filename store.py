import os
import asyncio
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from dotenv import load_dotenv
from langfuse import observe

load_dotenv()

_supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

listeners = []
MAX_DELIVERY_LOG = 50


@observe
async def log_delivery(stage: str, phone: str | None = None, ok: bool = True, status_code: int | None = None, detail: str = ""):
    row = {
        "at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "phone": phone,
        "ok": ok,
        "status_code": status_code,
        "detail": detail,
    }
    await asyncio.to_thread(_supabase.table("delivery_log").insert(row).execute)


@observe
def get_delivery_log():
    result = _supabase.table("delivery_log").select("*").order("id", desc=True).limit(MAX_DELIVERY_LOG).execute()
    return result.data


@observe
def get_conversation(phone: str):
    result = _supabase.table("conversations").select("sender, text").eq("phone", phone).order("id").execute()
    return [{"phone": phone, "sender": r["sender"], "text": r["text"]} for r in result.data]


@observe
def get_all_conversations() -> dict:
    result = _supabase.table("conversations").select("phone, sender, text").order("id").execute()
    grouped: dict = {}
    for r in result.data:
        grouped.setdefault(r["phone"], []).append({"phone": r["phone"], "sender": r["sender"], "text": r["text"]})
    return grouped


@observe
def get_escalated_phones() -> list:
    result = _supabase.table("escalations").select("phone").eq("escalated", True).execute()
    return [r["phone"] for r in result.data]


@observe
def load_menu() -> dict:
    cats = _supabase.table("categories").select("id, name").eq("active", True).order("display_order").execute()
    cat_map = {c["id"]: c["name"] for c in cats.data}
    result = _supabase.table("items").select("*").eq("active", True).order("display_order").execute()
    menu = {}
    for row in result.data:
        category = cat_map.get(row["category_id"], "other")
        if category not in menu:
            menu[category] = []
        menu[category].append({
            "name": row["name"],
            "price": float(row["price"]),
            "description": row.get("description", ""),
        })
    return menu


@observe
def get_all_orders() -> list:
    result = _supabase.table("orders").select("*").eq("hidden", False).execute()
    return result.data


@observe
def hide_order(order_id: str):
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        return None
    _supabase.table("orders").update({"hidden": True}).eq("order_id", order_id).execute()
    return {"ok": True}


HISTORY_WINDOW_HOURS = 12


@observe
def load_chat_history(phone: str) -> list:
    result = _supabase.table("chat_histories").select("messages").eq("phone", phone).execute()
    if not result.data:
        return []
    messages = result.data[0]["messages"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HISTORY_WINDOW_HOURS)
    filtered = []
    for msg in messages:
        if msg.get("role") == "system" and not msg.get("subtype"):
            # Static system messages (SYSTEM_PROMPT, phone context) â€” always keep
            filtered.append(msg)
            continue
        ts_str = msg.get("ts")
        if not ts_str:
            continue
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            filtered.append(msg)
    # Drop any orphaned non-user messages left at the start of the conversation window
    system_end = next((i for i, m in enumerate(filtered) if m.get("role") != "system"), len(filtered))
    while len(filtered) > system_end and filtered[system_end].get("role") != "user":
        filtered.pop(system_end)
    return filtered


@observe
def save_chat_history(phone: str, messages: list) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    for msg in messages:
        if "ts" not in msg and (msg.get("role") != "system" or msg.get("subtype")):
            msg["ts"] = now_iso
    _supabase.table("chat_histories").upsert({"phone": phone, "messages": messages}).execute()


@observe
def append_to_chat_history(phone: str, message: dict) -> None:
    history = load_chat_history(phone)
    if not history:
        return
    history.append(message)
    save_chat_history(phone, history)


@observe
def is_escalated(phone: str) -> bool:
    result = _supabase.table("escalations").select("escalated").eq("phone", phone).execute()
    return bool(result.data and result.data[0]["escalated"])


@observe
async def set_escalation(phone: str, escalated: bool):
    now_iso = datetime.now(timezone.utc).isoformat()
    if escalated:
        data = {"phone": phone, "escalated": True, "escalated_at": now_iso, "last_admin_reply_at": None}
        note = "A human agent has taken over this conversation. Do not send any responses until the conversation is handed back to you."
    else:
        data = {"phone": phone, "escalated": False, "escalated_at": None, "last_admin_reply_at": None}
        note = "The human agent has finished and handed the conversation back to you. Resume assisting the customer normally. You have full context of what the agent said above."
    _supabase.table("escalations").upsert(data).execute()
    append_to_chat_history(phone, {"role": "system", "subtype": "escalation_note", "content": note})
    event = {"type": "escalation", "phone": phone, "escalated": escalated}
    for queue in listeners:
        await queue.put(event)


@observe
def update_last_admin_reply(phone: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    _supabase.table("escalations").update({"last_admin_reply_at": now_iso}).eq("phone", phone).execute()


@observe
def get_stale_escalations(minutes: int = 15) -> list:
    result = _supabase.table("escalations").select("phone, escalated_at, last_admin_reply_at").eq("escalated", True).execute()
    now = datetime.now(timezone.utc)
    cutoff = timedelta(minutes=minutes)
    stale = []
    for row in result.data:
        last_reply_str = row.get("last_admin_reply_at")
        escalated_at_str = row.get("escalated_at")
        if last_reply_str:
            ts = datetime.fromisoformat(last_reply_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if now - ts > cutoff:
                stale.append(row["phone"])
        elif escalated_at_str:
            ts = datetime.fromisoformat(escalated_at_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if now - ts > cutoff:
                stale.append(row["phone"])
    return stale


@observe
async def add_message(phone: str, sender: str, text: str):
    _supabase.table("conversations").insert({"phone": phone, "sender": sender, "text": text}).execute()
    msg = {"phone": phone, "sender": sender, "text": text}
    for queue in listeners:
        await queue.put({"type": "message", **msg})


@observe
def create_order(phone: str, items: list):
    count_result = _supabase.table("orders").select("order_id", count="exact").execute()
    order_counter = (count_result.count or 0) + 1
    order_id = f"ORD-{order_counter:04d}"
    total = round(sum(item["price"] * item["qty"] for item in items), 2)
    order = {
        "order_id": order_id,
        "phone": phone,
        "items": items,
        "total": total,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _supabase.table("orders").insert(order).execute()
    return order


@observe
def confirm_order(order_id: str):
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        return None
    order = result.data[0]
    if order["status"] != "pending":
        return order
    _supabase.table("orders").update({"status": "confirmed"}).eq("order_id", order_id).execute()
    return {**order, "status": "confirmed"}


@observe
def get_order_status(order_id: str):
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    return result.data[0] if result.data else None


@observe
def get_orders_by_phone(phone: str):
    result = _supabase.table("orders").select("*").eq("phone", phone).execute()
    return result.data


@observe
def get_editable_order_by_phone(phone: str):
    result = _supabase.table("orders").select("*").eq("phone", phone).in_("status", ["pending", "confirmed"]).order("created_at", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


@observe
def get_active_order_by_phone(phone: str):
    result = _supabase.table("orders").select("*").eq("phone", phone).not_.in_("status", ["on_the_way", "delivered"]).order("created_at", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


@observe
def add_items_to_order(order_id: str, new_items: list):
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        return None
    order = result.data[0]
    merged = {item["name"]: item for item in order["items"]}
    for item in new_items:
        if item["name"] in merged:
            merged[item["name"]]["qty"] += item["qty"]
        else:
            merged[item["name"]] = item
    updated_items = list(merged.values())
    updated_total = round(sum(i["price"] * i["qty"] for i in updated_items), 2)
    _supabase.table("orders").update({"items": updated_items, "total": updated_total}).eq("order_id", order_id).execute()
    return {**order, "items": updated_items, "total": updated_total}


@observe
def edit_order(order_id: str, operations: list):
    """Apply a list of operations to an order's items.

    Each operation: {"action": "add"|"remove"|"set_qty", "name": str, "qty": int, "price": float}
    """
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        return None
    order = result.data[0]
    items = {item["name"]: dict(item) for item in order["items"]}
    for op in operations:
        action = op["action"]
        name = op["name"]
        if action == "remove":
            items.pop(name, None)
        elif action == "add":
            if name in items:
                items[name]["qty"] += op["qty"]
            else:
                items[name] = {"name": name, "qty": op["qty"], "price": op["price"]}
        elif action == "set_qty":
            if name in items:
                items[name]["qty"] = op["qty"]
    updated_items = list(items.values())
    updated_total = round(sum(i["price"] * i["qty"] for i in updated_items), 2)
    _supabase.table("orders").update({"items": updated_items, "total": updated_total}).eq("order_id", order_id).execute()
    return {**order, "items": updated_items, "total": updated_total}


@observe
def update_order_status(order_id: str, status: str):
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        return None
    _supabase.table("orders").update({"status": status}).eq("order_id", order_id).execute()
    return {**result.data[0], "status": status}


@observe
def get_client(phone: str):
    result = _supabase.table("clients").select("*").eq("phone", phone).execute()
    return result.data[0] if result.data else None


@observe
def save_client(phone: str, name: str, address: str) -> None:
    _supabase.table("clients").upsert({"phone": phone, "name": name, "address": address}).execute()

