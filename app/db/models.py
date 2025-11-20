import enum
from sqlalchemy import (
    Column, Integer, String, ForeignKey, Enum, TIMESTAMP, TEXT, BLOB, BIGINT,
    create_engine, UniqueConstraint, Boolean
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class ChatTypeEnum(str, enum.Enum):
    private = 'private'
    group = 'group'

class MessageStatusEnum(str, enum.Enum):
    sent = 'sent'
    delivered = 'delivered'
    read = 'read'

# --- Основные Модели ---

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    public_key = Column(TEXT, nullable=False)
    
    # --- ПРОФИЛЬ (Базовый) ---
    avatar_url = Column(String(255), nullable=True)  # Ссылка на файл аватарки
    bio = Column(String(500), nullable=True)         # Описание "Обо мне"
    
    # --- АКТИВНОСТЬ ---
    # Время последнего выхода из сети.
    # Если пользователь онлайн (есть WebSocket), это поле игнорируется клиентом.
    last_seen_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    chat_links = relationship("ChatParticipant", back_populates="user")
    sent_messages = relationship("Message", back_populates="sender")
    owned_chats = relationship("Chat", back_populates="owner")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    chat_type = Column(Enum(ChatTypeEnum), nullable=False, default=ChatTypeEnum.private)
    chat_name = Column(String(255), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    participant_links = relationship("ChatParticipant", back_populates="chat")
    messages = relationship("Message", back_populates="chat")
    owner = relationship("User", back_populates="owned_chats")


class ChatParticipant(Base):
    __tablename__ = "chat_participants"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    custom_nickname = Column(String(100), nullable=True)
    joined_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    last_cleared_at = Column(TIMESTAMP, nullable=True) 

    __table_args__ = (UniqueConstraint('user_id', 'chat_id', name='_user_chat_uc'),)

    user = relationship("User", back_populates="chat_links")
    chat = relationship("Chat", back_populates="participant_links")


class Message(Base):
    __tablename__ = "messages"

    id = Column(BIGINT, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content = Column(BLOB, nullable=False)
    sent_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    status = Column(Enum(MessageStatusEnum), nullable=False, default=MessageStatusEnum.sent)
    is_pinned = Column(Boolean, default=False, nullable=False)

    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages")