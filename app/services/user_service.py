from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional

from app.db import models, schemas
from app.core.security import get_password_hash

from sqlalchemy.sql import func
from fastapi import UploadFile
import shutil
import uuid
import os

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


def update_last_seen(db: Session, user_id: int):
    """Обновляет время последнего посещения на текущее."""
    user = get_user(db, user_id)
    if user:
        user.last_seen_at = func.now()
        db.commit()

def update_user_profile(db: Session, user_id: int, update_data: schemas.UserUpdate) -> models.User:
    """Обновляет текстовые поля профиля."""
    user = get_user(db, user_id)
    if not user: return None
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(user, key, value)
        
    db.commit()
    db.refresh(user)
    return user

def upload_avatar(db: Session, user_id: int, file: UploadFile) -> str:
    """Сохраняет аватарку и возвращает URL."""
    user = get_user(db, user_id)
    
    # Папка для загрузок
    if not os.path.exists("uploads"):
        os.makedirs("uploads")

    # Генерируем имя файла
    file_ext = file.filename.split(".")[-1]
    file_name = f"avatar_{user_id}_{uuid.uuid4()}.{file_ext}"
    file_path = f"uploads/{file_name}"
    
    # Сохраняем
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # URL для доступа (статика)
    url = f"/static/{file_name}"
    
    user.avatar_url = url
    db.commit()
    db.refresh(user)
    return url