# Meridian Electronics — Customer Support Chatbot

## Business Problem
Meridian Electronics' support team handles all customer inquiries manually via phone and email.
This prototype automates the four most common workflows using an AI chatbot connected to existing
backend systems via MCP — no direct database access required.

---

## High-Level Architecture

```mermaid
flowchart TD
    Customer([Customer]) -->|chat message| UI[Next.js Chat UI\nfrontend/]
    UI -->|POST /chat + session_id| API[FastAPI Backend\napp/main.py]
    API -->|user message + history| Engine[Chat Engine\napp/chatbot.py]
    Engine -->|messages + tools| LLM{LLM}
    LLM -->|primary| OAI[OpenAI\ngpt-4o-mini]
    LLM -->|fallback on error| OR[OpenRouter\ngpt-4o-mini]
    OAI -->|tool_call| Engine
    OR -->|tool_call| Engine
    Engine -->|JSON-RPC POST| MCP[MCP Server\norder-mcp on Cloud Run]
    MCP -->|tool result| Engine
    Engine -->|final response| API
    API -->|reply + session_id| UI
```

---

## Component Breakdown

```mermaid
flowchart LR
    subgraph Frontend["frontend/ — Next.js"]
        P[page.tsx\nChat UI + session state]
    end

    subgraph Backend["app/ — FastAPI"]
        M[main.py\nREST API + session store]
        C[chatbot.py\nOpenAI tool loop\n+ OpenRouter fallback]
        MC[mcp_client.py\nHTTP JSON-RPC client]
    end

    subgraph External
        OAI[OpenAI API\ngpt-4o-mini]
        OR[OpenRouter API\nopenai/gpt-4o-mini]
        MCP[MCP Server\norder-mcp]
    end

    P -->|POST /chat| M
    M --> C
    C -->|primary| OAI
    C -->|fallback| OR
    C --> MC
    MC -->|POST /mcp| MCP
```

---

## Authentication Flow

```mermaid
sequenceDiagram
    participant C as Customer
    participant Bot as Chatbot
    participant MCP as MCP Server

    C->>Bot: "Show me my orders"
    Bot->>C: "Please provide your email and 4-digit PIN"
    C->>Bot: email + PIN
    Bot->>MCP: verify_customer_pin(email, pin)
    MCP-->>Bot: customer details + customer_id
    Bot->>Bot: stores customer_id in session
    Bot->>MCP: list_orders(customer_id)
    MCP-->>Bot: order list
    Bot->>C: displays order history
    note over Bot: customer_id reused for\nall subsequent requests
```

---

## Order Placement Flow

```mermaid
sequenceDiagram
    participant C as Customer
    participant Bot as Chatbot
    participant MCP as MCP Server

    C->>Bot: "I want to buy a 27-inch monitor"
    Bot->>MCP: search_products("27-inch monitor")
    MCP-->>Bot: matching products with prices + stock
    Bot->>C: shows options
    C->>Bot: "I'll take MON-0056, qty 1"
    Bot->>MCP: get_product("MON-0056")
    MCP-->>Bot: confirmed price $484.14, stock 32
    Bot->>C: "Confirm order for $484.14?"
    C->>Bot: "Yes"
    Bot->>MCP: create_order(customer_id, items)
    MCP-->>Bot: order confirmation + order ID
    Bot->>C: order confirmed
```

---

## LLM Fallback Strategy

```mermaid
flowchart LR
    Req[API Request] --> OAI[Try OpenAI\ngpt-4o-mini]
    OAI -->|success| Resp[Response]
    OAI -->|RateLimitError\nTimeoutError\nConnectionError\n5xx| OR[Retry OpenRouter\nopenai/gpt-4o-mini]
    OR --> Resp
```

Both providers serve the same `gpt-4o-mini` model. OpenRouter acts as a transparent hot-standby — no prompt or tool definition changes needed.

---

## MCP Tools

| Tool | Auth Required | Purpose |
|------|:---:|---------|
| `search_products` | No | Find products by keyword |
| `list_products` | No | Browse by category |
| `get_product` | No | Price and stock by SKU |
| `verify_customer_pin` | — | Authenticate with email + PIN |
| `get_customer` | Yes | Customer profile |
| `list_orders` | Yes | Order history |
| `get_order` | Yes | Order line items |
| `create_order` | Yes | Place a new order |

---

## CI/CD & Deployment

```mermaid
flowchart TD
    Dev[git push main] --> GHA[GitHub Actions]

    GHA -->|job: deploy-api\ndocker build uv| ECR_API[ECR\nmeridian-chatbot]
    GHA -->|job: deploy-ui\ndocker build pnpm| ECR_UI[ECR\nmeridian-chatbot-ui]

    ECR_API --> ECS_API[ECS Fargate\nFastAPI — port 8000]
    ECR_UI  --> ECS_UI[ECS Fargate\nNext.js — port 3000]

    ECS_API --> ALB[Application Load Balancer]
    ECS_UI  --> ALB

    ALB --> Internet([Public URL])
```

### Package managers
| Layer | Tool |
|---|---|
| Python backend | `uv` — fast dependency install in Docker |
| Node.js frontend | `pnpm` — fast, strict, deterministic |

### GitHub Actions secrets required
| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | aiengineer IAM key |
| `AWS_SECRET_ACCESS_KEY` | aiengineer IAM secret |
| `API_URL` | ALB DNS of the backend e.g. `http://meridian-chatbot-alb-xxx.eu-west-1.elb.amazonaws.com` |

### Infrastructure (Terraform)
| Resource | Purpose |
|---|---|
| ECR (×2) | Docker image registries for API and UI |
| ECS Fargate (×2) | Serverless containers — API and UI services |
| ALB | Single public endpoint, routes to both services |
| IAM | Task execution role + task role (Bedrock-style scoping) |
| CloudWatch | Container logs, 7-day retention |
