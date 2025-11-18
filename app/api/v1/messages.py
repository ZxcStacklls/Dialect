from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Any
from pydantic import ValidationError

from app.db import database, schemas, models
from app.services import message_service
from app.services.connection_manager import manager
from app.core import security

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
    except Exception as e:
        print(f"❌ ОШИБКА АВТОРИЗАЦИИ WEBSOCKET: {e}")
        return None


# 🔵 2. HTTP Эндпоинт (Загрузка истории)
@router.get("/history/{chat_id}", response_model=List[schemas.Message])
def get_chat_history(
    chat_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(database.get_db)
):
    return message_service.get_chat_history(db, chat_id, limit, offset)


# 🟢 1. WebSocket Эндпоинт (Живое общение)
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...), 
    db: Session = Depends(database.get_db)
):
    # 1. Проверка авторизации
    user_id = get_user_from_token(token, db)
    if user_id is None:
        await websocket.close(code=1008)
        return

    # 2. Подключаем пользователя
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # 3. Ждем сообщение
            data: Dict[str, Any] = await websocket.receive_json()
            event_type = data.get("type")
            
            # --- РОУТИНГ СОБЫТИЙ ---
            
            # === 1. НОВОЕ СООБЩЕНИЕ (type: "new_message" или отсутствует) ===
            if event_type in (None, "new_message"):
                try:
                    # Конвертация строки в байты (для Pydantic)
                    raw_content = data.get("content")
                    if isinstance(raw_content, str):
                        raw_content = raw_content.encode('utf-8')

                    msg_create = schemas.MessageCreate(
                        chat_id=data.get("chat_id"),
                        content=raw_content
                    )
                    
                    new_msg = message_service.create_message(
                        db=db, 
                        sender_id=user_id, 
                        msg_data=msg_create
                    )

                    response_data = {
                        "type": "new_message",
                        "id": new_msg.id,
                        "chat_id": new_msg.chat_id,
                        "sender_id": user_id,
                        "content": new_msg.content.decode('utf-8') if isinstance(new_msg.content, bytes) else new_msg.content,
                        "sent_at": new_msg.sent_at.isoformat(),
                        "status": "sent"
                    }

                    participant_ids = message_service.get_chat_participants(db, chat_id=new_msg.chat_id)
                    for pid in participant_ids:
                        await manager.send_personal_message(response_data, pid)
                        
                except Exception as e:
                    await websocket.send_json({"error": f"Message error: {str(e)}"})


            # === 2. ПРОЧИТАНО (READ) ===
            elif event_type == "read":
                chat_id = data.get("chat_id")
                msg_id = data.get("message_id")
                
                if chat_id and msg_id:
                    message_service.mark_messages_as_read(db, chat_id, user_id, msg_id)
                    read_notification = {
                        "type": "message_read",
                        "chat_id": chat_id,
                        "user_id": user_id,
                        "last_read_id": msg_id
                    }
                    parts = message_service.get_chat_participants(db, chat_id=chat_id)
                    for pid in parts:
                        if pid != user_id:
                            await manager.send_personal_message(read_notification, pid)


            # === 3. РЕДАКТИРОВАНИЕ (EDIT) ===
            elif event_type == "edit":
                try:
                    msg_id = data.get("message_id")
                    new_text = data.get("content")
                    
                    if not msg_id or not new_text:
                        raise ValueError("Fields 'message_id' and 'content' are required")

                    # Приведение типов
                    if isinstance(msg_id, float): msg_id = int(msg_id)
                    if isinstance(new_text, str): new_text = new_text.encode('utf-8')

                    updated_msg = message_service.update_message(db, msg_id, user_id, new_text)
                    
                    if updated_msg:
                        edit_notify = {
                            "type": "message_edited",
                            "chat_id": updated_msg.chat_id,
                            "message_id": updated_msg.id,
                            "new_content": updated_msg.content.decode('utf-8')
                        }
                        parts = message_service.get_chat_participants(db, chat_id=updated_msg.chat_id)
                        for pid in parts:
                            await manager.send_personal_message(edit_notify, pid)
                    else:
                        await websocket.send_json({"error": "Edit failed: Not found or forbidden"})
                
                except Exception as e:
                    await websocket.send_json({"error": f"Edit error: {str(e)}"})


            # === 4. УДАЛЕНИЕ (DELETE) ===
            elif event_type == "delete":
                try:
                    msg_id = data.get("message_id")
                    if not msg_id:
                        raise ValueError("Field 'message_id' is required")
                        
                    if isinstance(msg_id, float): msg_id = int(msg_id)

                    # Сначала ищем, чтобы узнать chat_id (нужен для рассылки)
                    msg_obj = db.query(models.Message).filter(models.Message.id == msg_id).first()

                    if msg_obj and msg_obj.sender_id == user_id:
                        target_chat_id = msg_obj.chat_id
                        success = message_service.delete_message(db, msg_id, user_id)
                        
                        if success:
                            delete_notify = {
                                "type": "message_deleted",
                                "chat_id": target_chat_id,
                                "message_id": msg_id
                            }
                            parts = message_service.get_chat_participants(db, chat_id=target_chat_id)
                            for pid in parts:
                                await manager.send_personal_message(delete_notify, pid)
                    else:
                         await websocket.send_json({"error": "Delete failed: Not found or forbidden"})

                except Exception as e:
                    await websocket.send_json({"error": f"Delete error: {str(e)}"})

            # === 5. НЕИЗВЕСТНЫЙ ТИП ===
            else:
                await websocket.send_json({"error": f"Unknown event type: {event_type}"})

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        print(f"WebSocket Error: {e}")
        manager.disconnect(user_id)