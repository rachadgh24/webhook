import os
import asyncio
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

listeners = []
MAX_DELIVERY_LOG = 50


def log_delivery(stage: str, phone: str | None = None, ok: bool = True, status_code: int | None = None, detail: str = ""):
    _supabase.table("delivery_log").insert({
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage": stage,
        "phone": phone,
        "ok": ok,
        "status_code": status_code,
        "detail": detail,
    }).execute()


def get_delivery_log():
    result = _supabase.table("delivery_log").select("*").order("id", desc=True).limit(MAX_DELIVERY_LOG).execute()
    return result.data


def get_conversation(phone: str):
    result = _supabase.table("conversations").select("sender, text").eq("phone", phone).order("id").execute()
    return [{"phone": phone, "sender": r["sender"], "text": r["text"]} for r in result.data]


def get_all_conversations() -> dict:
    result = _supabase.table("conversations").select("phone, sender, text").order("id").execute()
    grouped: dict = {}
    for r in result.data:
        grouped.setdefault(r["phone"], []).append({"phone": r["phone"], "sender": r["sender"], "text": r["text"]})
    return grouped


def get_escalated_phones() -> list:
    result = _supabase.table("escalations").select("phone").eq("escalated", True).execute()
    return [r["phone"] for r in result.data]


def get_all_orders() -> list:
    result = _supabase.table("orders").select("*").execute()
    return result.data


def load_chat_history(phone: str) -> list:
    result = _supabase.table("chat_histories").select("messages").eq("phone", phone).execute()
    return result.data[0]["messages"] if result.data else []


def save_chat_history(phone: str, messages: list) -> None:
    _supabase.table("chat_histories").upsert({"phone": phone, "messages": messages}).execute()


def is_escalated(phone: str) -> bool:
    result = _supabase.table("escalations").select("escalated").eq("phone", phone).execute()
    return bool(result.data and result.data[0]["escalated"])


async def set_escalation(phone: str, escalated: bool):
    _supabase.table("escalations").upsert({"phone": phone, "escalated": escalated}).execute()
    event = {"type": "escalation", "phone": phone, "escalated": escalated}
    for queue in listeners:
        await queue.put(event)


async def add_message(phone: str, sender: str, text: str):
    _supabase.table("conversations").insert({"phone": phone, "sender": sender, "text": text}).execute()
    msg = {"phone": phone, "sender": sender, "text": text}
    for queue in listeners:
        await queue.put({"type": "message", **msg})


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
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    _supabase.table("orders").insert(order).execute()
    return order


def confirm_order(order_id: str):
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        return None
    order = result.data[0]
    if order["status"] != "pending":
        return order
    _supabase.table("orders").update({"status": "confirmed"}).eq("order_id", order_id).execute()
    return {**order, "status": "confirmed"}


def get_order_status(order_id: str):
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    return result.data[0] if result.data else None


def get_orders_by_phone(phone: str):
    result = _supabase.table("orders").select("*").eq("phone", phone).execute()
    return result.data


def update_order_status(order_id: str, status: str):
    result = _supabase.table("orders").select("*").eq("order_id", order_id).execute()
    if not result.data:
        return None
    _supabase.table("orders").update({"status": status}).eq("order_id", order_id).execute()
    return {**result.data[0], "status": status}
