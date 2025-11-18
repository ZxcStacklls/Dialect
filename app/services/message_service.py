from sqlalchemy.orm import Session
from sqlalchemy import update
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

def mark_messages_as_read(db: Session, chat_id: int, user_id: int, last_message_id: int):
    """
    Помечает все сообщения в чате до last_message_id (включительно)
    как 'read', ЕСЛИ они были отправлены НЕ текущим пользователем.
    """
    # Обновляем статус в БД
    stmt = (
        update(models.Message)
        .where(
            models.Message.chat_id == chat_id,
            models.Message.id <= last_message_id,
            models.Message.sender_id != user_id, # Не помечаем свои же сообщения
            models.Message.status != models.MessageStatusEnum.read
        )
        .values(status=models.MessageStatusEnum.read)
    )
    db.execute(stmt)
    db.commit()


def update_message(db: Session, message_id: int, user_id: int, new_content: bytes):
    """
    Обновляет текст сообщения, если его автор == user_id.
    """
    message = db.query(models.Message).filter(models.Message.id == message_id).first()
    
    if not message:
        return None # Сообщение не найдено
        
    if message.sender_id != user_id:
        return False # Попытка изменить чужое сообщение (или 403)
        
    message.content = new_content
    # В идеале тут можно добавить поле edited_at в модель, но для V1 хватит контента
    db.commit()
    db.refresh(message)
    return message

def delete_message(db: Session, message_id: int, user_id: int):
    """
    Удаляет сообщение, если его автор == user_id.
    """
    message = db.query(models.Message).filter(models.Message.id == message_id).first()
    
    if not message:
        return None
        
    if message.sender_id != user_id:
        return False
        
    db.delete(message)
    db.commit()
    return True