import asyncio
from datetime import datetime

conversations = {}
listeners = []
orders = {}
order_counter = 0


def get_conversation(phone: str):
    if phone not in conversations:
        conversations[phone] = []
    return conversations[phone]


async def add_message(phone: str, sender: str, text: str):
    msg = {"phone": phone, "sender": sender, "text": text}
    get_conversation(phone).append(msg)
    for queue in listeners:
        await queue.put(msg)


def create_order(phone: str, items: list):
    global order_counter
    order_counter += 1
    order_id = f"ORD-{order_counter:04d}"
    total = sum(item["price"] * item["qty"] for item in items)
    order = {
        "order_id": order_id,
        "phone": phone,
        "items": items,
        "total": round(total, 2),
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    orders[order_id] = order
    if phone not in orders:
        pass
    return order


def confirm_order(order_id: str):
    order = orders.get(order_id)
    if not order:
        return None
    if order["status"] != "pending":
        return order
    order["status"] = "confirmed"
    return order


def get_order_status(order_id: str):
    return orders.get(order_id)


def get_orders_by_phone(phone: str):
    return [o for o in orders.values() if o["phone"] == phone]


def update_order_status(order_id: str, status: str):
    order = orders.get(order_id)
    if not order:
        return None
    order["status"] = status
    return order
