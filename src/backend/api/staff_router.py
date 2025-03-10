# routers/staff_router.py
import logging
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Body, Query

from pydantic import BaseModel
from service_container import ServiceContainer
from models import ChatSession, AgentType, MessageRole, ChatTurn, ToggleReason

from dependencies import get_service_container

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Models for staff API
class StaffMessageRequest(BaseModel):
    """Request model for staff sending a message"""
    session_id: str
    customer_id: str
    message: str

class MessageResponse(BaseModel):
    """Response model for message API"""
    message: str
    session_id: str
    customer_id: str
    role: MessageRole
    current_agent: AgentType
    timestamp: datetime

class SessionResponse(BaseModel):
    """API response model for session info"""
    session_id: str
    customer_id: str
    current_agent: AgentType
    start_time: datetime
    last_interaction: datetime
    message_count: int
    
class TransferRequest(BaseModel):
    """Request model for transferring back to bot"""
    session_id: str
    customer_id: str
    message: str = "Transferring back to automated assistant."

# Staff routes
@router.get("/sessions/active", response_model=List[SessionResponse])
async def get_active_sessions(
    services: ServiceContainer = Depends(get_service_container)
):
    """Get all active chat sessions for staff to view"""
    try:
        result = []
        for session_id, session in services.active_sessions.items():
            session_response = SessionResponse(
                session_id=session.session_id,
                customer_id=session.customer_id,
                current_agent=session.current_agent,
                start_time=session.start_time,
                last_interaction=session.last_interaction,
                message_count=session.message_count
            )
            result.append(session_response)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting active sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/message", response_model=MessageResponse)
async def staff_send_message(
    message_request: StaffMessageRequest,
    services: ServiceContainer = Depends(get_service_container)
):
    """Send a message from the human agent to the customer"""
    try:
        session_id = message_request.session_id
        customer_id = message_request.customer_id
        message = message_request.message
        
        # Get session
        session = await services.get_or_create_session(session_id, customer_id)
        chat_history = await services.get_chat_history(session_id, customer_id)
        
        # Ensure session is in human agent mode
        if session.current_agent != AgentType.HUMAN:
            session.current_agent = AgentType.HUMAN
            await services.human_handler.transfer_to_human(
                session_id,
                ToggleReason.AGENT_INITIATED
            )
        
        # Add message to chat history
        await chat_history.add_turn(MessageRole.HUMAN_AGENT, message)
        
        # Update session last interaction time
        session.last_interaction = datetime.now()
        
        # If integrated with WhatsApp, send message via WhatsApp API
        # This would depend on your WhatsApp integration
        # await send_whatsapp_message(customer_id, message)
        
        return MessageResponse(
            message=message,
            session_id=session_id,
            customer_id=customer_id,
            role=MessageRole.HUMAN_AGENT,
            current_agent=AgentType.HUMAN,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error sending human agent message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transfer/bot", response_model=MessageResponse)
async def transfer_to_bot(
    transfer_request: TransferRequest,
    services: ServiceContainer = Depends(get_service_container)
):
    """Transfer conversation from human agent back to bot"""
    try:
        session_id = transfer_request.session_id
        customer_id = transfer_request.customer_id
        custom_message = transfer_request.message
        
        # Get session and chat history
        session = await services.get_or_create_session(session_id, customer_id)
        chat_history = await services.get_chat_history(session_id, customer_id)
        
        # Only proceed if currently in human mode
        if session.current_agent != AgentType.HUMAN:
            return MessageResponse(
                message="Session already handled by bot",
                session_id=session_id,
                customer_id=customer_id,
                role=MessageRole.SYSTEM,
                current_agent=AgentType.BOT,
                timestamp=datetime.now()
            )
        
        # Transfer to bot using your handler
        transfer_message = await services.human_handler.transfer_to_bot(
            session_id,
            chat_history
        )
        
        # If custom message provided, use that instead
        if custom_message:
            transfer_message = custom_message
        
        # Update session agent type
        session.current_agent = AgentType.BOT
        
        # Add system message to chat history
        await chat_history.add_turn(MessageRole.SYSTEM, transfer_message)
        
        return MessageResponse(
            message=transfer_message,
            session_id=session_id,
            customer_id=customer_id,
            role=MessageRole.SYSTEM,
            current_agent=AgentType.BOT,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error transferring to bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/history")
async def get_chat_history_for_staff(
    session_id: str,
    customer_id: str,
    limit: int = Query(50, ge=1, le=100),
    services: ServiceContainer = Depends(get_service_container)
):
    """Get conversation history for a session (staff view)"""
    try:
        chat_history = await services.get_chat_history(session_id, customer_id)
        history = await chat_history.get_last_n_turns(limit)
        
        # Convert to API format
        result = []
        for turn in history:
            chat_turn = ChatTurn(
                role=turn.get("role", MessageRole.SYSTEM),
                content=turn.get("content", ""),
                timestamp=turn.get("timestamp", datetime.now()),
                customer_id=customer_id,
                session_id=session_id,
                metadata=turn.get("metadata")
            )
            result.append(chat_turn)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting chat history for staff: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/takeover", response_model=MessageResponse)
async def take_over_session(
    session_id: str = Body(...),
    customer_id: str = Body(...),
    message: str = Body(None),
    services: ServiceContainer = Depends(get_service_container)
):
    """Staff manually takes over a session that's currently handled by bot"""
    try:
        # Get session
        session = await services.get_or_create_session(session_id, customer_id)
        chat_history = await services.get_chat_history(session_id, customer_id)
        
        # Skip if already in human mode
        if session.current_agent == AgentType.HUMAN:
            return MessageResponse(
                message="Session already handled by human agent",
                session_id=session_id,
                customer_id=customer_id,
                role=MessageRole.SYSTEM,
                current_agent=AgentType.HUMAN,
                timestamp=datetime.now()
            )
        
        # Get or customize takeover message
        takeover_message = "A customer support agent has joined the conversation."
        if message:
            takeover_message = message
        
        # Transfer to human
        await services.human_handler.transfer_to_human(
            session_id,
            ToggleReason.AGENT_INITIATED
        )
        
        # Update session
        session.current_agent = AgentType.HUMAN
        
        # Add system message
        await chat_history.add_turn(MessageRole.SYSTEM, takeover_message)
        
        return MessageResponse(
            message=takeover_message,
            session_id=session_id,
            customer_id=customer_id,
            role=MessageRole.SYSTEM,
            current_agent=AgentType.HUMAN,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error taking over session: {e}")
        raise HTTPException(status_code=500, detail=str(e))