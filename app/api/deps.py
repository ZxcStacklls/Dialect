from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, ExpiredSignatureError

from app.db import database, models, schemas
from app.core import security
from app.services import user_service

# Эта строка создает "схему" для FastAPI.
# "tokenUrl" указывает, что токен можно получить по адресу "/api/v1/auth/token".
# FastAPI будет автоматически искать заголовок 'Authorization: Bearer <token>'
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(database.get_db)
) -> models.User:
    """
    Зависимость (Dependency) для FastAPI.

    1. Принимает 'token' из заголовка (через oauth2_scheme).
    2. Принимает сессию 'db' (через get_db).
    3. Проверяет токен.
    4. Загружает пользователя из БД.
    5. Возвращает объект models.User или выбрасывает ошибку 401.
    """

    # Исключение, если токен невалидный (включая протухший)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # 1. Расшифровываем токен
        token_data = security.verify_and_decode_token(token)

        if token_data.user_id is None:
            raise credentials_exception

    except ExpiredSignatureError:
        # Отдельно ловим протухший токен
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен истек",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        # Любая другая ошибка (неверная подпись и т.д.)
        raise credentials_exception

    # 2. Загружаем пользователя из БД
    user = user_service.get_user(db, user_id=token_data.user_id)

    if user is None:
        # Если токен верный, но юзера уже удалили из БД
        raise credentials_fallback_exception

    # 3. Возвращаем полную модель пользователя
    return user


def get_current_active_user(
        current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    Эта зависимость просто вызывает get_current_user.
    В будущем сюда можно добавить проверку (if not current_user.is_active: ...).
    Пока она просто для красоты и правильной архитектуры.
    """
    # if not current_user.is_active:
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user