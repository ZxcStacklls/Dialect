from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List

from app.db import models, schemas
from app.services import user_service

def create_new_chat(
    db: Session, 
    creator: models.User, 
    chat_data: schemas.ChatCreate
) -> models.Chat:
    """
    Создает новый чат (личный или групповой).
    """
    
    # 1. Проверяем, существуют ли все приглашенные участники
    participant_ids = chat_data.participant_ids
    
    # Обязательно добавляем создателя в список участников
    if creator.id not in participant_ids:
        participant_ids.append(creator.id)

    participants: List[models.User] = []
    for user_id in participant_ids:
        user = user_service.get_user(db, user_id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь с ID {user_id} не найден."
            )
        participants.append(user)

    # 2. Обрабатываем личные чаты (V1 не будет их объединять, но можно добавить)
    if chat_data.chat_type == models.ChatTypeEnum.private:
        if len(participants) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Личный чат должен иметь ровно двух участников."
            )
        # (В V2 здесь можно добавить проверку, не существует ли уже личный чат)
    
    # 3. Создаем сам чат
    db_chat = models.Chat(
        chat_type=chat_data.chat_type,
        chat_name=chat_data.chat_name
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)

    # 4. Добавляем всех участников в chat_participants
    for user in participants:
        participant_link = models.ChatParticipant(
            user_id=user.id,
            chat_id=db_chat.id
        )
        db.add(participant_link)
    
    db.commit()
    db.refresh(db_chat) # Обновляем, чтобы подтянуть связи
    return db_chat


def get_user_chats(db: Session, user_id: int) -> List[models.Chat]:
    """
    Возвращает список всех чатов, в которых состоит пользователь.
    """
    # Находим пользователя (это также гарантирует, что он существует)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
        
    # user.chat_links (из models.py) -> [ChatParticipant, ...]
    # link.chat -> Chat
    chats = [link.chat for link in user.chat_links]
    
    return chats