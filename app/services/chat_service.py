from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from sqlalchemy import func
from typing import List
import datetime

from app.db import models, schemas
from app.services import user_service
# Импортируем message_service для удаления сообщений
from app.services import message_service 

def create_new_chat(db: Session, creator: models.User, chat_data: schemas.ChatCreate) -> models.Chat:
    participant_ids = chat_data.participant_ids
    if creator.id not in participant_ids:
        participant_ids.append(creator.id)
    participant_ids = list(set(participant_ids))

    # Private logic
    if chat_data.chat_type == models.ChatTypeEnum.private:
        if len(participant_ids) != 2:
            raise HTTPException(status_code=400, detail="Личный чат должен иметь 2 участников.")
        
        user1_id, user2_id = participant_ids
        existing_chat = db.query(models.Chat).join(models.ChatParticipant).filter(
            models.Chat.chat_type == models.ChatTypeEnum.private,
            models.ChatParticipant.user_id.in_([user1_id, user2_id])
        ).group_by(models.Chat.id).having(func.count(models.ChatParticipant.user_id) == 2).first()

        if existing_chat:
            parts = [p.user_id for p in existing_chat.participant_links]
            if set(parts) == set(participant_ids):
                return existing_chat

    # Group logic
    owner_id = None
    if chat_data.chat_type == models.ChatTypeEnum.group:
        if len(participant_ids) > 30:
            raise HTTPException(status_code=400, detail="Максимум 30 участников.")
        owner_id = creator.id

    # Create
    participants_objs = []
    for uid in participant_ids:
        user = user_service.get_user(db, user_id=uid)
        if not user: raise HTTPException(status_code=404, detail=f"User {uid} not found")
        participants_objs.append(user)

    db_chat = models.Chat(
        chat_type=chat_data.chat_type,
        chat_name=chat_data.chat_name,
        owner_id=owner_id
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)

    for user in participants_objs:
        participant_link = models.ChatParticipant(user_id=user.id, chat_id=db_chat.id)
        db.add(participant_link)
    
    db.commit()
    db.refresh(db_chat)
    return db_chat


def get_user_chats(db: Session, user_id: int) -> List[models.Chat]:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user: raise HTTPException(status_code=404, detail="User not found")
    return [link.chat for link in user.chat_links]


def add_user_to_chat(db: Session, chat_id: int, user_id: int, requester_id: int):
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat: raise HTTPException(status_code=404, detail="Chat not found")
    if chat.chat_type == models.ChatTypeEnum.private:
        raise HTTPException(status_code=400, detail="Нельзя добавить участника в ЛС")

    # Проверка участия requester
    is_member = db.query(models.ChatParticipant).filter(
        models.ChatParticipant.chat_id == chat_id,
        models.ChatParticipant.user_id == requester_id
    ).first()
    if not is_member: raise HTTPException(status_code=403, detail="Вы не участник")

    # Лимит
    count = db.query(func.count(models.ChatParticipant.id)).filter(models.ChatParticipant.chat_id == chat_id).scalar()
    if count >= 30: raise HTTPException(status_code=400, detail="Группа полна")

    existing = db.query(models.ChatParticipant).filter(models.ChatParticipant.chat_id == chat_id, models.ChatParticipant.user_id == user_id).first()
    if existing: raise HTTPException(status_code=400, detail="Уже в чате")

    db.add(models.ChatParticipant(chat_id=chat_id, user_id=user_id))
    db.commit()
    return True


def remove_user_from_chat(db: Session, chat_id: int, user_id_to_remove: int, requester_id: int):
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat: raise HTTPException(status_code=404, detail="Chat not found")

    if user_id_to_remove != requester_id:
        if chat.owner_id != requester_id:
            raise HTTPException(status_code=403, detail="Только владелец может удалять других")

    participant = db.query(models.ChatParticipant).filter(
        models.ChatParticipant.chat_id == chat_id,
        models.ChatParticipant.user_id == user_id_to_remove
    ).first()
    if not participant: raise HTTPException(status_code=404, detail="Участник не найден")
        
    db.delete(participant)
    db.commit()
    return True


def set_custom_nickname(db: Session, chat_id: int, target_user_id: int, nickname: str, requester_id: int):
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat: raise HTTPException(status_code=404, detail="Chat not found")

    if target_user_id != requester_id and chat.owner_id != requester_id:
        raise HTTPException(status_code=403, detail="Нет прав")

    participant = db.query(models.ChatParticipant).filter(
        models.ChatParticipant.chat_id == chat_id,
        models.ChatParticipant.user_id == target_user_id
    ).first()
    if not participant: raise HTTPException(status_code=404, detail="Participant not found")

    participant.custom_nickname = nickname
    db.commit()
    return True


def update_chat_name(db: Session, chat_id: int, new_name: str, requester_id: int):
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat: raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.chat_type != models.ChatTypeEnum.group:
        raise HTTPException(status_code=400, detail="Только группы")
    if chat.owner_id != requester_id:
        raise HTTPException(status_code=403, detail="Только владелец")

    chat.chat_name = new_name
    db.commit()
    return True


# --- НОВЫЕ ФУНКЦИИ УДАЛЕНИЯ И ОЧИСТКИ ---

def delete_chat(db: Session, chat_id: int, user_id: int, for_everyone: bool):
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat: raise HTTPException(status_code=404, detail="Chat not found")

    if for_everyone:
        # Удаление для всех
        if chat.chat_type == models.ChatTypeEnum.group:
            if chat.owner_id != user_id:
                raise HTTPException(status_code=403, detail="Только владелец может удалить группу")
        else:
            # В ЛС проверяем, что юзер вообще участник
            if not db.query(models.ChatParticipant).filter_by(chat_id=chat_id, user_id=user_id).first():
                raise HTTPException(status_code=403, detail="Вы не участник")
        
        db.delete(chat) # Каскадное удаление
        db.commit()
    else:
        # Удаление для себя (выход из чата)
        part = db.query(models.ChatParticipant).filter_by(chat_id=chat_id, user_id=user_id).first()
        if part:
            db.delete(part)
            db.commit()
    return True

def clear_chat_history(db: Session, chat_id: int, user_id: int, for_everyone: bool):
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat: raise HTTPException(status_code=404, detail="Chat not found")

    if for_everyone:
        if chat.chat_type == models.ChatTypeEnum.group and chat.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Только владелец может очистить для всех")
        
        if not db.query(models.ChatParticipant).filter_by(chat_id=chat_id, user_id=user_id).first():
             raise HTTPException(status_code=403, detail="Вы не участник")

        message_service.delete_all_messages_in_chat(db, chat_id)
    else:
        part = db.query(models.ChatParticipant).filter_by(chat_id=chat_id, user_id=user_id).first()
        if not part: raise HTTPException(status_code=404, detail="Вы не участник")
        
        # ⭐ ВАЖНОЕ ИЗМЕНЕНИЕ: Используем func.now() (время БД), а не datetime.utcnow()
        part.last_cleared_at = func.now()
        db.commit()
    return True