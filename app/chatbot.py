import json
import os
from dataclasses import dataclass, field
from typing import Any

import openai
from openai import OpenAI
from mcp_client import call_tool

MODEL = "gpt-4o-mini"
OPENROUTER_MODEL = "openai/gpt-4o-mini"

# Errors that warrant falling back to OpenRouter
_FALLBACK_ERRORS = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


def _openai_client() -> tuple[OpenAI, str]:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"]), MODEL


def _openrouter_client() -> tuple[OpenAI, str]:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
    ), OPENROUTER_MODEL

SYSTEM_PROMPT = """You are a friendly and professional customer support agent for Meridian Electronics, \
a company that sells computer products including monitors, keyboards, printers, networking gear, and accessories.

You can help customers with:
- Browsing and searching products (no login required)
- Checking product availability and pricing (no login required)
- Viewing order history (requires authentication)
- Placing new orders (requires authentication)

Authentication rules:
- Always ask for the customer's email and 4-digit PIN before accessing order history or placing orders.
- Once authenticated, use the customer_id from the session for all order-related calls — never ask again.
- If verify_customer_pin returns an error, politely ask them to re-check their credentials.

Ordering rules:
- Always confirm product details and total price with the customer before calling create_order.
- When creating an order, use the exact SKU, current unit_price from get_product, and currency "USD".
- If stock is insufficient, tell the customer and suggest alternatives.

Communication style:
- Be concise, warm, and professional.
- Format product listings clearly: name, SKU, price, and stock.
- Format order summaries with line items and totals.

{session_context}"""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search products by keyword. Use when a customer describes what they want.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term e.g. '27-inch monitor'"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": "List products by category. Categories: Monitors, Keyboards, Printers, Networking, Accessories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "is_active": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "Get full details for a product by SKU including current price and stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "Product SKU e.g. MON-0056"}
                },
                "required": ["sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_customer_pin",
            "description": "Authenticate a customer with email and 4-digit PIN. Required before any order operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "pin": {"type": "string", "description": "4-digit PIN"},
                },
                "required": ["email", "pin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_orders",
            "description": "List orders for the authenticated customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "status": {"type": "string", "description": "draft|submitted|approved|fulfilled|cancelled"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Get full details of a specific order including line items.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Place a new order. Confirm details with the customer first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sku": {"type": "string"},
                                "quantity": {"type": "integer"},
                                "unit_price": {"type": "string"},
                                "currency": {"type": "string", "default": "USD"},
                            },
                            "required": ["sku", "quantity", "unit_price"],
                        },
                    },
                },
                "required": ["customer_id", "items"],
            },
        },
    },
]


@dataclass
class Session:
    customer_id: str | None = None
    customer_name: str | None = None
    messages: list[dict] = field(default_factory=list)


def _session_context(session: Session) -> str:
    if session.customer_id:
        return f"\nCurrent session: Customer authenticated — ID: {session.customer_id}, Name: {session.customer_name or 'unknown'}."
    return "\nCurrent session: No customer authenticated yet."


def _extract_field(text: str, *labels: str) -> str | None:
    for line in text.splitlines():
        for label in labels:
            if label.lower() in line.lower():
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    return None


def _complete(client: OpenAI, model: str, system: str, messages: list) -> Any:
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, *messages],
        tools=TOOLS,
        tool_choice="auto",
    )


def chat(user_message: str, session: Session) -> tuple[str, Session]:
    system = SYSTEM_PROMPT.format(session_context=_session_context(session))
    session.messages.append({"role": "user", "content": user_message})

    while True:
        try:
            client, model = _openai_client()
            response = _complete(client, model, system, session.messages)
        except _FALLBACK_ERRORS:
            client, model = _openrouter_client()
            response = _complete(client, model, system, session.messages)

        msg = response.choices[0].message

        if not msg.tool_calls:
            session.messages.append({"role": "assistant", "content": msg.content})
            return msg.content, session

        # Assistant message with tool calls
        session.messages.append(msg)

        for tc in msg.tool_calls:
            arguments = json.loads(tc.function.arguments)
            result = call_tool(tc.function.name, arguments)

            if tc.function.name == "verify_customer_pin" and not result.startswith("Error"):
                session.customer_id = _extract_field(result, "ID", "customer id") or session.customer_id
                session.customer_name = _extract_field(result, "Name") or session.customer_name
                system = SYSTEM_PROMPT.format(session_context=_session_context(session))

            session.messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
