import re as _re
import difflib as _difflib
from langfuse import observe
from store import create_order as _create_order, confirm_order as _confirm_order
from store import get_order_status as _get_order_status, get_orders_by_phone as _get_orders_by_phone
from store import get_active_order_by_phone as _get_active_order_by_phone, add_items_to_order as _add_items_to_order
from store import get_editable_order_by_phone as _get_editable_order_by_phone, edit_order as _edit_order
from store import get_client as _get_client, save_client as _save_client
from store import load_menu as _load_menu

MENU_PHOTO_MEDIA_ID = "2017954492405428"

MENU = _load_menu()

RESTAURANT_INFO = {
    "name": "Toto's Kitchen",
    "address": "123 Main Street, Downtown",
    "hours": {
        "monday": "11:00 - 22:00",
        "tuesday": "11:00 - 22:00",
        "wednesday": "11:00 - 22:00",
        "thursday": "11:00 - 23:00",
        "friday": "11:00 - 23:00",
        "saturday": "12:00 - 23:00",
        "sunday": "12:00 - 21:00",
    },
    "phone": "+1 555-0123",
    "delivery": True,
    "delivery_fee": 3.00,
    "minimum_order": 15.00,
}


# --- Tool handler functions ---

def _find_menu_item(query: str):
    """Exact match first, then fuzzy match for typos (cutoff 0.6).
    'watter' â†’ Water (0.91), but 'sparkling water' â†’ None (0.50)."""
    q = query.strip().lower()
    flat = [item for items in MENU.values() for item in items]
    names_lower = [item["name"].lower() for item in flat]

    # Exact match
    for i, name in enumerate(names_lower):
        if name == q:
            return flat[i]

    # Fuzzy match â€” handles typos without matching unrelated strings
    matches = _difflib.get_close_matches(q, names_lower, n=1, cutoff=0.6)
    if matches:
        return flat[names_lower.index(matches[0])]

    return None


def get_full_menu():
    lines = []
    for category, items in MENU.items():
        lines.append(f"\n{category.upper()}:")
        for item in items:
            lines.append(f"  - {item['name']}: ${item['price']:.2f} â€” {item['description']}")
    return "\n".join(lines)


def get_category_menu(category: str):
    cat = category.lower()
    if cat not in MENU:
        return f"Category '{category}' not found. Available categories: {', '.join(MENU.keys())}"
    lines = [f"{cat.upper()}:"]
    for item in MENU[cat]:
        lines.append(f"  - {item['name']}: ${item['price']:.2f} â€” {item['description']}")
    return "\n".join(lines)


def check_price(item_name: str):
    item = _find_menu_item(item_name)
    if item:
        return f"{item['name']}: ${item['price']:.2f}"
    return f"'{item_name}' is not on the menu. Use get_full_menu to see all available items."


def get_restaurant_hours():
    lines = [f"{day.capitalize()}: {hours}" for day, hours in RESTAURANT_INFO["hours"].items()]
    return f"{RESTAURANT_INFO['name']} opening hours:\n" + "\n".join(lines)


def get_restaurant_info():
    info = RESTAURANT_INFO
    return (
        f"Name: {info['name']}\n"
        f"Address: {info['address']}\n"
        f"Phone: {info['phone']}\n"
        f"Delivery: {'Yes' if info['delivery'] else 'No'}\n"
        f"Delivery fee: ${info['delivery_fee']:.2f}\n"
        f"Minimum order for delivery: ${info['minimum_order']:.2f}"
    )


def check_delivery_availability():
    info = RESTAURANT_INFO
    if info["delivery"]:
        return f"Yes, we deliver. Delivery fee: ${info['delivery_fee']:.2f}. Minimum order: ${info['minimum_order']:.2f}."
    return "Sorry, we do not offer delivery at this time."


def send_menu_photo():
    return "Menu photo has been sent to the client."


@observe
def place_order(phone: str, items: list):
    resolved_items = []
    for entry in items:
        name = entry.get("name", "")
        qty = entry.get("qty", 1)
        # Handle model passing qty inside the name, e.g. "56 grilled chickens" with qty=1
        m = _re.match(r'^(\d+)\s+(.+)$', name.strip())
        if m and qty == 1:
            qty = int(m.group(1))
            name = m.group(2)
        item = _find_menu_item(name)
        if not item:
            return f"'{name}' is not on the menu. Please check the menu and try again."
        resolved_items.append({"name": item["name"], "qty": qty, "price": item["price"]})

    editable = _get_editable_order_by_phone(phone)
    if editable:
        order = _add_items_to_order(editable["order_id"], resolved_items)
        lines = [f"Items added to existing order {order['order_id']}:"]
    else:
        order = _create_order(phone, resolved_items)
        lines = [f"Order {order['order_id']} created:"]
    for item in order["items"]:
        lines.append(f"  - {item['name']} x{item['qty']} = ${item['price'] * item['qty']:.2f}")
    lines.append(f"Total: ${order['total']:.2f}")
    lines.append(f"Status: {order['status']}")
    lines.append("Ask the client to confirm the order.")
    return "\n".join(lines)


@observe
def confirm_client_order(order_id: str):
    order = _confirm_order(order_id)
    if not order:
        return f"Order {order_id} not found."
    if order["status"] == "confirmed":
        msg = f"Order {order_id} is confirmed. Total: ${order['total']:.2f}. It will be prepared shortly."
        client = _get_client(order["phone"])
        if client:
            msg += f"\nSaved delivery address: {client['address']}. Ask the client to confirm this address (e.g. 'Delivering to {client['address']}, correct?'). If they provide a different address, call save_client_info to update it."
        else:
            msg += "\nNo delivery info on file. Ask the client for their full name and delivery address in one message, then call save_client_info."
        return msg
    return f"Order {order_id} cannot be confirmed. Current status: {order['status']}."


@observe
def save_client_info(phone: str, name: str, address: str):
    _save_client(phone, name, address)
    return f"Client info saved. Name: {name}, Address: {address}."


@observe
def check_client_order_status(phone: str):
    client_orders = _get_orders_by_phone(phone)
    if not client_orders:
        return "No orders found for this client."
    latest = client_orders[-1]
    lines = [f"Order {latest['order_id']}:"]
    for item in latest["items"]:
        lines.append(f"  - {item['name']} x{item['qty']}")
    lines.append(f"Total: ${latest['total']:.2f}")
    lines.append(f"Status: {latest['status']}")
    lines.append(f"Placed at: {latest['created_at']}")
    return "\n".join(lines)


@observe
def edit_client_order(phone: str, edits: list):
    order = _get_editable_order_by_phone(phone)
    if not order:
        return "No editable order found. Orders can only be edited when they are pending or confirmed."

    operations = []
    for edit in edits:
        action = edit.get("action")
        name = edit.get("name", "")
        qty = edit.get("qty", 1)

        if action == "add":
            item = _find_menu_item(name)
            if not item:
                return f"'{name}' is not on the menu."
            operations.append({"action": "add", "name": item["name"], "qty": qty, "price": item["price"]})

        elif action in ("remove", "set_qty"):
            query = name.strip().lower()
            matched = next(
                (i["name"] for i in order["items"] if i["name"].lower() == query),
                None,
            )
            if not matched:
                return f"Item '{name}' not found in the order."
            if action == "set_qty" and qty < 1:
                return f"Quantity must be at least 1. Use 'remove' to delete an item."
            operations.append({"action": action, "name": matched, "qty": qty})

        else:
            return f"Unknown edit action '{action}'. Use 'add', 'remove', or 'set_qty'."

    updated = _edit_order(order["order_id"], operations)
    if not updated["items"]:
        return f"Order {order['order_id']} now has no items. Add something or it will remain empty."
    lines = [f"Order {updated['order_id']} updated:"]
    for item in updated["items"]:
        lines.append(f"  - {item['name']} x{item['qty']} = ${item['price'] * item['qty']:.2f}")
    lines.append(f"Total: ${updated['total']:.2f}")
    lines.append(f"Status: {updated['status']}")
    return "\n".join(lines)


# --- Map function names to handlers ---

TOOL_HANDLERS = {
    "get_full_menu": lambda args: get_full_menu(),
    "get_category_menu": lambda args: get_category_menu(args["category"]),
    "check_price": lambda args: check_price(args["item_name"]),
    "get_restaurant_hours": lambda args: get_restaurant_hours(),
    "get_restaurant_info": lambda args: get_restaurant_info(),
    "check_delivery_availability": lambda args: check_delivery_availability(),
    "send_menu_photo": lambda args: send_menu_photo(),
    "place_order": lambda args: place_order(args["phone"], args["items"]),
    "confirm_order": lambda args: confirm_client_order(args["order_id"]),
    "check_order_status": lambda args: check_client_order_status(args["phone"]),
    "edit_order": lambda args: edit_client_order(args["phone"], args["edits"]),
    "save_client_info": lambda args: save_client_info(args["phone"], args["name"], args["address"]),
}


# --- OpenAI tool definitions ---

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_full_menu",
            "description": "Returns the full restaurant menu with all categories, items, prices, and descriptions.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_menu",
            "description": "Returns menu items for a specific category (starters, mains, desserts, or drinks).",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "The menu category: starters, mains, desserts, or drinks"}
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_price",
            "description": "Returns the price of a specific menu item by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "The name of the menu item to check the price for"}
                },
                "required": ["item_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_restaurant_hours",
            "description": "Returns the restaurant opening hours for each day of the week.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_restaurant_info",
            "description": "Returns general restaurant information: name, address, phone, and delivery details.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_delivery_availability",
            "description": "Checks if the restaurant offers delivery, and returns the delivery fee and minimum order.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_menu_photo",
            "description": "Sends a photo of the restaurant menu/catalogue to the client. Use this when the client asks to see the menu, catalogue, or wants a photo of what's available.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Creates a new order for the client. Use when the client wants to order items. The order starts as 'pending' and needs client confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "The client's phone number"},
                    "items": {
                        "type": "array",
                        "description": "Items to order",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Menu item name"},
                                "qty": {"type": "integer", "description": "Quantity (defaults to 1 if omitted)"},
                            },
                            "required": ["name"],
                        },
                    },
                },
                "required": ["phone", "items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_order",
            "description": "Confirms a pending order after the client agrees. Use when the client says 'yes', 'confirm', 'go ahead', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID to confirm (e.g. ORD-0001)"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_order_status",
            "description": "Checks the status of the client's latest order. Use when the client asks about their order status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "The client's phone number"},
                },
                "required": ["phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_order",
            "description": "Edits the client's current order (pending or confirmed only). Use when the client wants to remove an item, add an item, or change an item's quantity. Not allowed once the order is preparing, on the way, or delivered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "The client's phone number"},
                    "edits": {
                        "type": "array",
                        "description": "List of edit operations to apply",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string", "enum": ["add", "remove", "set_qty"], "description": "'add' to add a new item or increase qty, 'remove' to delete an item, 'set_qty' to change an item's quantity"},
                                "name": {"type": "string", "description": "The menu item name"},
                                "qty": {"type": "integer", "description": "Quantity â€” required for 'add' and 'set_qty', ignored for 'remove'"},
                            },
                            "required": ["action", "name"],
                        },
                    },
                },
                "required": ["phone", "edits"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_client_info",
            "description": "Saves the client's full name and delivery address. Call this after collecting the client's name and address following an order confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "The client's phone number"},
                    "name": {"type": "string", "description": "The client's full name"},
                    "address": {"type": "string", "description": "The client's full delivery address"},
                },
                "required": ["phone", "name", "address"],
            },
        },
    },
]

