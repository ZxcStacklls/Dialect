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

class UserPublic(BaseModel):
    """
    Публичная схема пользователя (то, что видят другие)
    Никогда не включаем сюда номер телефона или дату регистрации.
    """
    model_config = ConfigDict(from_attributes=True) # Для чтения из SQLAlchemy
    
    id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    public_key: str # Открытый ключ нужен другим для шифрования

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

class ChatBase(BaseModel):
    chat_type: ChatTypeEnum
    chat_name: Optional[str] = None

class ChatCreate(BaseModel):
    """Схема для создания нового чата"""
    chat_type: ChatTypeEnum
    participant_ids: List[int] # ID пользователей, которых добавляем в чат
    chat_name: Optional[str] = None # Если это группа

class Chat(ChatBase):
    """Схема для отображения чата (включая участников)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    participants: List[UserPublic] = [] # Показываем публичные данные участников


# --- Схемы Сообщения (Message) ---

class MessageBase(BaseModel):
    content: bytes # В Pydantic BLOB/BINARY = bytes
    
class MessageCreate(BaseModel):
    """Схема для создания сообщения (отправка по WebSocket)"""
    chat_id: int
    content: bytes # Клиент шлет зашифрованные байты (или base64, тогда тут str)

class Message(MessageBase):
    """Схема для отображения сообщения (получение по WebSocket)"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    sender_id: Optional[int]
    sent_at: datetime
    status: MessageStatusEnum