from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict

from app.db import database, models, schemas
from app.api.deps import get_current_active_user
from app.services import user_service

# Импортируем наш фильтр для проверки юзернейма
from ...core.bloom_filter import bloom_service

router = APIRouter(
    prefix="/v1/users",
    tags=["Users"]  # Тег для документации
)


# --- 1. Защищенный эндпоинт: "Получить мой профиль" ---

@router.get("/me", response_model=schemas.UserPublic)
def read_users_me(
        current_user: models.User = Depends(get_current_active_user)
):
    """
    Получить данные о текущем, аутентифицированном пользователе.

    FastAPI (благодаря `Depends`) не вызовет этот код,
    пока `get_current_active_user` не вернет пользователя
    или не выбросит ошибку 401.
    """
    # current_user - это полная модель User из БД.
    # FastAPI автоматически преобразует ее в Pydantic-схему UserPublic.
    return current_user


# --- 2. Публичный эндпоинт: "Проверить доступность юзернейма" ---

@router.get("/check-username/{username}", response_model=Dict[str, bool])
def check_username_availability(
        username: str,
        db: Session = Depends(database.get_db)
):
    """
    Проверяет, доступен ли юзернейм для регистрации.

    Логика:
    1. Спросить Фильтр Блума (быстро, в памяти).
    2. Если `False` -> 100% свободен.
    3. Если `True` -> Возможно занят, надо проверить в БД (медленно).
    """
    if not username or len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Юзернейм слишком короткий.",
        )

    is_available = True

    # Шаг 1: Проверка Фильтром Блума
    if bloom_service.contains(username):
        # Шаг 2: Точная проверка в БД
        if user_service.get_user_by_username(db, username=username) is not None:
            is_available = False

    # Если фильтр сказал False, is_available остается True, и мы не лезем в БД.

    return {"is_available": is_available}