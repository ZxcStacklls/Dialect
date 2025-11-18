from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List
from sqlalchemy import and_, func

from app.db import models, schemas
from app.services import user_service

def create_new_chat(
    db: Session, 
    creator: models.User, 
    chat_data: schemas.ChatCreate
) -> models.Chat:
    """
    Создает новый чат или возвращает существующий (для ЛС).
    """
    participant_ids = chat_data.participant_ids
    if creator.id not in participant_ids:
        participant_ids.append(creator.id)
        
    # Убираем дубликаты ID
    participant_ids = list(set(participant_ids))

    # --- ЛОГИКА ДЛЯ ЛИЧНЫХ ЧАТОВ (PRIVATE) ---
    if chat_data.chat_type == models.ChatTypeEnum.private:
        if len(participant_ids) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Личный чат должен иметь ровно двух участников."
            )
        
        # Проверяем, существует ли уже такой чат между этими двумя
        # SQL-магия: ищем чат, у которого есть ровно эти 2 участника
        
        # 1. Ищем общие чаты
        # Это упрощенная проверка: ищем чат, где есть оба юзера и тип private.
        # В идеале нужен сложный JOIN, но для V1 подойдет такой метод:
        user1_id, user2_id = participant_ids
        
        existing_chat = db.query(models.Chat).join(models.ChatParticipant).filter(
            models.Chat.chat_type == models.ChatTypeEnum.private,
            models.ChatParticipant.user_id.in_([user1_id, user2_id])
        ).group_by(models.Chat.id).having(func.count(models.ChatParticipant.user_id) == 2).first()

        # Если нашли существующий чат — возвращаем его, не создавая новый
        if existing_chat:
            # Дополнительная проверка, что это именно эти двое (для надежности)
            participants = [p.user_id for p in existing_chat.participant_links]
            if set(participants) == set(participant_ids):
                return existing_chat

    # --- СОЗДАНИЕ НОВОГО ЧАТА (ГРУППА ИЛИ НОВЫЙ ЛС) ---
    
    # Проверка существования юзеров
    participants_objs = []
    for uid in participant_ids:
        user = user_service.get_user(db, user_id=uid)
        if not user:
             raise HTTPException(status_code=404, detail=f"User {uid} not found")
        participants_objs.append(user)

    # Создаем объект чата
    db_chat = models.Chat(
        chat_type=chat_data.chat_type,
        chat_name=chat_data.chat_name
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)

    # Добавляем участников
    for user in participants_objs:
        participant_link = models.ChatParticipant(
            user_id=user.id,
            chat_id=db_chat.id
        )
        db.add(participant_link)
    
    db.commit()
    db.refresh(db_chat)
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

def add_user_to_chat(db: Session, chat_id: int, user_id: int, requester_id: int):
    """Добавить пользователя в существующий чат."""
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    
    if chat.chat_type == models.ChatTypeEnum.private:
        raise HTTPException(status_code=400, detail="Нельзя добавить участника в личный чат")

    # Проверяем, есть ли добавляющий в этом чате (только участники могут добавлять)
    is_member = db.query(models.ChatParticipant).filter(
        models.ChatParticipant.chat_id == chat_id,
        models.ChatParticipant.user_id == requester_id
    ).first()
    
    if not is_member:
        raise HTTPException(status_code=403, detail="Вы не участник этого чата")

    # Проверяем, не добавлен ли уже целевой юзер
    existing_participant = db.query(models.ChatParticipant).filter(
        models.ChatParticipant.chat_id == chat_id,
        models.ChatParticipant.user_id == user_id
    ).first()
    
    if existing_participant:
        raise HTTPException(status_code=400, detail="Пользователь уже в чате")

    # Добавляем
    new_participant = models.ChatParticipant(chat_id=chat_id, user_id=user_id)
    db.add(new_participant)
    db.commit()
    return True

def remove_user_from_chat(db: Session, chat_id: int, user_id: int, requester_id: int):
    """Удалить пользователя из чата (или выйти самому)."""
    
    # Для V1 разрешаем удалять только себя (выйти из чата)
    # Или можно добавить логику админа позже.
    if user_id != requester_id:
         raise HTTPException(status_code=403, detail="В V1 можно удалять только себя (покинуть чат)")

    participant = db.query(models.ChatParticipant).filter(
        models.ChatParticipant.chat_id == chat_id,
        models.ChatParticipant.user_id == user_id
    ).first()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Участник не найден")
        
    db.delete(participant)
    db.commit()
    return True