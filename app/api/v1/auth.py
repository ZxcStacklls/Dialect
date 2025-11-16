from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db import schemas, database
from app.services import auth_service
from app.core.security import create_access_token

# Создаем "роутер" - мини-приложение FastAPI для этого модуля.
# prefix="/v1/auth" означает, что все URL в этом файле
# будут начинаться с /api/v1/auth/...
router = APIRouter(
    prefix="/v1/auth",
    tags=["Auth"]  # Тег для авто-документации (Swagger UI)
)

@router.post("/register", response_model=schemas.UserPublic)
def register_user(
    user_data: schemas.UserCreate, 
    db: Session = Depends(database.get_db)
):
    """
    Эндпоинт для регистрации нового пользователя.
    
    Принимает JSON с данными пользователя (схему UserCreate).
    Возвращает публичные данные пользователя (схему UserPublic).
    
    FastAPI автоматически обработает HTTPException, 
    если auth_service его вызовет (н.п. "юзернейм занят").
    """
    new_user = auth_service.register_new_user(db=db, user_data=user_data)
    
    # Мы НЕ возвращаем new_user (т.к. это модель SQLAlchemy с хешем),
    # а возвращаем Pydantic-схему UserPublic, которая сама
    # отфильтрует нужные поля (id, username, first_name и т.д.).
    return new_user


@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db)
):
    """
    Эндпоинт для входа (аутентификации) и получения JWT токена.
    
    Он использует стандарт OAuth2 (form-data), поэтому
    в Swagger UI будет удобная форма для логина.
    
    - form_data.username: Это поле будет содержать номер телефона.
    - form_data.password: Это поле будет содержать пароль.
    """
    
    # ВАЖНО: Мы используем `form_data.username` как `phone_number`
    # для аутентификации, т.к. OAuth2PasswordRequestForm
    # ожидает поле 'username' по стандарту.
    user = auth_service.authenticate_user(
        db=db, 
        phone_number=form_data.username, 
        password=form_data.password
    )
    
    if not user:
        # Если аутентификация не удалась
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный номер телефона или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Если все в порядке, создаем JWT токен
    access_token = create_access_token(user_id=user.id)
    
    return {"access_token": access_token, "token_type": "bearer"}