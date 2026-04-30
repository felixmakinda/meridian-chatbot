# Meridian Electronics — Customer Support Chatbot

## Business Problem
Meridian Electronics' support team handles all customer inquiries manually via phone and email.
This prototype automates the four most common workflows — product browsing, stock checks,
order history, and order placement — using an AI chatbot connected to existing backend systems
via MCP, with no direct database access.

---

## System Architecture

```mermaid
flowchart TD
    Customer([Customer]) -->|HTTPS| CF[CloudFront CDN]
    CF -->|serves static files| S3[S3 Bucket\nNext.js static export]

    Customer -->|POST /chat| AR[AWS AppRunner\nFastAPI API]

    AR -->|tool calls| CB[chatbot.py\nOpenAI tool loop]
    CB -->|primary| OAI[OpenAI\ngpt-4o-mini]
    CB -->|fallback on error| OR[OpenRouter\ngpt-4o-mini]
    OAI & OR -->|tool_call| MC[mcp_client.py]
    MC -->|JSON-RPC POST| MCP[MCP Server\norder-mcp on Cloud Run]
    MCP -->|tool result| MC
```

---

## Component Breakdown

```mermaid
flowchart LR
    subgraph Frontend["frontend/  —  Next.js + pnpm"]
        P[page.tsx\nChat UI + session state]
        L[layout.tsx]
        G[globals.css\nTailwind CSS]
    end

    subgraph Backend["app/  —  FastAPI + uv"]
        M[main.py\nREST API + in-memory session store]
        C[chatbot.py\nOpenAI tool loop + OpenRouter fallback]
        MC[mcp_client.py\nHTTP JSON-RPC client]
    end

    subgraph AWS
        CF[CloudFront]
        S3[S3]
        AR[AppRunner]
        ECR[ECR]
    end

    subgraph External
        OAI[OpenAI API]
        OR[OpenRouter API]
        MCP[order-mcp\nCloud Run]
    end

    P --> M
    M --> C
    C --> OAI
    C --> OR
    C --> MC
    MC --> MCP

    Frontend -->|static export| S3
    S3 --> CF
    Backend -->|Docker image| ECR
    ECR --> AR
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
    note over Bot: customer_id reused for all<br/>subsequent requests — no re-auth
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
    C->>Bot: "Yes, confirm"
    Bot->>MCP: create_order(customer_id, items)
    MCP-->>Bot: order confirmation + order ID
    Bot->>C: order confirmed
```

---

## LLM Fallback Strategy

```mermaid
flowchart LR
    Req[Chat Request] --> OAI[OpenAI\ngpt-4o-mini]
    OAI -->|success| Res[Response]
    OAI -->|RateLimitError\nTimeoutError\nConnectionError\n5xx| OR[OpenRouter\ngpt-4o-mini]
    OR --> Res
```

Same model on both providers — OpenRouter is a transparent hot-standby with no prompt or tool changes needed.

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

## CI/CD Pipeline

```mermaid
flowchart TD
    Dev[git push main] --> GHA[GitHub Actions]

    GHA --> A[Job: deploy-api]
    GHA --> B[Job: deploy-ui]

    A -->|docker build\nuv install| ECR[AWS ECR]
    ECR -->|auto-deploy| AR[AWS AppRunner]

    B -->|pnpm install\npnpm build| OUT[Next.js static export\nout/]
    OUT -->|aws s3 sync| S3[AWS S3]
    S3 -->|cache invalidation| CF[AWS CloudFront]
```

---

## Infrastructure (Terraform)

| Resource | Purpose |
|---|---|
| **ECR** | Docker image registry for the FastAPI backend |
| **AppRunner** | Serverless container runtime — auto-scales, no ALB or VPC config needed |
| **S3** | Private bucket for Next.js static files |
| **CloudFront** | CDN — serves frontend over HTTPS globally, SPA routing via custom error pages |
| **IAM** | AppRunner access role scoped to ECR pull only |
| **CloudWatch** | Container logs with 7-day retention |

## Package Managers

| Layer | Tool | Why |
|---|---|---|
| Python backend | `uv` | Fast dependency install in Docker |
| Node.js frontend | `pnpm` | Fast, strict, deterministic lockfile |
