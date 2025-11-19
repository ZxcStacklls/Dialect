from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.db import database, models, schemas
from app.api.deps import get_current_active_user
from app.services import chat_service

router = APIRouter(
    prefix="/v1/chats",
    tags=["Chats"],
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
    participants = [link.user for link in new_chat.participant_links]
    
    chat_response = schemas.Chat(
        id=new_chat.id,
        chat_type=new_chat.chat_type,
        chat_name=new_chat.chat_name,
        owner_id=new_chat.owner_id,
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

@router.delete("/{chat_id}/users/{target_user_id}", status_code=status.HTTP_200_OK)
def remove_user(
    chat_id: int,
    target_user_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Удалить участника (или выйти самому)."""
    chat_service.remove_user_from_chat(
        db, chat_id, user_id_to_remove=target_user_id, requester_id=current_user.id
    )
    return {"message": "User removed/left"}

@router.put("/{chat_id}/users/{user_id}/nickname", status_code=status.HTTP_200_OK)
def set_nickname(
    chat_id: int,
    user_id: int,
    nickname: str = Query(..., min_length=1, max_length=50),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Установить кастомный никнейм в группе."""
    chat_service.set_custom_nickname(
        db, chat_id, target_user_id=user_id, nickname=nickname, requester_id=current_user.id
    )
    return {"message": "Nickname updated"}

@router.put("/{chat_id}/name", status_code=status.HTTP_200_OK)
def rename_chat(
    chat_id: int,
    name: str = Query(..., min_length=1, max_length=100),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Переименовать группу (только для владельца)."""
    chat_service.update_chat_name(
        db, chat_id, new_name=name, requester_id=current_user.id
    )
    return {"message": "Chat renamed successfully"}


@router.delete("/{chat_id}", status_code=status.HTTP_200_OK)
def delete_chat_endpoint(
    chat_id: int,
    for_everyone: bool = Query(False), # ?for_everyone=true/false
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """
    Удалить чат целиком.
    - for_everyone=false (default): Удалить у себя (выйти).
    - for_everyone=true: Удалить у всех (удалить чат физически).
    """
    chat_service.delete_chat(db, chat_id, current_user.id, for_everyone)
    return {"message": "Chat deleted"}


@router.delete("/{chat_id}/messages", status_code=status.HTTP_200_OK)
def clear_history_endpoint(
    chat_id: int,
    for_everyone: bool = Query(False),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """
    Очистить историю сообщений.
    - for_everyone=false: Скрыть старые сообщения только для себя.
    - for_everyone=true: Удалить сообщения физически.
    """
    chat_service.clear_chat_history(db, chat_id, current_user.id, for_everyone)
    return {"message": "History cleared"}