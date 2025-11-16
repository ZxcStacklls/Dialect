from pybloom_live import BloomFilter
from typing import List
import os
import logging

# Константы для нашего фильтра
EXPECTED_USERNAMES = 1_000_000
FALSE_POSITIVE_RATE = 0.001
FILTER_FILEPATH = "username_filter.bloom"


class BloomFilterService:
    def __init__(self, filepath: str = FILTER_FILEPATH):
        self.filepath = filepath
        self.filter: BloomFilter

        # Попытка загрузить фильтр из файла
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'rb') as f:
                    self.filter = BloomFilter.fromfile(f)
                logging.info(f"Фильтр Блума загружен из {self.filepath}.")
            except Exception as e:
                logging.warning(f"Ошибка загрузки фильтра {self.filepath}: {e}. Создаем новый.")
                self._create_new()
        else:
            logging.info("Файл фильтра Блума не найден. Создаем новый.")
            self._create_new()

    def _create_new(self):
        """Вспомогательный метод для создания пустого фильтра."""
        # ИСПРАВЛЕНИЕ: Мы создаем экземпляр, а не присваиваем класс
        self.filter = BloomFilter(
            capacity=EXPECTED_USERNAMES,
            error_rate=FALSE_POSITIVE_RATE
        )

    def _save(self):
        """Сохраняет состояние фильтра в файл."""
        try:
            with open(self.filepath, 'wb') as f:
                self.filter.tofile(f)
        except Exception as e:
            logging.error(f"Не удалось сохранить фильтр Блума: {e}")

    def add(self, item: str):
        """Добавляет юзернейм в фильтр и сохраняет на диск."""
        if not item:
            return

        item_bytes = item.encode('utf-8')
        if item_bytes not in self.filter:
            self.filter.add(item_bytes)
            self._save()  # Сохраняем при каждом добавлении

    def contains(self, item: str) -> bool:
        """Проверяет, *возможно* ли юзернейм в фильтре."""
        if not item:
            return False
        return item.encode('utf-8') in self.filter

    def sync_from_db(self, usernames: List[str]):
        """
        Полная синхронизация фильтра с базой данных.
        (Вызывается ОДИН РАЗ при старте сервера).
        """
        logging.info(f"Синхронизация {len(usernames)} юзернеймов в фильтр Блума...")

        self.filter = BloomFilter(
            capacity=max(len(usernames) * 2, EXPECTED_USERNAMES),
            error_rate=FALSE_POSITIVE_RATE
        )

        for username in usernames:
            if username:
                self.filter.add(username.encode('utf-8'))

        self._save()
        logging.info("Синхронизация фильтра Блума завершена.")


#
# --- ВАЖНОЕ ДОБАВЛЕНИЕ ---
#
# Создаем тот самый синглтон-экземпляр, который
# импортируется во всем приложении.
#
bloom_service = BloomFilterService()