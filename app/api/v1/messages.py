from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db import database, schemas, models
from app.services import message_service, connection_manager
from app.core import security

# Импортируем наш менеджер соединений
from app.services.connection_manager import manager

router = APIRouter(
    prefix="/v1/messages",
    tags=["Messages"]
)

# --- Хелпер для авторизации в WebSocket ---
def get_user_from_token(token: str, db: Session):
    """Проверяет токен из URL и возвращает user_id."""
    try:
        payload = security.verify_and_decode_token(token)
        return payload.user_id
    except Exception:
        return None


# 🟢 1. WebSocket Эндпоинт (Живое общение)
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...), # Токен берем из ?token=...
    db: Session = Depends(database.get_db)
):
    # 1. Проверка авторизации
    user_id = get_user_from_token(token, db)
    if user_id is None:
        await websocket.close(code=1008) # Policy Violation
        return

    # 2. Подключаем пользователя
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # 3. Ждем сообщение от клиента
            # Клиент шлет JSON: {"chat_id": 1, "content": "encrypted_base64..."}
            data = await websocket.receive_json()
            
            # Валидируем данные через Pydantic (вручную)
            try:
                msg_create = schemas.MessageCreate(**data)
            except Exception:
                await websocket.send_json({"error": "Invalid data format"})
                continue

            # 4. СОХРАНЯЕМ В БД (Cloud History)
            # Это делает переписку независимой от устройства
            new_msg = message_service.create_message(
                db=db, 
                sender_id=user_id, 
                msg_data=msg_create
            )

            # 5. Рассылка участникам (Real-time)
            # Получаем список ID участников этого чата
            participant_ids = message_service.get_chat_participants(db, chat_id=msg_create.chat_id)
            
            # Формируем ответ для отправки
            response_data = {
                "id": new_msg.id,
                "chat_id": new_msg.chat_id,
                "sender_id": user_id,
                "content": new_msg.content.decode('utf-8') if isinstance(new_msg.content, bytes) else new_msg.content,
                "sent_at": new_msg.sent_at.isoformat(),
                "status": "sent"
            }

            # Отправляем ВСЕМ участникам, кто сейчас онлайн (включая себя, чтобы обновить UI)
            for pid in participant_ids:
                await manager.send_personal_message(response_data, pid)
                
    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        print(f"Error in websocket: {e}")
        manager.disconnect(user_id)


# 🔵 2. HTTP Эндпоинт (Загрузка истории)
@router.get("/history/{chat_id}", response_model=List[schemas.Message])
def get_chat_history(
    chat_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(database.get_db)
    # Сюда можно добавить get_current_user для проверки доступа к чату
):
    """
    Этот эндпоинт вызывает клиент, когда открывает чат,
    чтобы подгрузить старые сообщения из БД.
    """
    return message_service.get_chat_history(db, chat_id, limit, offset)