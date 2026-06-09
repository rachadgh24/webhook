import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from dotenv import load_dotenv
from langfuse import observe

load_dotenv()

logger = logging.getLogger(__name__)

_supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

listeners = []
MAX_DELIVERY_LOG = 50


@observe
async def log_delivery(stage: str, phone: str | None = None, ok: bool = True, status_code: int | None = None, detail: str = ""):
    logger.info("log_delivery start stage=%s phone=%s ok=%s", stage, phone, ok)
    row = {
        "at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "phone": phone,
        "ok": ok,
        "status_code": status_code,
        "detail": detail,
    }
    await asyncio.to_thread(_supabase.table("delivery_log").insert(row).execute)
    logger.info("log_delivery done stage=%s", stage)


@observe
def get_delivery_log():
    logger.info("get_delivery_log start")
    result = _supabase.table("delivery_log").select("*").order("id", desc=True).limit(MAX_DELIVERY_LOG).execute()
    logger.info("get_delivery_log done rows=%d", len(result.data))
    return result.data


@observe
def get_conversation(phone: str):
    logger.info("get_conversation start phone=%s", phone)
    result = _supabase.table("conversations").select("sender, text").eq("phone", phone).order("id").execute()
    logger.info("get_conversation done phone=%s rows=%d", phone, len(result.data))
    return [{"phone": phone, "sender": r["sender"], "text": r["text"]} for r in result.data]


@observe
def get_all_conversations() -> dict:
    logger.info("get_all_conversations start")
    result = _supabase.table("conversations").select("phone, sender, text").order("id").execute()
    grouped: dict = {}
    for r in result.data:
        grouped.setdefault(r["phone"], []).append({"phone": r["phone"], "sender": r["sender"], "text": r["text"]})
    logger.info("get_all_conversations done phones=%d", len(grouped))
    return grouped


@observe
def get_escalated_phones() -> list:
    logger.info("get_escalated_phones start")
    result = _supabase.table("escalations").select("phone").eq("escalated", True).execute()
    logger.info("get_escalated_phones done count=%d", len(result.data))
    return [r["phone"] for r in result.data]


@observe
def load_menu() -> dict:
    logger.info("load_menu start")
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
    logger.info("load_menu done categories=%d", len(menu))
    return menu


@observe
def get_all_orders() -> list:
    logger.info("get_all_orders start")
    result = _supabase.table("orders").select("*").eq("hidden", False).execute()
    logger.info("get_all_orders done count=%d", len(result.data))
    return result.data


@observe
def hide_order(order_id: str):
    logger.info("hide_order start order_id=%s", order_id)
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        logger.info("hide_order done order_id=%s not_found", order_id)
        return None
    _supabase.table("orders").update({"hidden": True}).eq("order_id", order_id).execute()
    logger.info("hide_order done order_id=%s", order_id)
    return {"ok": True}


HISTORY_WINDOW_HOURS = 12


@observe
def load_chat_history(phone: str) -> list:
    logger.info("load_chat_history start phone=%s", phone)
    result = _supabase.table("chat_histories").select("messages").eq("phone", phone).execute()
    if not result.data:
        logger.info("load_chat_history done phone=%s no_history", phone)
        return []
    messages = result.data[0]["messages"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HISTORY_WINDOW_HOURS)
    filtered = []
    for msg in messages:
        if msg.get("role") == "system" and not msg.get("subtype"):
            # Static system messages (SYSTEM_PROMPT, phone context) — always keep
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
    logger.info("load_chat_history done phone=%s messages=%d", phone, len(filtered))
    return filtered


@observe
def save_chat_history(phone: str, messages: list) -> None:
    logger.info("save_chat_history start phone=%s messages=%d", phone, len(messages))
    now_iso = datetime.now(timezone.utc).isoformat()
    for msg in messages:
        if "ts" not in msg and (msg.get("role") != "system" or msg.get("subtype")):
            msg["ts"] = now_iso
    _supabase.table("chat_histories").upsert({"phone": phone, "messages": messages}).execute()
    logger.info("save_chat_history done phone=%s", phone)


@observe
def append_to_chat_history(phone: str, message: dict) -> None:
    logger.info("append_to_chat_history start phone=%s", phone)
    history = load_chat_history(phone)
    if not history:
        logger.info("append_to_chat_history done phone=%s no_history", phone)
        return
    history.append(message)
    save_chat_history(phone, history)
    logger.info("append_to_chat_history done phone=%s", phone)


@observe
def is_escalated(phone: str) -> bool:
    logger.info("is_escalated start phone=%s", phone)
    result = _supabase.table("escalations").select("escalated").eq("phone", phone).execute()
    escalated = bool(result.data and result.data[0]["escalated"])
    logger.info("is_escalated done phone=%s escalated=%s", phone, escalated)
    return escalated


@observe
async def set_escalation(phone: str, escalated: bool):
    logger.info("set_escalation start phone=%s escalated=%s", phone, escalated)
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
    logger.info("set_escalation done phone=%s", phone)


@observe
def update_last_admin_reply(phone: str) -> None:
    logger.info("update_last_admin_reply start phone=%s", phone)
    now_iso = datetime.now(timezone.utc).isoformat()
    _supabase.table("escalations").update({"last_admin_reply_at": now_iso}).eq("phone", phone).execute()
    logger.info("update_last_admin_reply done phone=%s", phone)


@observe
def get_stale_escalations(minutes: int = 15) -> list:
    logger.info("get_stale_escalations start minutes=%d", minutes)
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
    logger.info("get_stale_escalations done stale=%d", len(stale))
    return stale


@observe
async def add_message(phone: str, sender: str, text: str):
    logger.info("add_message start phone=%s sender=%s", phone, sender)
    _supabase.table("conversations").insert({"phone": phone, "sender": sender, "text": text}).execute()
    msg = {"phone": phone, "sender": sender, "text": text}
    for queue in listeners:
        await queue.put({"type": "message", **msg})
    logger.info("add_message done phone=%s", phone)


@observe
def create_order(phone: str, items: list):
    logger.info("create_order start phone=%s items=%d", phone, len(items))
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
    logger.info("create_order done phone=%s order_id=%s total=%s", phone, order_id, total)
    return order


@observe
def confirm_order(order_id: str):
    logger.info("confirm_order start order_id=%s", order_id)
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        logger.info("confirm_order done order_id=%s not_found", order_id)
        return None
    order = result.data[0]
    if order["status"] != "pending":
        logger.info("confirm_order done order_id=%s status=%s not_pending", order_id, order["status"])
        return order
    _supabase.table("orders").update({"status": "confirmed"}).eq("order_id", order_id).execute()
    logger.info("confirm_order done order_id=%s confirmed", order_id)
    return {**order, "status": "confirmed"}


@observe
def get_order_status(order_id: str):
    logger.info("get_order_status start order_id=%s", order_id)
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    found = result.data[0] if result.data else None
    logger.info("get_order_status done order_id=%s found=%s", order_id, found is not None)
    return found


@observe
def get_orders_by_phone(phone: str):
    logger.info("get_orders_by_phone start phone=%s", phone)
    result = _supabase.table("orders").select("*").eq("phone", phone).execute()
    logger.info("get_orders_by_phone done phone=%s count=%d", phone, len(result.data))
    return result.data


@observe
def get_editable_order_by_phone(phone: str):
    logger.info("get_editable_order_by_phone start phone=%s", phone)
    result = _supabase.table("orders").select("*").eq("phone", phone).in_("status", ["pending", "confirmed"]).order("created_at", desc=True).limit(1).execute()
    found = result.data[0] if result.data else None
    logger.info("get_editable_order_by_phone done phone=%s found=%s", phone, found is not None)
    return found


@observe
def get_active_order_by_phone(phone: str):
    logger.info("get_active_order_by_phone start phone=%s", phone)
    result = _supabase.table("orders").select("*").eq("phone", phone).not_.in_("status", ["on_the_way", "delivered"]).order("created_at", desc=True).limit(1).execute()
    found = result.data[0] if result.data else None
    logger.info("get_active_order_by_phone done phone=%s found=%s", phone, found is not None)
    return found


@observe
def add_items_to_order(order_id: str, new_items: list):
    logger.info("add_items_to_order start order_id=%s new_items=%d", order_id, len(new_items))
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        logger.info("add_items_to_order done order_id=%s not_found", order_id)
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
    logger.info("add_items_to_order done order_id=%s total=%s", order_id, updated_total)
    return {**order, "items": updated_items, "total": updated_total}


@observe
def edit_order(order_id: str, operations: list):
    """Apply a list of operations to an order's items.

    Each operation: {"action": "add"|"remove"|"set_qty", "name": str, "qty": int, "price": float}
    """
    logger.info("edit_order start order_id=%s operations=%d", order_id, len(operations))
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        logger.info("edit_order done order_id=%s not_found", order_id)
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
    logger.info("edit_order done order_id=%s total=%s", order_id, updated_total)
    return {**order, "items": updated_items, "total": updated_total}


@observe
def update_order_status(order_id: str, status: str):
    logger.info("update_order_status start order_id=%s status=%s", order_id, status)
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        logger.info("update_order_status done order_id=%s not_found", order_id)
        return None
    _supabase.table("orders").update({"status": status}).eq("order_id", order_id).execute()
    logger.info("update_order_status done order_id=%s status=%s", order_id, status)
    return {**result.data[0], "status": status}


@observe
def get_client(phone: str):
    logger.info("get_client start phone=%s", phone)
    result = _supabase.table("clients").select("*").eq("phone", phone).execute()
    found = result.data[0] if result.data else None
    logger.info("get_client done phone=%s found=%s", phone, found is not None)
    return found


@observe
def save_client(phone: str, name: str, address: str) -> None:
    logger.info("save_client start phone=%s", phone)
    _supabase.table("clients").upsert({"phone": phone, "name": name, "address": address}).execute()
    logger.info("save_client done phone=%s", phone)
