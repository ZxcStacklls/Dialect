from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional

from app.db import models, schemas
from app.core.security import get_password_hash

# --- READ-операции (Получение данных) ---

def get_user(db: Session, user_id: int) -> Optional[models.User]:
    """Получить пользователя по его ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_phone(db: Session, phone_number: str) -> Optional[models.User]:
    """Получить пользователя по номеру телефона."""
    return db.query(models.User).filter(models.User.phone_number == phone_number).first()

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """Получить пользователя по юзернейму."""
    return db.query(models.User).filter(models.User.username == username).first()

# --- CREATE-операция (Создание) ---

def create_user(db: Session, user_data: schemas.UserCreate) -> models.User:
    """
    Создать нового пользователя.
    Эта функция НЕ проверяет, существует ли юзер.
    Она просто выполняет операцию создания.
    """
    # 1. Получаем хеш пароля
    hashed_password = get_password_hash(user_data.password)
    
    # 2. Создаем объект модели SQLAlchemy
    #    Обратите внимание: мы убираем 'password' и добавляем 'password_hash'
    db_user = models.User(
        phone_number=user_data.phone_number,
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        public_key=user_data.public_key,
        password_hash=hashed_password  # Используем хеш
    )
    
    # 3. Сохраняем в БД
    db.add(db_user)
    db.commit()
    db.refresh(db_user) # Обновляем объект, чтобы получить ID из БД
    
    return db_user


def search_users(
    db: Session, 
    query_str: str, 
    limit: int = 10
) -> list[models.User]:
    """
    Ищет пользователей по совпадению в username, имени или фамилии.
    """
    if not query_str:
        return []
        
    # Используем % для поиска подстроки (SQL LIKE)
    search_pattern = f"%{query_str}%"
    
    return db.query(models.User).filter(
        or_(
            models.User.username.like(search_pattern),
            models.User.first_name.like(search_pattern),
            models.User.last_name.like(search_pattern),
            models.User.phone_number.like(search_pattern)
        )
    ).limit(limit).all()