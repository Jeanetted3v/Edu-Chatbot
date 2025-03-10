from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ChatMessage(BaseModel):
    content: str
    sender: str
    session_id: str
    timestamp: Optional[datetime] = None


class ChatSession(BaseModel):
    session_id: str
    is_human_agent: bool
    start_time: datetime
    last_active: datetime
