# routers/webhook_router.py
import logging
import hashlib
from typing import Dict, Any
from fastapi import APIRouter, Depends, Body, HTTPException

from service_container import ServiceContainer
from models import AgentType, MessageRole

from dependencies import get_service_container

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Placeholder for sending WhatsApp messages
async def send_whatsapp_message(to: str, message: str):
    """
    Placeholder for sending WhatsApp messages
    You would replace this with your actual WhatsApp API integration
    """
    logger.info(f"Sending WhatsApp message to {to}: {message}")
    # Your actual WhatsApp API code would go here
    return True

@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    data: Dict[str, Any] = Body(...),
    services: ServiceContainer = Depends(get_service_container)
):
    """Webhook for WhatsApp messages"""
    try:
        # This structure will depend on your WhatsApp integration
        # Example for a simple integration:
        if "message" in data:
            # Extract customer ID (phone number), message, etc.
            customer_id = data.get("from", "unknown")
            message_text = data.get("message", {}).get("text", "")
            
            # Skip empty messages
            if not message_text:
                return {"status": "ignored", "reason": "empty message"}
            
            # Generate session ID from phone number if needed
            session_id = f"wa_{hashlib.md5(customer_id.encode()).hexdigest()}"
            
            # Process the message using the existing handler
            response = await services.query_handler.handle_query(
                message_text,
                session_id,
                customer_id
            )
            
            # Get updated session to check agent type
            session = await services.get_or_create_session(session_id, customer_id)
            
            # Send response back to WhatsApp
            await send_whatsapp_message(customer_id, response)
            
            # If transferred to human agent, notify staff
            if session.current_agent == AgentType.HUMAN:
                # In a real implementation, you might send a notification
                # to the staff interface (email, Slack, SMS, etc.)
                logger.info(f"WhatsApp session {session_id} transferred to human agent")
            
            return {"status": "success"}
            
        return {"status": "ignored", "reason": "no message found"}
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {e}")
        return {"status": "error", "message": str(e)}