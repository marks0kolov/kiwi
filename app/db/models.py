import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class MessageType(enum.Enum):
    """An enum for message types in kiwi's context window"""
    SYSTEM_MESSAGE = enum.auto()
    TOOL_RESPONSE = enum.auto()

    USER_MESSAGE = enum.auto()
    USER_ACTION = enum.auto()
    USER_REACTION = enum.auto()

    KIWI_MESSAGE = enum.auto()
    KIWI_REACTION = enum.auto()


class User(Base):
    "Table storing Telegram users known to kiwi"
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=False,
    )

    username: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
    )


class Conversation(Base):
    "Table storing all conversations each user had with kiwi"
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )

    system_prompt: Mapped[Text] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    user: Mapped[User] = relationship(
        back_populates="conversations",
    )


class Message(Base):
    "Table storing all messages sent by user, kiwi, system or more"
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    message_type: Mapped[MessageType] = mapped_column(
        Enum(
            MessageType,
            name="message_type",
        ),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    context: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    conversation: Mapped[Conversation] = relationship(
        back_populates="messages",
    )

    __table_args__ = (
        Index(
            "ix_messages_conversation_sent_at",
            "conversation_id",
            "sent_at",
        ),
    )
