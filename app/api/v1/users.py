from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Dict, List

from app.db import database, models, schemas
from app.api.deps import get_current_active_user
from app.services import user_service
from app.services.connection_manager import manager

# Импортируем наш фильтр для проверки юзернейма
from ...core.bloom_filter import bloom_service

router = APIRouter(
    prefix="/v1/users",
    tags=["Users"]
)


# --- 1. Защищенный эндпоинт: "Получить мой профиль" ---
@router.get("/me", response_model=schemas.UserPublic)
def read_users_me(
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Получить данные о текущем, аутентифицированном пользователе.
    """
    # Вручную проверяем онлайн (хотя для себя это всегда True, если мы делаем запрос)
    # Но для единообразия можно оставить
    current_user.is_online = True 
    return current_user


# --- 2. Обновить профиль (PATCH) ---
@router.patch("/me", response_model=schemas.UserPublic)
def update_me(
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Обновить текстовые поля профиля (Био, Имя)."""
    updated_user = user_service.update_user_profile(db, current_user.id, user_update)
    return updated_user


# --- 3. Загрузить аватарку (POST) ---
@router.post("/me/avatar", response_model=schemas.UserPublic)
def upload_my_avatar(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    """Загрузить аватарку (картинку)."""
    # Проверка типа файла
    if not file.content_type.startswith("image/"):
         raise HTTPException(400, detail="Файл должен быть изображением")
         
    user_service.upload_avatar(db, current_user.id, file)
    
    # Возвращаем обновленного пользователя (URL аватарки теперь заполнен)
    # Нужно "обновить" объект current_user, чтобы Pydantic увидел новый avatar_url
    db.refresh(current_user)
    return current_user


# --- 4. Проверка юзернейма ---
@router.get("/check-username/{username}", response_model=Dict[str, bool])
def check_username_availability(
    username: str,
    db: Session = Depends(database.get_db)
):
    if not username or len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Юзернейм слишком короткий.",
        )

    is_available = True

    if bloom_service.contains(username):
        if user_service.get_user_by_username(db, username=username) is not None:
            is_available = False

    return {"is_available": is_available}


# --- 5. Поиск пользователей ---
@router.get("/search", response_model=List[schemas.UserPublic])
def search_for_users(
    q: str,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(database.get_db)
):
    if len(q) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Запрос должен быть не короче 3 символов"
        )
        
    users = user_service.search_users(db, query_str=q)
    return users


# --- 6. Получить чужой профиль по ID ---
@router.get("/{user_id}", response_model=schemas.UserPublic)
def read_user_by_id(
    user_id: int, 
    db: Session = Depends(database.get_db)
):
    user = user_service.get_user(db, user_id)
    if not user: raise HTTPException(404, "User not found")

    # Превращаем в Pydantic модель
    user_public = schemas.UserPublic.from_orm(user)

    # ⭐ ВРУЧНУЮ ПРОВЕРЯЕМ ОНЛАЙН
    user_public.is_online = manager.is_user_online(user.id)

    return user_public