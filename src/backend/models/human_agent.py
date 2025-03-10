from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


class MessageRole(str, Enum):
    USER = "user"
    BOT = "bot"
    SYSTEM = "system"
    HUMAN_AGENT = "human_agent"


class AgentType(Enum):
    BOT = "bot"
    HUMAN = "human"


class ChatTurn(BaseModel):
    """Model for a single message in the conversation"""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    customer_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ChatSession(BaseModel):
    session_id: str
    customer_id: str
    current_agent: AgentType = AgentType.BOT
    start_time: datetime = Field(default_factory=datetime.now)
    last_interaction: datetime = Field(default_factory=datetime.now)
    sentiment_score: float = 1.0
    sentiment_confidence: float = 1.0
    message_count: int = 0
    last_analyzed_msg_index: int = 0


class ToggleReason(Enum):
    CUSTOMER_REQUEST = "customer_request"
    AGENT_INITIATED = "agent_initiated"
    SENTIMENT_BASED = "sentiment_based"


class AgentDecision(BaseModel):
    """Used in HumanAgentHandler, process_message method"""
    should_transfer: bool
    response: Optional[str]
    transfer_reason: Optional[ToggleReason] = None


class AnalysisResult(BaseModel):
    """for Message analyzer class"""
    score: float
    confidence: float
    method_used: str
    full_analysis: bool
    triggers_detected: list[str] = None
    analysis_details: Dict = None


# Additional API models using your existing models as base
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
    timestamp: datetime = Field(default_factory=datetime.now)

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
    reason: ToggleReason = ToggleReason.AGENT_INITIATED
    message: Optional[str] = None

# WebSocket message models
class WSMessage(BaseModel):
    """Base model for WebSocket messages"""
    type: str
    session_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class WSChatMessage(WSMessage):
    """WebSocket message containing chat content"""
    type: str = "message"
    role: MessageRole
    content: str
    customer_id: str
    metadata: Optional[Dict[str, Any]] = None

class WSSystemNotification(WSMessage):
    """WebSocket notification for system events"""
    type: str = "system"
    message: str
    event: str  # 'handover', 'transfer_to_bot', 'error', etc.
    data: Optional[Dict[str, Any]] = None
