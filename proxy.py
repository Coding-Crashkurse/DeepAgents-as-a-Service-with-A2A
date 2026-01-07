import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Dict

import httpx
from a2a.client.card_resolver import A2ACardResolver
from a2a.client.client import ClientConfig
from a2a.client.client_factory import ClientFactory
from a2a.types import Message, Part, Role, TextPart
from a2a.utils import get_message_text
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles


BASE_URL = os.getenv("A2A_BASE_URL", "http://localhost:8001")
ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"

app = FastAPI(title="DeepAgents Proxy", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sse_payload(data: Dict[str, str]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=True)}\n\n"


@app.get("/api/health")
async def health() -> Dict[str, str]:
    return {"ok": "true", "a2a_base_url": BASE_URL}


@app.get("/api/stream")
async def stream(text: str = Query(..., min_length=1)) -> StreamingResponse:
    async def event_stream() -> AsyncGenerator[str, None]:
        request_id = str(uuid.uuid4())
        yield sse_payload({"type": "start", "request_id": request_id, "ts": utc_timestamp()})

        try:
            async with httpx.AsyncClient(timeout=None) as http:
                card = await A2ACardResolver(http, BASE_URL).get_agent_card()
                client = await ClientFactory.connect(
                    card,
                    client_config=ClientConfig(
                        supported_transports=[card.preferred_transport],
                        httpx_client=http,
                        streaming=True,
                        polling=False,
                    ),
                )

                try:
                    message = Message(
                        role=Role.user,
                        message_id=str(uuid.uuid4()),
                        parts=[Part(root=TextPart(text=text))],
                    )

                    async for task, update in client.send_message(message):
                        state = task.status.state.value
                        if update is None:
                            payload = {
                                "type": "status",
                                "state": state,
                                "text": "",
                                "request_id": request_id,
                                "ts": utc_timestamp(),
                            }
                        else:
                            update_text = (
                                get_message_text(update.status.message, delimiter=" ")
                                if update.status.message
                                else ""
                            )
                            payload = {
                                "type": "message",
                                "state": state,
                                "text": update_text,
                                "request_id": request_id,
                                "ts": utc_timestamp(),
                            }

                        yield sse_payload(payload)

                finally:
                    await client.close()

            yield sse_payload({"type": "done", "request_id": request_id, "ts": utc_timestamp()})
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001 - surface proxy errors to the UI
            yield sse_payload(
                {
                    "type": "error",
                    "message": str(exc),
                    "request_id": request_id,
                    "ts": utc_timestamp(),
                }
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
