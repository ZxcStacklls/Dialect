import logging
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import os   

# --- Импорты наших компонентов ---
from app.db import database, models
from app.core.bloom_filter import bloom_service
from app.services import user_service

# --- Импорты наших роутеров (API) ---
from app.api.v1 import auth as auth_v1
from app.api.v1 import users as users_v1
from app.api.v1 import auth as auth_v1
from app.api.v1 import chats as chats_v1
from app.api.v1 import messages as messages_v1

# Настраиваем базовый логгер
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not os.path.exists("uploads"):
    os.makedirs("uploads")

# --- События "при старте" / "при выключении" ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер Lifespan (новый способ в FastAPI)
    выполняется при старте и остановке приложения.
    """
    logger.info("Приложение запускается...")

    # --- 1. Создание таблиц БД ---
    # Вызываем нашу функцию из database.py
    logger.info("Проверка и создание таблиц в БД...")
    database.create_all_tables()
    logger.info("Таблицы проверены.")

    # --- 2. Синхронизация Фильтра Блума ---
    logger.info("Загрузка юзернеймов в Фильтр Блума...")
    # Нам нужна сессия БД только для этой операции
    db = database.SessionLocal()
    try:
        # Получаем ВСЕ username из БД
        users_with_usernames = db.query(models.User.username) \
            .filter(models.User.username.isnot(None)) \
            .all()

        # 'all()' вернет список кортежей, н.п. [('john',), ('alice',)]
        all_usernames = [u[0] for u in users_with_usernames]

        # Загружаем их в сервис фильтра
        bloom_service.sync_from_db(all_usernames)

    except Exception as e:
        logger.error(f"Ошибка при синхронизации Фильтра Блума: {e}")
    finally:
        db.close()

    # Приложение готово к работе
    yield

    # --- Код "при выключении" ---
    logger.info("Приложение останавливается...")


# --- Создание основного приложения ---

app = FastAPI(
    title="Dialect Messenger API",
    version="1.0.0",
    lifespan=lifespan  # Подключаем нашу логику старта
)

# --- Подключение API-роутеров ---

# Роутер для авторизации (/api/v1/auth/...)
app.include_router(auth_v1.router, prefix="/api")

# Роутер для пользователей (/api/v1/users/...)
app.include_router(users_v1.router, prefix="/api")

# Роутер для чатов (/api/v1/chats/...)
app.include_router(chats_v1.router, prefix="/api")

# Роутер для сообщений (/api/v1/messages/...)
app.include_router(messages_v1.router, prefix="/api")

# Подключаем раздачу файлов из папки uploads/
app.mount("/static", StaticFiles(directory="uploads"), name="static")


# --- Тестовый эндпоинт ---
@app.get("/")
def read_root():
    """Простой эндпоинт для проверки, что сервер жив."""
    return {"message": "Welcome to Dialect Messenger API V1"}