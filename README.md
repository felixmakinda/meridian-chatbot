# Meridian Electronics — Customer Support Chatbot

An AI-powered customer support chatbot for Meridian Electronics, built with FastAPI, Next.js, and OpenAI gpt-4o-mini. The chatbot automates the four most common support workflows — product browsing, stock checks, order history, and order placement — by connecting to a backend MCP (Model Context Protocol) server via JSON-RPC.

**Live demo:** https://d2316p91bmkv0v.cloudfront.net

---

## What it does

Customers can chat naturally with the bot to:

- **Browse and search products** — by keyword or category, no login required
- **Check stock and pricing** — real-time data from the MCP server
- **View order history** — requires email + 4-digit PIN authentication
- **Place orders** — bot confirms price and stock before creating the order

---

## Architecture

```
Customer → CloudFront (Next.js UI) → AppRunner (FastAPI) → MCP Server (Cloud Run)
                                           ↓
                                    OpenAI gpt-4o-mini
                                    (OpenRouter fallback)
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, Tailwind CSS, static export |
| Backend | FastAPI, Python 3.12, `uv` |
| AI | OpenAI gpt-4o-mini with tool use |
| Fallback | OpenRouter (same model, hot-standby) |
| Data | MCP server over HTTP JSON-RPC |
| Hosting | AWS AppRunner (API) + S3 + CloudFront (UI) |
| IaC | Terraform |
| CI/CD | GitHub Actions |

---

## Project structure

```
meridian-chatbot/
├── app/                  # FastAPI backend
│   ├── main.py           # REST API + in-memory session store
│   ├── chatbot.py        # OpenAI tool loop + OpenRouter fallback
│   ├── mcp_client.py     # HTTP JSON-RPC client for the MCP server
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/             # Next.js chat UI
│   └── src/app/page.tsx  # Chat interface
├── infra/terraform/      # AWS infrastructure (ECR, AppRunner, S3, CloudFront)
└── .github/workflows/    # CI/CD — deploy API and UI on push to main
```

---

## Key design decisions

**MCP over HTTP JSON-RPC** — The chatbot connects to a pre-built MCP server via plain HTTP POST requests. No MCP SDK is used; a lightweight `mcp_client.py` handles the protocol directly, keeping dependencies minimal.

**OpenAI tool use loop** — The bot runs an agentic loop: it receives a user message, decides which MCP tools to call, executes them, and continues until it has a final answer. Tools are defined in OpenAI's function-calling format.

**Session state in memory** — Each conversation is tracked server-side by a `session_id`. The session stores the authenticated `customer_id` and message history. Once a customer authenticates, the bot never asks again within the same session.

**OpenRouter as hot-standby** — If OpenAI returns a rate limit, timeout, or server error, the same request is retried against OpenRouter with no prompt or tool changes. Both providers run the same model.

**Static frontend on S3 + CloudFront** — The Next.js app is exported as static HTML/JS and served via CloudFront. No Node.js server is needed in production.

---

## Running locally

**Backend:**
```bash
cd app
cp .env.example .env   # add OPENAI_API_KEY, OPENROUTER_API_KEY
uv pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
pnpm install
NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev
```

---

## Deployment

Infrastructure is managed with Terraform. CI/CD runs on GitHub Actions — a push to `main` builds and deploys both the API (Docker → ECR → AppRunner) and the UI (pnpm build → S3 → CloudFront invalidation).

See [ARCHITECTURE.md](ARCHITECTURE.md) for full system diagrams.
