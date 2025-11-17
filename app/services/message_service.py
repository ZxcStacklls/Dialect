from sqlalchemy.orm import Session
from typing import List
from app.db import models, schemas

def create_message(
    db: Session, 
    sender_id: int, 
    msg_data: schemas.MessageCreate
) -> models.Message:
    """
    Сохраняет зашифрованное сообщение в базу данных.
    """
    # Создаем запись
    db_msg = models.Message(
        chat_id=msg_data.chat_id,
        sender_id=sender_id,
        content=msg_data.content, # Это зашифрованные байты/строка
        status=models.MessageStatusEnum.sent
    )
    
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    return db_msg

def get_chat_history(
    db: Session, 
    chat_id: int, 
    limit: int = 50, 
    offset: int = 0
) -> List[models.Message]:
    """
    Получает историю сообщений чата (для загрузки при открытии).
    Сортируем от новых к старым (или наоборот, зависит от UI).
    """
    messages = db.query(models.Message)\
        .filter(models.Message.chat_id == chat_id)\
        .order_by(models.Message.sent_at.desc())\
        .limit(limit)\
        .offset(offset)\
        .all()
    
    return messages

def get_chat_participants(db: Session, chat_id: int) -> List[int]:
    """
    Получает ID всех участников чата, чтобы знать, кому рассылать.
    """
    participants = db.query(models.ChatParticipant.user_id)\
        .filter(models.ChatParticipant.chat_id == chat_id)\
        .all()
    # Превращаем список кортежей [(1,), (2,)] в список [1, 2]
    return [p[0] for p in participants]