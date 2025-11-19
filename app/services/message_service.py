from sqlalchemy.orm import Session
from sqlalchemy import update
from typing import List
from fastapi import HTTPException, status

from app.db import models, schemas

# --- Вспомогательная функция проверки ---
def check_is_participant(db: Session, chat_id: int, user_id: int):
    """Проверяет, состоит ли пользователь в чате. Если нет — 403 Forbidden."""
    participant = db.query(models.ChatParticipant).filter(
        models.ChatParticipant.chat_id == chat_id,
        models.ChatParticipant.user_id == user_id
    ).first()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не являетесь участником этого чата"
        )
    return participant


def create_message(
    db: Session, 
    sender_id: int, 
    msg_data: schemas.MessageCreate
) -> models.Message:
    """
    Сохраняет сообщение. СТРОГАЯ ПРОВЕРКА: отправитель должен быть в чате.
    """
    # 1. Проверка участия
    check_is_participant(db, msg_data.chat_id, sender_id)

    # 2. Создаем запись
    db_msg = models.Message(
        chat_id=msg_data.chat_id,
        sender_id=sender_id,
        content=msg_data.content,
        status=models.MessageStatusEnum.sent
    )
    
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    return db_msg


def get_chat_history(
    db: Session, 
    chat_id: int, 
    user_id: int,
    limit: int = 50, 
    offset: int = 0
) -> List[models.Message]:
    """
    Получает историю. Учитывает очистку истории (last_cleared_at).
    """
    # 1. Проверяем участие и получаем данные об очистке
    participant = check_is_participant(db, chat_id, user_id)

    query = db.query(models.Message).filter(models.Message.chat_id == chat_id)

    # 2. Фильтруем по времени очистки (если была)
    if participant.last_cleared_at:
        query = query.filter(models.Message.sent_at > participant.last_cleared_at)
        
    # 3. Сортировка и лимит
    messages = query.order_by(models.Message.sent_at.desc())\
        .limit(limit)\
        .offset(offset)\
        .all()
    
    return messages


def get_chat_participants(db: Session, chat_id: int) -> List[int]:
    """Получает ID всех участников."""
    participants = db.query(models.ChatParticipant.user_id)\
        .filter(models.ChatParticipant.chat_id == chat_id)\
        .all()
    return [p[0] for p in participants]


def mark_messages_as_read(db: Session, chat_id: int, user_id: int, last_message_id: int):
    """Помечает прочитанным. СТРОГАЯ ПРОВЕРКА."""
    check_is_participant(db, chat_id, user_id)
    
    stmt = (
        update(models.Message)
        .where(
            models.Message.chat_id == chat_id,
            models.Message.id <= last_message_id,
            models.Message.sender_id != user_id,
            models.Message.status != models.MessageStatusEnum.read
        )
        .values(status=models.MessageStatusEnum.read)
    )
    db.execute(stmt)
    db.commit()


def update_message(db: Session, message_id: int, user_id: int, new_content: bytes):
    """Редактирование (автор)."""
    # Тут проверка участия не обязательна, так как мы проверяем авторство.
    # Если ты автор, ты либо в чате, либо был в нем.
    message = db.query(models.Message).filter(models.Message.id == message_id).first()
    if not message: return None
    if message.sender_id != user_id: return False
        
    message.content = new_content
    db.commit()
    db.refresh(message)
    return message


def delete_message(db: Session, message_id: int, user_id: int):
    """Удаление (автор или владелец)."""
    message = db.query(models.Message).filter(models.Message.id == message_id).first()
    if not message: return None
        
    is_author = (message.sender_id == user_id)
    chat = db.query(models.Chat).filter(models.Chat.id == message.chat_id).first()
    is_owner = (chat and chat.owner_id == user_id)

    if is_author or is_owner:
        db.delete(message)
        db.commit()
        return True
    return False


def pin_message(db: Session, message_id: int, user_id: int, is_pinned: bool):
    """Закреп (участник)."""
    message = db.query(models.Message).filter(models.Message.id == message_id).first()
    if not message: return None
    
    # Проверка участия
    check_is_participant(db, message.chat_id, user_id)
    
    message.is_pinned = is_pinned
    db.commit()
    return True

def delete_all_messages_in_chat(db: Session, chat_id: int):
    """Физическое удаление всех сообщений (для очистки 'для всех')."""
    db.query(models.Message).filter(models.Message.chat_id == chat_id).delete()
    db.commit()