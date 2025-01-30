from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime
from pymongo import MongoClient
from langchain.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseMessage


class ChatHistory:
    def __init__(self, mongodb_uri: str, database: str):
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[database]
        self.conversations = self.db.conversations

    def save_message(self, customer_id: str, role: str, content: str, metadata: Optional[Dict] = None):
        message = {
            "customer_id": customer_id,
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow(),
            "metadata": metadata or {}
        }
        self.conversations.insert_one(message)

    def get_conversation_history(self, customer_id: str, limit: int = 50) -> List[Dict]:
        return list(
            self.conversations.find(
                {"customer_id": customer_id},
                sort=[("timestamp", -1)],
                limit=limit
            )
        )


class ConversationMemory(ConversationBufferMemory):
    def __init__(self, chat_history: ChatHistory, customer_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_history = chat_history
        self.customer_id = customer_id

    def save_context(self, inputs: Dict[str, str], outputs: Dict[str, str]) -> None:
        """Save context from this conversation to buffer and MongoDB."""
        super().save_context(inputs, outputs)
        
        # Save to MongoDB
        self.chat_history.save_message(
            customer_id=self.customer_id,
            role="user",
            content=inputs.get("input", ""),
            metadata={"intent": inputs.get("intent")}
        )
        self.chat_history.save_message(
            customer_id=self.customer_id,
            role="assistant",
            content=outputs.get("output", ""),
            metadata={"intent": inputs.get("intent")}
        )