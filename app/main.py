"""Agent service — điểm ráp nối của cả lab (CP1, CP3, CP4).

Luồng một request tới /ask:

    client ──► verify_api_key ──► rate_limiter ──► cost_guard
                                                       │
                              store.get_history ◄──────┘
                                       │
                                    ask_llm
                                       │
                              store.append × 2 ──► cost_guard.record ──► log_event
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from utils.mock_llm import ask_llm

from .auth import verify_api_key
from .config import get_settings
from .cost_guard import CostGuard
from .lifecycle import lifecycle
from .logging_utils import log_event
from .rate_limiter import RateLimiter
from .store import ConversationStore, get_redis_client

SERVICE_NAME = "day12-agent"
SERVICE_VERSION = "1.0.0"


# ─────────────────────────────────────────────────────────────
# Providers — CHO SẴN
# Tách ra thành hàm để test có thể thay bằng Redis giả qua
# app.dependency_overrides, và để kết nối Redis chỉ tạo khi thật sự cần.
# ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_store() -> ConversationStore:
    return ConversationStore(get_redis_client())


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_redis_client(), get_settings().rate_limit_per_minute)


@lru_cache(maxsize=1)
def get_cost_guard() -> CostGuard:
    return CostGuard(get_redis_client(), get_settings().monthly_budget_usd)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """CHO SẴN — chạy lúc app khởi động và lúc tắt."""
    lifecycle.install()
    log_event("service_started", service=SERVICE_NAME, version=SERVICE_VERSION)
    try:
        yield
    finally:
        for provider in (get_store, get_rate_limiter, get_cost_guard):
            if provider.cache_info().currsize:
                provider().client.close()
            provider.cache_clear()
        log_event("service_stopped", service=SERVICE_NAME)


app = FastAPI(title="Day 12 Production Agent", version=SERVICE_VERSION, lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@app.get("/", response_class=HTMLResponse)
def home():
        return HTMLResponse(
                """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#f3f5f0">
    <title>Day 12 AI Agent</title>
    <style>
        :root {
            color-scheme: light;
            --ink: #182520;
            --muted: #68766f;
            --paper: #f3f5f0;
            --panel: #ffffff;
            --line: #dce3dc;
            --forest: #174b3d;
            --forest-dark: #10372e;
            --lime: #d9f278;
            --coral: #bd4b36;
            --user: #e8f1e9;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            color: var(--ink);
            background-color: var(--paper);
            background-image: radial-gradient(#cbd5cc 0.7px, transparent 0.7px);
            background-size: 18px 18px;
            font-family: "Segoe UI", Candara, sans-serif;
        }
        .topbar {
            min-height: 76px;
            padding: 16px clamp(20px, 5vw, 72px);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            color: #fff;
            background: var(--forest-dark);
            border-bottom: 4px solid var(--lime);
        }
        .brand { display: flex; align-items: center; gap: 12px; }
        .brand-mark {
            width: 38px;
            height: 38px;
            display: grid;
            place-items: center;
            color: var(--forest-dark);
            background: var(--lime);
            border-radius: 11px;
            font-weight: 800;
            font-size: 18px;
        }
        .brand-name { font-size: 15px; font-weight: 700; }
        .brand-subtitle { margin-top: 3px; color: #bfd0c7; font-size: 12px; }
        .online {
            display: inline-flex;
            align-items: center;
            gap: 9px;
            color: #e4eee8;
            font-size: 13px;
            white-space: nowrap;
        }
        .online-dot {
            width: 9px;
            height: 9px;
            background: var(--lime);
            border-radius: 50%;
            box-shadow: 0 0 0 4px rgb(217 242 120 / 15%);
        }
        main {
            width: min(100% - 32px, 860px);
            margin: 56px auto 48px;
        }
        .intro { margin-bottom: 28px; }
        .eyebrow {
            margin: 0 0 10px;
            color: var(--forest);
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 1.2px;
            text-transform: uppercase;
        }
        h1 {
            margin: 0;
            font-family: Georgia, "Times New Roman", serif;
            font-size: clamp(32px, 6vw, 48px);
            font-weight: 500;
            line-height: 1.08;
        }
        .lead { margin: 11px 0 0; color: var(--muted); font-size: 15px; }
        .workspace {
            overflow: hidden;
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 12px;
            box-shadow: 0 18px 55px rgb(24 37 32 / 8%);
        }
        .workspace-head {
            min-height: 54px;
            padding: 14px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--line);
        }
        .workspace-title { font-size: 13px; font-weight: 700; }
        .privacy-note { color: var(--muted); font-size: 12px; }
        .chat {
            min-height: 280px;
            max-height: 46vh;
            overflow-y: auto;
            padding: 22px clamp(16px, 4vw, 32px);
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .message { max-width: min(84%, 620px); animation: appear 180ms ease-out both; }
        .message.user { align-self: flex-end; }
        .message.agent { align-self: flex-start; }
        .message-label {
            margin: 0 0 6px 3px;
            color: var(--muted);
            font-size: 11px;
            font-weight: 700;
        }
        .bubble {
            padding: 12px 15px;
            line-height: 1.55;
            font-size: 14px;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            border: 1px solid var(--line);
            border-radius: 4px 14px 14px 14px;
        }
        .user .bubble {
            background: var(--user);
            border-color: #d2e3d5;
            border-radius: 14px 4px 14px 14px;
        }
        .agent .bubble { background: #fff; }
        .message.error .bubble { color: #8e3024; background: #fff2ef; border-color: #f1c6bc; }
        .message.loading .bubble { color: var(--muted); font-style: italic; }
        .composer {
            padding: 20px clamp(16px, 4vw, 28px) 24px;
            background: #f8faf7;
            border-top: 1px solid var(--line);
        }
        .fields {
            display: grid;
            grid-template-columns: minmax(180px, 0.7fr) minmax(0, 1.3fr);
            gap: 14px;
        }
        label { display: block; margin-bottom: 7px; font-size: 12px; font-weight: 700; }
        input, textarea {
            width: 100%;
            color: var(--ink);
            background: #fff;
            border: 1px solid #cbd6cd;
            border-radius: 7px;
            font: inherit;
            font-size: 14px;
            outline: none;
        }
        input { height: 43px; padding: 0 12px; }
        textarea { min-height: 43px; max-height: 150px; padding: 11px 12px; resize: vertical; }
        input:focus, textarea:focus { border-color: var(--forest); box-shadow: 0 0 0 3px rgb(23 75 61 / 12%); }
        .send-row { margin-top: 14px; display: flex; align-items: center; justify-content: space-between; gap: 14px; }
        .hint { color: var(--muted); font-size: 12px; }
        button {
            min-height: 42px;
            padding: 0 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 9px;
            color: #fff;
            background: var(--forest);
            border: 0;
            border-radius: 7px;
            font: inherit;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            transition: background 150ms ease, transform 150ms ease;
        }
        button:hover:not(:disabled) { background: #20634f; transform: translateY(-1px); }
        button:disabled { opacity: 0.6; cursor: wait; }
        button:focus-visible { outline: 3px solid #9abf4d; outline-offset: 3px; }
        .arrow { font-size: 17px; line-height: 1; }
        @keyframes appear { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        @media (max-width: 600px) {
            .topbar { min-height: 68px; padding-inline: 18px; }
            main { margin-top: 36px; }
            .fields { grid-template-columns: 1fr; gap: 12px; }
            .chat { min-height: 240px; max-height: 42vh; }
            .message { max-width: 94%; }
            .privacy-note { max-width: 130px; text-align: right; line-height: 1.35; }
            .hint { max-width: 58%; line-height: 1.35; }
        }
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after { scroll-behavior: auto !important; animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
        }
    </style>
</head>
<body>
    <header class="topbar">
        <div class="brand">
            <div class="brand-mark" aria-hidden="true">12</div>
            <div>
                <div class="brand-name">Day 12 AI Agent</div>
                <div class="brand-subtitle">Cloud Services &amp; Deployment</div>
            </div>
        </div>
        <div class="online"><span class="online-dot" aria-hidden="true"></span>Agent Online</div>
    </header>
    <main>
        <section class="intro" aria-labelledby="page-title">
            <p class="eyebrow">Your cloud agent</p>
            <h1 id="page-title">What can I help you explore?</h1>
            <p class="lead">Send a message to start a conversation with the Day 12 agent.</p>
        </section>
        <section class="workspace" aria-label="AI Agent chat">
            <div class="workspace-head">
                <span class="workspace-title">Conversation</span>
                <span class="privacy-note">Your API key stays in this page only</span>
            </div>
            <div class="chat" id="chat" role="log" aria-live="polite" aria-relevant="additions">
                <div class="message agent">
                    <div class="message-label">Agent</div>
                    <div class="bubble">Hello. Enter your API key below and send a question to begin.</div>
                </div>
            </div>
            <form class="composer" id="message-form">
                <div class="fields">
                    <div>
                        <label for="api-key">API key</label>
                        <input id="api-key" name="api-key" type="password" autocomplete="off" placeholder="Enter your API key" aria-describedby="key-hint">
                    </div>
                    <div>
                        <label for="question">Message</label>
                        <textarea id="question" name="question" rows="1" maxlength="2000" placeholder="Ask a question..." required></textarea>
                    </div>
                </div>
                <div class="send-row">
                    <span class="hint" id="key-hint">The key is sent only with your request.</span>
                    <button id="send-button" type="submit"><span>Send</span><span class="arrow" aria-hidden="true">&#8594;</span></button>
                </div>
            </form>
        </section>
    </main>
    <script>
        const form = document.getElementById("message-form");
        const keyInput = document.getElementById("api-key");
        const questionInput = document.getElementById("question");
        const chat = document.getElementById("chat");
        const sendButton = document.getElementById("send-button");

        function addMessage(kind, text, label) {
            const message = document.createElement("div");
            message.className = `message ${kind}`;
            const title = document.createElement("div");
            title.className = "message-label";
            title.textContent = label;
            const bubble = document.createElement("div");
            bubble.className = "bubble";
            bubble.textContent = text;
            message.append(title, bubble);
            chat.append(message);
            chat.scrollTop = chat.scrollHeight;
            return message;
        }

        function errorText(status) {
            if (status === 401) return "That API key was not accepted. Check it and try again.";
            if (status === 429) return "This agent is receiving too many requests. Please wait a moment and try again.";
            if (status === 402) return "The monthly usage budget has been reached. Please contact the service owner.";
            if (status >= 500) return "The agent had a server problem. Please try again shortly.";
            return "The request could not be completed. Please check your message and try again.";
        }

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const apiKey = keyInput.value;
            const question = questionInput.value.trim();
            if (!apiKey) {
                addMessage("error", "Enter your API key before sending a message.", "Notice");
                keyInput.focus();
                return;
            }
            if (!question) {
                questionInput.focus();
                return;
            }

            addMessage("user", question, "You");
            const loading = addMessage("agent loading", "Thinking...", "Agent");
            sendButton.disabled = true;
            questionInput.disabled = true;

            try {
                const response = await fetch("/ask", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-API-Key": apiKey,
                        "X-User-Id": "web-user"
                    },
                    body: JSON.stringify({ question })
                });
                const body = await response.json().catch(() => ({}));
                loading.remove();
                if (!response.ok) {
                    addMessage("error", errorText(response.status), "Notice");
                    return;
                }
                addMessage("agent", body.answer || "The agent returned an empty response.", "Agent");
                questionInput.value = "";
            } catch {
                loading.remove();
                addMessage("error", "Could not reach the agent. Check your connection and try again.", "Notice");
            } finally {
                sendButton.disabled = false;
                questionInput.disabled = false;
                questionInput.focus();
            }
        });
    </script>
</body>
</html>"""
        )


# ─────────────────────────────────────────────────────────────
# Health & readiness
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness probe — process còn sống không?

    TODO (CP1 + CP4):
      - Đang tắt dần (``lifecycle.shutting_down``) → trả
        ``JSONResponse(status_code=503, content={"status": "shutting_down"})``
      - Bình thường → ``{"status": "ok", "service": SERVICE_NAME,
        "version": SERVICE_VERSION}`` (mặc định FastAPI trả 200).

    Endpoint này phải **nhẹ**: không gọi Redis, không query DB. Nó chỉ trả
    lời câu hỏi "có cần restart container này không?". Nếu nó phụ thuộc
    Redis, Redis chết một nhịp là cả cụm container bị restart theo.
    """
    if lifecycle.shutting_down:
        return JSONResponse(
            status_code=503,
            content={"status": "shutting_down"},
        )
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/ready")
def ready(store: ConversationStore = Depends(get_store)):
    """Readiness probe — đã sẵn sàng nhận traffic chưa?

    TODO (CP4):
      - Đang tắt dần → 503 ``{"status": "shutting_down"}``
      - ``store.ping()`` False → 503 ``{"status": "not ready", "redis": False}``
      - Ngược lại → ``{"status": "ready", "redis": True}``

    Khác /health ở chỗ: endpoint này ĐƯỢC PHÉP kiểm tra dependency. Load
    balancer dùng nó để quyết định có đẩy request vào instance này không.
    """
    if lifecycle.shutting_down:
        return JSONResponse(
            status_code=503,
            content={"status": "shutting_down"},
        )
    if not store.ping():
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "redis": False},
        )
    return {"status": "ready", "redis": True}


# ─────────────────────────────────────────────────────────────
# Endpoint chính
# ─────────────────────────────────────────────────────────────
@app.post("/ask")
def ask(
    payload: AskRequest,
    user_id: str = Depends(verify_api_key),
    store: ConversationStore = Depends(get_store),
    limiter: RateLimiter = Depends(get_rate_limiter),
    guard: CostGuard = Depends(get_cost_guard),
):
    """Hỏi agent một câu.

    TODO (CP3 + CP4) — làm ĐÚNG THỨ TỰ sau:
      1. ``limiter.check(user_id)``           → 429 nếu gọi quá nhanh
      2. ``guard.check(user_id)``             → 402 nếu hết ngân sách
      3. ``history = store.get_history(user_id)``
      4. ``result = ask_llm(payload.question, history)``
      5. ``store.append(user_id, "user", payload.question)`` và
         ``store.append(user_id, "assistant", result["answer"])``
      6. ``guard.record(user_id, result["cost_usd"])``
      7. ``log_event("ask_completed", user_id=user_id,
         tokens_in=result["tokens_in"], tokens_out=result["tokens_out"],
         cost_usd=result["cost_usd"])``
      8. trả về::

            {
                "answer": result["answer"],
                "user_id": user_id,
                "history_length": len(history),
                "cost_usd": result["cost_usd"],
                "tokens": {"in": result["tokens_in"], "out": result["tokens_out"]},
            }

    Vì sao check trước rồi mới gọi LLM? Vì tiền mất ở bước gọi LLM. Chặn sau
    khi đã gọi thì bạn vừa trả tiền vừa trả lỗi.

    ``user_id`` do ``verify_api_key`` trả về, nên request không có API key
    hợp lệ sẽ dừng ở 401 trước khi chạm vào bất cứ dòng nào ở đây.
    """
    limiter.check(user_id)
    guard.check(user_id)

    history = store.get_history(user_id)
    result = ask_llm(payload.question, history)
    store.append(user_id, "user", payload.question)
    store.append(user_id, "assistant", result["answer"])
    guard.record(user_id, result["cost_usd"])
    log_event(
        "ask_completed",
        user_id=user_id,
        tokens_in=result["tokens_in"],
        tokens_out=result["tokens_out"],
        cost_usd=result["cost_usd"],
    )

    return {
        "answer": result["answer"],
        "user_id": user_id,
        "history_length": len(history),
        "cost_usd": result["cost_usd"],
        "tokens": {"in": result["tokens_in"], "out": result["tokens_out"]},
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
