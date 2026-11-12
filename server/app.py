"""Jo web chat backend.

Exposes the chat contract used by the GitHub Pages GUI:

    POST /v1/chat  {"message": "..."}  ->  {"response": "..."}

The endpoint reuses Jo's direct-chat agent path (same task shape the
Telegram worker uses) so web conversations go through the same
consciousness loop instead of a separate code path.
"""

from typing import Any, Dict

import uuid

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Jo", version="6.5.1")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


def _get_chat_agent():
    from supervisor.workers import _get_chat_agent

    return _get_chat_agent()


def _run_direct_chat(message: str) -> str:
    agent = _get_chat_agent()
    task: Dict[str, Any] = {
        "id": "web_" + uuid.uuid4().hex[:8],
        "type": "task",
        "chat_id": 0,
        "_is_direct_chat": True,
        "text": message,
    }
    events = agent.handle_task(task) or []
    for event in events:
        if isinstance(event, dict) and event.get("type") == "send_message":
            return str(event.get("text") or "")
    return ""


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    response = _run_direct_chat(req.message)
    return ChatResponse(response=response)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}
