from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.db import database, models, schemas
from app.api.deps import get_current_active_user
from app.services import chat_service

router = APIRouter(
    prefix="/v1/chats",
    tags=["Chats"],
    # Все эндпоинты в этом файле требуют авторизованного юзера
    dependencies=[Depends(get_current_active_user)]
)

@router.post("/", response_model=schemas.Chat)
def create_chat(
    chat_data: schemas.ChatCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """
    Создать новый чат.
    
    Текущий пользователь (создатель) автоматически
    добавляется в список участников.
    """
    new_chat = chat_service.create_new_chat(db, creator=current_user, chat_data=chat_data)
    
    # Нам нужно вручную заполнить поле participants для Pydantic схемы,
    # так как сервис возвращает модель SQLAlchemy
    participants = [link.user for link in new_chat.participant_links]
    
    # Конвертируем в Pydantic-схему (немного вручную)
    chat_response = schemas.Chat(
        id=new_chat.id,
        chat_type=new_chat.chat_type,
        chat_name=new_chat.chat_name,
        participants=[schemas.UserPublic.from_orm(p) for p in participants]
    )
    return chat_response


@router.get("/", response_model=List[schemas.Chat])
def get_my_chats(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """
    Получить список всех чатов текущего пользователя.
    """
    chats = chat_service.get_user_chats(db, user_id=current_user.id)
    
    # Конвертируем список моделей SQLAlchemy в список схем Pydantic
    response_chats = []
    for chat in chats:
        participants = [link.user for link in chat.participant_links]
        chat_dto = schemas.Chat(
            id=chat.id,
            chat_type=chat.chat_type,
            chat_name=chat.chat_name,
            participants=[schemas.UserPublic.from_orm(p) for p in participants]
        )
        response_chats.append(chat_dto)
        
    return response_chats


@router.post("/{chat_id}/users", status_code=status.HTTP_201_CREATED)
def add_user(
    chat_id: int,
    user_id: int, # Кого добавляем (передаем через Query параметр ?user_id=...)
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Добавить пользователя в группу."""
    chat_service.add_user_to_chat(db, chat_id, user_id, requester_id=current_user.id)
    return {"message": "User added successfully"}

@router.delete("/{chat_id}/users/me", status_code=status.HTTP_200_OK)
def leave_chat(
    chat_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Покинуть чат."""
    chat_service.remove_user_from_chat(db, chat_id, user_id=current_user.id, requester_id=current_user.id)
    return {"message": "You left the chat"}