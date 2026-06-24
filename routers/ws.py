from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from database import get_db
# pyrefly: ignore [missing-import]
from services.auth_service import decode_token, get_user_by_id
# pyrefly: ignore [missing-import]
from services.websocket_manager import manager

router = APIRouter(tags=["websocket"])

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    # Authenticate token
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=1008)
        return
        
    user_id = payload.get("user_id")
    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        await websocket.close(code=1008)
        return
        
    # Tenant ID is essential for isolating broadcasts
    tenant_id = user.tenant_id
    if not tenant_id:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, tenant_id, user_id)
    try:
        while True:
            # We don't expect messages from the client right now,
            # but we need to keep the loop open to listen for disconnects
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, tenant_id)
