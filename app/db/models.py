import enum
from sqlalchemy import (
    Column, Integer, String, ForeignKey, Enum, TIMESTAMP, TEXT, BLOB, BIGINT,
    create_engine, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

# Создаем базовый класс для всех моделей
Base = declarative_base()

# --- Модели ENUM (для типов) ---
# Это помогает использовать Enum в Python, который маппится на ENUM в SQL

class ChatTypeEnum(str, enum.Enum):
    private = 'private'
    group = 'group'

class MessageStatusEnum(str, enum.Enum):
    sent = 'sent'
    delivered = 'delivered'
    read = 'read'


# --- Основные Модели Таблиц ---

class User(Base):
    """Модель Пользователя (таблица 'users')"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    public_key = Column(TEXT, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    # --- Связи ---
    # Связь с 'chat_participants' (какие чаты у юзера)
    chat_links = relationship("ChatParticipant", back_populates="user")
    
    # Связь с 'messages' (какие сообщения отправил)
    sent_messages = relationship("Message", back_populates="sender")


class Chat(Base):
    """Модель Чата (таблица 'chats')"""
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    chat_type = Column(Enum(ChatTypeEnum), nullable=False, default=ChatTypeEnum.private)
    chat_name = Column(String(255), nullable=True) # Имя для групповых чатов
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    # --- Связи ---
    # Связь с 'chat_participants' (какие юзеры в чате)
    participant_links = relationship("ChatParticipant", back_populates="chat")

    # Связь с 'messages' (какие сообщения в чате)
    messages = relationship("Message", back_populates="chat")


class ChatParticipant(Base):
    """
    Модель Участника Чата (таблица 'chat_participants')
    Это 'association object', связывающий User и Chat.
    """
    __tablename__ = "chat_participants"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    # Уникальный индекс, чтобы юзер не мог дважды вступить в один чат
    __table_args__ = (UniqueConstraint('user_id', 'chat_id', name='_user_chat_uc'),)

    # --- Связи ---
    user = relationship("User", back_populates="chat_links")
    chat = relationship("Chat", back_populates="participant_links")


class Message(Base):
    """Модель Сообщения (таблица 'messages')"""
    __tablename__ = "messages"

    id = Column(BIGINT, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content = Column(BLOB, nullable=False) # Зашифрованный контент
    sent_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    status = Column(Enum(MessageStatusEnum), nullable=False, default=MessageStatusEnum.sent)

    # --- Связи ---
    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", back_populates="sent_messages")