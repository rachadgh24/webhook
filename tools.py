import json

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
    for items in MENU.values():
        for item in items:
            if item["name"].lower() == item_name.lower():
                return f"{item['name']}: ${item['price']:.2f}"
    return f"Item '{item_name}' not found on the menu."


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


# --- Map function names to handlers ---

TOOL_HANDLERS = {
    "get_full_menu": lambda args: get_full_menu(),
    "get_category_menu": lambda args: get_category_menu(args["category"]),
    "check_price": lambda args: check_price(args["item_name"]),
    "get_restaurant_hours": lambda args: get_restaurant_hours(),
    "get_restaurant_info": lambda args: get_restaurant_info(),
    "check_delivery_availability": lambda args: check_delivery_availability(),
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
]
