from typing import List
import logging
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends, Body, Query

from pydantic import BaseModel
from service_container import ServiceContainer
from models import ChatSession, AgentType, MessageRole, ChatTurn, ToggleReason
from src.api.deps import get_service_container

# Set up logging
logger = logging.getLogger(__name__)
router = APIRouter()

# Models for API
class MessageRequest(BaseModel):
    """Request model for sending a message"""
    message: str
    session_id: str
    customer_id: str
    source: str = "api"  # 'api', 'whatsapp', 'web', etc.

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

class HandoverRequest(BaseModel):
    """Request model for handover operations"""
    session_id: str
    customer_id: str
    reason: str = "Customer requested assistance"


async def check_session(customer_id: str, services: ServiceContainer) -> str:
    """
    Check if a recent active session exists for a customer.
    If yes, return that session_id. If not, create a new session_id.
    
    Args:
        customer_id: The customer's unique identifier
        services: The service container instance
        
    Returns:
        str: The session_id to use
    """
    # Get session timeout from config or use default
    session_timeout_hours = (
        services.cfg.session.timeout_hours
        if hasattr(services.cfg, 'session')
        and hasattr(services.cfg.session, 'timeout_hours')
        else 24
    )
    
    # Check for recent active session
    recent_session = None
    for sess_id, sess in services.active_sessions.items():
        if sess.customer_id == customer_id:
            # Calculate hours since last interaction
            hours_since_last = (datetime.now() - sess.last_interaction).total_seconds() / 3600
            if hours_since_last < session_timeout_hours:
                recent_session = sess
                break
    
    if recent_session:
        # Use recent session
        session_id = recent_session.session_id
        logger.info(f"Using recent session {session_id} for customer {customer_id}")
    else:
        # Create new session
        session_id = str(uuid4())
        logger.info(f"Creating new session {session_id} for customer {customer_id}")
    
    return session_id


@router.post("/message", response_model=MessageResponse)
async def customer_router(
    message_request: MessageRequest,
    services: ServiceContainer = Depends(get_service_container)
):
    """Main endpoint, Send a message and get a response
    
    Routes message to handle_query funciton.
    Being called whenevr a customer sends a message in the chat interface.
    """
    try:
        customer_id = message_request.customer_id
        session_id = message_request.session_id
        source = message_request.source
        message = message_request.message

        if not session_id:
            session_id = await check_session(customer_id, services)
        
        # Get or create session with the determined session_id
        session = await services.get_or_create_session(session_id, customer_id)
        
        # Process the message using your existing query handler
        response = await services.query_handler.handle_query(
            message,
            session_id,
            customer_id
        )
        
        # Determine the response role based on current agent
        response_role = MessageRole.HUMAN_AGENT if session.current_agent == AgentType.HUMAN else MessageRole.BOT
        
        return MessageResponse(
            message=response,
            session_id=session_id,
            customer_id=customer_id,
            role=response_role,
            current_agent=session.current_agent,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


