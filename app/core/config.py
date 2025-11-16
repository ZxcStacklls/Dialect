from pydantic_settings import BaseSettings
from pydantic import computed_field
from typing import Optional

class Settings(BaseSettings):
    """
    Класс для загрузки настроек приложения из .env файла.
    """
    
    # --- Настройки БД (из .env) ---
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int = 3306
    DB_NAME: str

    # --- Настройки JWT (из .env) ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 # 1 час

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        """
        Собирает URL для подключения к MySQL из отдельных переменных.
        Формат: mysql+pymysql://user:password@host:port/dbname
        """
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        # Указываем Pydantic, что нужно читать переменные из файла .env
        env_file = ".env"
        env_file_encoding = "utf-8"

# Создаем ЕДИНСТВЕННЫЙ экземпляр настроек,
# который будет импортироваться во всем приложении.
# При первом импорте он автоматически прочитает .env файл.
settings = Settings()

# --- Для проверки, что все работает ---
if __name__ == "__main__":
    print("Настройки загружены:")
    print(f"URL Базы данных: {settings.DATABASE_URL}")
    print(f"Секретный ключ: {settings.SECRET_KEY[:4]}...")