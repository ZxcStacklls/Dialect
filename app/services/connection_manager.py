from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Словарь: user_id -> WebSocket соединение
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """Принимает соединение и запоминает пользователя."""
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        """Удаляет пользователя из списка активных при разрыве."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: int):
        """
        Отправляет сообщение конкретному пользователю, если он онлайн.
        """
        if user_id in self.active_connections:
            connection = self.active_connections[user_id]
            # Отправляем JSON данные
            await connection.send_json(message)
            return True
        return False

# Создаем глобальный экземпляр менеджера
manager = ConnectionManager()