import requests

MCP_URL = "https://order-mcp-74afyau24q-uc.a.run.app/mcp"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def call_tool(tool_name: str, arguments: dict) -> str:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": 1,
    }
    try:
        resp = requests.post(MCP_URL, json=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            return f"Error: {data['error'].get('message', 'Unknown MCP error')}"

        content = data.get("result", {}).get("content", [])
        return "\n".join(c["text"] for c in content if c.get("type") == "text")

    except requests.exceptions.Timeout:
        return "Error: Request to backend timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return f"Error: Could not reach backend service — {e}"
