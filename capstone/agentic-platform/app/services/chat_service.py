"""Chat use-cases: conversations and their messages (Ch 25).

A thin orchestration over the ``ChatRepository`` port. Creating a conversation, appending a
turn, and listing history are the operations the chat UI (Ch 38) drives. The agent reply itself
is produced by the run/agent path; this service owns the *conversation* record, not the
reasoning.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.errors import EntityNotFoundError
from app.domain.models import ChatMessage, Conversation, MessageRole
from app.domain.ports import ChatRepository


class ChatService:
    """Use-cases over conversations and messages."""

    def __init__(self, *, chats: ChatRepository) -> None:
        self._chats = chats

    async def start_conversation(
        self, *, tenant_id: str, title: str = "New conversation"
    ) -> Conversation:
        """Create and persist a new conversation for the tenant."""
        conversation = Conversation(tenant_id=tenant_id, title=title)
        return await self._chats.create_conversation(conversation)

    async def get_conversation(
        self, *, tenant_id: str, conversation_id: str
    ) -> Conversation:
        """Fetch a conversation for the tenant, or raise ``EntityNotFoundError``."""
        conversation = await self._chats.get_conversation(tenant_id, conversation_id)
        if conversation is None:
            raise EntityNotFoundError("Conversation", conversation_id)
        return conversation

    async def post_message(
        self,
        *,
        tenant_id: str,
        conversation_id: str,
        role: MessageRole,
        content: str,
    ) -> ChatMessage:
        """Append one message to a conversation after checking it exists for the tenant."""
        # Verify ownership before writing — never trust a client-supplied conversation id.
        await self.get_conversation(tenant_id=tenant_id, conversation_id=conversation_id)
        message = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata={"tenant_id": tenant_id},
        )
        return await self._chats.add_message(message)

    async def history(
        self, *, tenant_id: str, conversation_id: str
    ) -> Sequence[ChatMessage]:
        """Return the conversation's messages in chronological order."""
        await self.get_conversation(tenant_id=tenant_id, conversation_id=conversation_id)
        return await self._chats.list_messages(tenant_id, conversation_id)
