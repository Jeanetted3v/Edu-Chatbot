# src/backend/api/websocket_router.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from datetime import datetime
import json
from starlette.websockets import WebSocketState
from src.backend.api.deps import get_websocket_service_container
from src.backend.chat.service_container import ServiceContainer
from src.backend.websocket.manager import manager
from src.backend.api.utils_router import human_takeover
from src.backend.models.human_agent import ToggleReason
from src.backend.models.api import MessageRole, AgentType
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Helper functions for WebSocket message handling
async def handle_customer_message(
    services, session_id, customer_id, content, manager
):
    """Process a message from a customer via WebSocket"""
    # Use existing handle_query function
    response = await services.query_handler.handle_query(
        content,
        session_id,
        customer_id
    )
    
    # Get the updated session
    session = await services.get_or_create_session(session_id, customer_id)
    
    # Determine response role
    response_role = (
        MessageRole.HUMAN_AGENT 
        if session.current_agent == AgentType.HUMAN 
        else MessageRole.BOT
    )
    
    # Broadcast the customer's message to all connections
    await manager.broadcast_to_session(
        session_id,
        {
            "type": "new_message",
            "message": {
                "role": MessageRole.USER,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "customer_id": customer_id
            }
        }
    )
    
    # Broadcast the response to all connections
    await manager.broadcast_to_session(
        session_id,
        {
            "type": "new_message",
            "message": {
                "role": response_role,
                "content": response,
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "customer_id": customer_id
            }
        }
    )


async def handle_staff_message(
    services, session_id, customer_id, content, manager
):
    """Process a message from a staff member via WebSocket"""
    # Get session
    session = await services.get_or_create_session(session_id, customer_id)
    chat_history = await services.get_chat_history(session_id, customer_id)
    
    # Ensure session is in human agent mode
    if session.current_agent != AgentType.HUMAN:
        await human_takeover(
            session_id=session_id,
            reason=ToggleReason.AGENT_INITIATED,
            services=services
        )
    
    # Add message to chat history
    await chat_history.add_turn(MessageRole.HUMAN_AGENT, content)
    
    # Update session last interaction time
    session.last_interaction = datetime.now()
    
    # Broadcast the staff message to all connections
    await manager.broadcast_to_session(
        session_id,
        {
            "type": "new_message",
            "message": {
                "role": MessageRole.HUMAN_AGENT,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "session_id": session_id,
                "customer_id": customer_id
            }
        }
    )


# Then in your WebSocket endpoint:
@router.websocket("/chat/{session_id}/{client_type}")
async def websocket_endpoint(
    websocket: WebSocket, 
    session_id: str,
    client_type: str, 
    services: ServiceContainer = Depends(get_websocket_service_container)
):
    try:
        # Connect the WebSocket
        await manager.connect(websocket, session_id, client_type)
        
        # Send initial chat history
        chat_history = await services.get_chat_history(session_id, None)
        recent_messages = await chat_history.get_recent_turns(50)
        
        # Format messages for the client
        formatted_messages = [
            {
                "role": msg.get("role", "unknown"),
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp").isoformat() if msg.get("timestamp") else "",
                "customer_id": msg.get("customer_id", ""),
                "session_id": msg.get("session_id", "")
            }
            for msg in recent_messages
        ]
        
        await websocket.send_json({
            "type": "history",
            "messages": formatted_messages
        })
        
        # Keep connection alive, handle client messages
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle different message types
            if message_data.get("type") == "message":
                content = message_data.get("content")
                customer_id = message_data.get("customer_id", "")
                
                if client_type == "customer":
                    await handle_customer_message(services, session_id, customer_id, content, manager)
                elif client_type == "staff":
                    await handle_staff_message(services, session_id, customer_id, content, manager)
            
    except WebSocketDisconnect:
        await manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close(code=1011)  # 1011 = Internal Error