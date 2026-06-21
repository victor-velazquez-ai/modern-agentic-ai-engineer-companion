"""Chat routes: conversations and their messages (Ch 25).

- ``POST /v1/chats``                       — start a conversation.
- ``GET  /v1/chats/{id}``                  — fetch a conversation.
- ``POST /v1/chats/{id}/messages``         — append a message.
- ``GET  /v1/chats/{id}/messages``         — list the conversation's history.

Transport only — delegates to ``ChatService``. The agent's *reply* is produced via the run/SSE
path; these routes own the conversation record the UI renders (Ch 38).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.schemas import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
)
from app.core.auth import Principal, get_current_principal
from app.core.deps import get_chat_service
from app.core.ratelimit import enforce_rate_limit
from app.domain.models import MessageRole
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ConversationResponse, status_code=201, summary="Start a conversation")
async def start_conversation(
    body: ConversationCreate,
    chats: ChatService = Depends(get_chat_service),
    principal: Principal = Depends(get_current_principal),
) -> ConversationResponse:
    conversation = await chats.start_conversation(
        tenant_id=principal.tenant_id, title=body.title
    )
    return ConversationResponse.from_domain(conversation)


@router.get("/{conversation_id}", response_model=ConversationResponse, summary="Fetch a conversation")
async def get_conversation(
    conversation_id: str,
    chats: ChatService = Depends(get_chat_service),
    principal: Principal = Depends(get_current_principal),
) -> ConversationResponse:
    conversation = await chats.get_conversation(
        tenant_id=principal.tenant_id, conversation_id=conversation_id
    )
    return ConversationResponse.from_domain(conversation)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=201,
    summary="Append a message",
    dependencies=[Depends(enforce_rate_limit)],
)
async def post_message(
    conversation_id: str,
    body: MessageCreate,
    chats: ChatService = Depends(get_chat_service),
    principal: Principal = Depends(get_current_principal),
) -> MessageResponse:
    message = await chats.post_message(
        tenant_id=principal.tenant_id,
        conversation_id=conversation_id,
        role=MessageRole(body.role),
        content=body.content,
    )
    return MessageResponse.from_domain(message)


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
    summary="List conversation history",
)
async def list_messages(
    conversation_id: str,
    chats: ChatService = Depends(get_chat_service),
    principal: Principal = Depends(get_current_principal),
) -> list[MessageResponse]:
    messages = await chats.history(
        tenant_id=principal.tenant_id, conversation_id=conversation_id
    )
    return [MessageResponse.from_domain(m) for m in messages]
