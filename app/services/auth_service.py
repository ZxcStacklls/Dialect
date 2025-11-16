from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Optional

from app.db import models, schemas
from app.services import user_service
from app.core.security import verify_password

# Импортируем наш синглтон-сервис
from ..core.bloom_filter import bloom_service


def register_new_user(db: Session, user_data: schemas.UserCreate) -> models.User:
    """
    Бизнес-логика регистрации нового пользователя.
    Включает проверки на дубликаты.
    """

    # 1. Проверка на дубликат телефона
    db_user_by_phone = user_service.get_user_by_phone(db, phone_number=user_data.phone_number)
    if db_user_by_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким номером телефона уже зарегистрирован.",
        )

    # 2. Проверка на дубликат юзернейма (если он предоставлен)
    if user_data.username:

        # ⭐ ШАГ 2.1: Быстрая проверка Фильтром Блума
        if bloom_service.contains(user_data.username):

            # ⭐ ШАГ 2.2: Если фильтр сказал "возможно", делаем точную проверку в БД
            db_user_by_username = user_service.get_user_by_username(db, username=user_data.username)
            if db_user_by_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Этот юзернейм уже занят.",
                )
        # Если фильтр сказал "нет", мы пропускаем проверку БД (шаг 2.2)
        # и сразу переходим к созданию.

    # 3. Если все проверки пройдены, создаем пользователя
    new_user = user_service.create_user(db, user_data=user_data)

    # ⭐ ШАГ 4: Добавляем новый юзернейм в фильтр
    if new_user.username:
        bloom_service.add(new_user.username)

    return new_user


def authenticate_user(db: Session, phone_number: str, password: str) -> Optional[models.User]:
    """
    Бизнес-логика аутентификации (входа).
    (Этот код остался без изменений)
    """

    # 1. Находим пользователя по номеру
    user = user_service.get_user_by_phone(db, phone_number=phone_number)
    if not user:
        return None

    # 2. Проверяем пароль
    if not verify_password(password, user.password_hash):
        return None

    # 3. Все верно, возвращаем пользователя
    return user