from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings # Импортируем наши настройки
from app.db.models import Base # Импортируем Base из models.py
import logging

# 1. Создаем "Движок" (Engine)
# Он управляет пулом подключений к БД.
# Мы используем DATABASE_URL, который собрали в config.py
try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,  # Проверять соединение перед запросом
        pool_recycle=3600    # Переподключаться каждый час
    )
    logging.info("Соединение с БД (Engine) успешно создано.")

except Exception as e:
    logging.error(f"Ошибка при создании Engine для БД: {e}")
    # Если мы не можем подключиться к БД, приложение не должно стартовать.
    raise

# 2. Создаем "Фабрику Сессий"
# Этот SessionLocal будет создавать новые сессии (Session) для каждого запроса.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 3. Функция-зависимость (Dependency) для FastAPI
def get_db() -> Session:
    """
    Эта функция-зависимость будет вызываться для каждого API-запроса,
    который требует доступа к БД.
    Она открывает сессию, выполняет запрос и гарантированно закрывает сессию,
    даже если произошла ошибка.
    """
    db = SessionLocal()
    try:
        yield db # Возвращаем сессию в API-эндпоинт
    finally:
        db.close() # Закрываем сессию после того, как эндпоинт отработал

# --- Функция для создания таблиц ---
def create_all_tables():
    """
    Вспомогательная функция для создания всех таблиц в БД,
    описанных в app/db/models.py.
    (Мы вызовем ее один раз при старте приложения в main.py)
    """
    try:
        print("Создание таблиц в БД (если их нет)...")
        Base.metadata.create_all(bind=engine)
        print("Таблицы успешно созданы/проверены.")
    except Exception as e:
        print(f"Ошибка при создании таблиц: {e}")
        raise