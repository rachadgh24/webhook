import json as _json
from store import create_order as _create_order, confirm_order as _confirm_order
from store import get_order_status as _get_order_status, get_orders_by_phone as _get_orders_by_phone

MENU_PHOTO_MEDIA_ID = "2017954492405428"

MENU = {
    "starters": [
        {"name": "Bruschetta", "price": 6.50, "description": "Toasted bread with tomatoes, garlic, and basil"},
        {"name": "Soup of the Day", "price": 5.00, "description": "Ask for today's selection"},
        {"name": "Caesar Salad", "price": 7.50, "description": "Romaine lettuce, croutons, parmesan, caesar dressing"},
    ],
    "mains": [
        {"name": "Grilled Chicken", "price": 14.00, "description": "Served with roasted vegetables and rice"},
        {"name": "Beef Burger", "price": 12.50, "description": "Angus beef patty, cheddar, lettuce, tomato, fries"},
        {"name": "Margherita Pizza", "price": 11.00, "description": "Tomato sauce, mozzarella, fresh basil"},
        {"name": "Grilled Salmon", "price": 16.50, "description": "Atlantic salmon with lemon butter sauce and greens"},
        {"name": "Pasta Carbonara", "price": 13.00, "description": "Spaghetti, pancetta, egg, parmesan, black pepper"},
    ],
    "desserts": [
        {"name": "Tiramisu", "price": 7.00, "description": "Classic Italian coffee-flavoured dessert"},
        {"name": "Chocolate Cake", "price": 6.50, "description": "Rich dark chocolate layered cake"},
        {"name": "Ice Cream", "price": 4.50, "description": "Three scoops, choice of vanilla, chocolate, or strawberry"},
    ],
    "drinks": [
        {"name": "Water", "price": 1.50, "description": "Still or sparkling"},
        {"name": "Soft Drink", "price": 2.50, "description": "Coca-Cola, Fanta, Sprite"},
        {"name": "Fresh Juice", "price": 4.00, "description": "Orange, apple, or mango"},
        {"name": "Coffee", "price": 3.00, "description": "Espresso, americano, or latte"},
    ],
}

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

def get_full_menu():
    lines = []
    for category, items in MENU.items():
        lines.append(f"\n{category.upper()}:")
        for item in items:
            lines.append(f"  - {item['name']}: ${item['price']:.2f} — {item['description']}")
    return "\n".join(lines)


def get_category_menu(category: str):
    cat = category.lower()
    if cat not in MENU:
        return f"Category '{category}' not found. Available categories: {', '.join(MENU.keys())}"
    lines = [f"{cat.upper()}:"]
    for item in MENU[cat]:
        lines.append(f"  - {item['name']}: ${item['price']:.2f} — {item['description']}")
    return "\n".join(lines)


def check_price(item_name: str):
    query = item_name.lower()
    for items in MENU.values():
        for item in items:
            name = item["name"].lower()
            if name == query or name in query or query in name:
                return f"{item['name']}: ${item['price']:.2f}"
    return f"Item '{item_name}' not found on the menu. Use get_full_menu to see available items."


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


def place_order(phone: str, items_json: str):
    items_raw = _json.loads(items_json) if isinstance(items_json, str) else items_json
    resolved_items = []
    for entry in items_raw:
        name = entry.get("name", "")
        qty = entry.get("qty", 1)
        query = name.lower()
        found = False
        for menu_items in MENU.values():
            for item in menu_items:
                menu_name = item["name"].lower()
                if menu_name == query or menu_name in query or query in menu_name:
                    resolved_items.append({"name": item["name"], "qty": qty, "price": item["price"]})
                    found = True
                    break
            if found:
                break
        if not found:
            return f"Item '{name}' not found on the menu. Please check the menu and try again."

    order = _create_order(phone, resolved_items)
    lines = [f"Order {order['order_id']} created:"]
    for item in order["items"]:
        lines.append(f"  - {item['name']} x{item['qty']} = ${item['price'] * item['qty']:.2f}")
    lines.append(f"Total: ${order['total']:.2f}")
    lines.append(f"Status: {order['status']}")
    lines.append("Ask the client to confirm the order.")
    return "\n".join(lines)


def confirm_client_order(order_id: str):
    order = _confirm_order(order_id)
    if not order:
        return f"Order {order_id} not found."
    if order["status"] == "confirmed":
        return f"Order {order_id} is confirmed. Total: ${order['total']:.2f}. It will be prepared shortly."
    return f"Order {order_id} cannot be confirmed. Current status: {order['status']}."


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
                    "items": {"type": "string", "description": "JSON array of items, e.g. [{\"name\": \"Grilled Salmon\", \"qty\": 2}, {\"name\": \"Water\", \"qty\": 1}]"},
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
]
