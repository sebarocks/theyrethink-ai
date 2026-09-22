"""Chat por SSE con eventos estables y cancelación cooperativa."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.service import AgentService
from app.api.deps import CurrentUser, ensure_user_id
from app.db import get_session
from app.models import Thread, User

router = APIRouter(prefix="/threads", tags=["chat"])
HEARTBEAT_SECONDS = 15.0


class ChatRequest(BaseModel):
    text: str = Field(min_length=1, max_length=32_000)


def get_agent_service(request: Request) -> AgentService:
    return request.app.state.agent_service


def _event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{thread_id}/messages")
async def send_message(
    thread_id: int,
    payload: ChatRequest,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_session),  # noqa: B008
    service: AgentService = Depends(get_agent_service),  # noqa: B008
) -> StreamingResponse:
    thread = await db.get(Thread, thread_id)
    user_id = ensure_user_id(user)
    if thread is None or thread.user_id != user_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "thread_not_found",
                "detail": "El hilo no existe.",
            },
        )

    async def produce(queue: asyncio.Queue[tuple[str, object]]) -> None:
        try:
            async for chunk in service.send_message(
                agent_id=thread.agent_id,
                user_id=user_id,
                thread_id=thread_id,
                text=payload.text,
            ):
                await queue.put(("chunk", {"text": chunk.text, "done": chunk.done}))
            await queue.put(("finished", None))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await queue.put(("failed", exc))

    async def events() -> AsyncIterator[str]:
        queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()
        producer = asyncio.create_task(produce(queue))
        response_text = ""
        try:
            while True:
                try:
                    kind, value = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield _event("heartbeat", {})
                    continue

                if kind == "chunk":
                    data = cast(dict[str, object], value)
                    response_text += str(data["text"])
                    yield _event("chunk", data)
                elif kind == "failed":
                    await db.rollback()
                    yield _event(
                        "error",
                        {
                            "code": "chat_stream_failed",
                            "detail": "No se pudo completar la respuesta.",
                        },
                    )
                    return
                else:
                    await service.record_turn(
                        db,
                        thread_id=thread_id,
                        user_text=payload.text,
                        assistant_text=response_text,
                    )
                    await db.commit()
                    yield _event("done", {})
                    return
        except asyncio.CancelledError:
            await db.rollback()
            raise
        finally:
            if not producer.done():
                producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
