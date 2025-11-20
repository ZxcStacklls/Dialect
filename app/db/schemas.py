from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
import enum

# Импортируем Enum'ы из models, чтобы использовать их в схемах
from .models import ChatTypeEnum, MessageStatusEnum

# --- Схемы Пользователя (User) ---

class UserBase(BaseModel):
    """Базовая схема пользователя (общие поля)"""
    phone_number: str
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None

class UserCreate(UserBase):
    """Схема для создания пользователя (регистрация)"""
    password: str  # Пароль в открытом виде, будет хеширован в сервисе
    public_key: str

class UserUpdate(BaseModel):
    """Схема для обновления профиля"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None

class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    public_key: str
    
    # Профиль
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    
    # Активность
    last_seen_at: datetime
    is_online: bool = False

class UserInDB(UserBase):
    """Полная схема пользователя (как в БД)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    public_key: str
    created_at: datetime


# --- Схемы Авторизации (Auth & Token) ---

class Token(BaseModel):
    """Схема JWT токена"""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """Схема данных, зашитых в JWT токен"""
    user_id: Optional[int] = None


# --- Схемы Чата (Chat) ---

class ChatParticipantPublic(BaseModel):
    user_id: int
    custom_nickname: Optional[str] = None

class ChatBase(BaseModel):
    chat_type: ChatTypeEnum
    chat_name: Optional[str] = None

class ChatCreate(BaseModel):
    """Схема для создания нового чата"""
    chat_type: ChatTypeEnum
    participant_ids: List[int] # ID пользователей, которых добавляем в чат
    chat_name: Optional[str] = None # Если это группа

class Chat(ChatBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    owner_id: Optional[int] = None # <-- Добавили владельца
    # Участники теперь могут содержать никнейм, поэтому можно усложнить схему,
    # но пока оставим список UserPublic, а никнейм будем тянуть отдельно или расширим UserPublic
    participants: List[UserPublic] = []


# --- Схемы Сообщения (Message) ---

class MessageBase(BaseModel):
    content: bytes # В Pydantic BLOB/BINARY = bytes
    
class MessageCreate(BaseModel):
    """Схема для создания сообщения (отправка по WebSocket)"""
    chat_id: int
    content: bytes # Клиент шлет зашифрованные байты (или base64, тогда тут str)

class MessageUpdate(BaseModel):
    """Схема для редактирования сообщения"""
    message_id: int
    content: bytes # Новое зашифрованное содержимое

class Message(MessageBase):
    """Схема для отображения сообщения (получение по WebSocket)"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    sender_id: Optional[int]
    sent_at: datetime
    status: MessageStatusEnum
    is_pinned: bool = False