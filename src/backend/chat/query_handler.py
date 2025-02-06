from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime
from pydantic_ai import Agent
import logging

from src.backend.chat.chat_history import ChatHistory
from src.backend.chat.course_service import CourseService
from src.backend.dataloaders.local_doc_loader import LocalDocLoader
from src.backend.dataprocesser.hybrid_search import HybridSearcher
from src.backend.chat.intent_classifier import IntentClassifier
from src.backend.models.general import GeneralResponse
from src.backend.models.intent import IntentResult

logger = logging.getLogger(__name__)


class QueryHandler:
    def __init__(self, csv_path: str):
        self.intent_classifier = IntentClassifier()
        self.course_service = CourseService(csv_path)
        self.chat_history = ChatHistory()
        
    async def _get_intent(
        self,
        query: str
    ) -> IntentResult:
        """Get intent classification with context from chat history"""
        # Add current query to history
        self.chat_history.add_turn('user', query)
        
        # Format history for prompt
        message_history = self.chat_history.format_history_for_prompt()
        
        # Get intent classification
        result = await self.intent_classifier.classify_intent(
            query,
            message_history
        )
        intent_result = result.data
        
        # Add response to history
        self.chat_history.add_turn('assistant', intent_result.response)
        
        return intent_result

    async def handle_query(self, query: str) -> str:
        """Main entry point for handling user queries"""
        try:
            # Reset chat history for new conversation
            self.chat_history = ChatHistory()
            intent_result = await self._get_intent(query)
            
            while True:
                # If we need more information
                if intent_result.missing_info:
                    print(intent_result.response)
                    user_response = input("User: ")
                    intent_result = await self._get_intent(user_response, intent_result)
                    continue
                
                # Once we have all required information, handle the intent
                if intent_result.intent in [
                    IntentType.COURSE_INQUIRY,
                    IntentType.SCHEDULE_INQUIRY,
                    IntentType.FEE_INQUIRY,
                    IntentType.LEVEL_INQUIRY
                ]:
                    # Get message history for context
                    message_history = self.chat_history.format_history_for_prompt()
                    
                    # Get response from course service
                    response = await self.course_service.handle_query(
                        intent_result,
                        message_history
                    )
                else:
                    response = intent_result.response

                # Add final response to chat history
                self.chat_history.add_turn('assistant', response)
                return response
                
        except Exception as e:
            logger.error(f"Error handling query: {e}")
            error_msg = ("抱歉，处理您的询问时出现了错误。请稍后再试或联系我们的客服。" 
                         if any(char in query for char in '你的是我们') 
                         else "Sorry, there was an error processing your query. Please try again later or contact our support.")
            self.chat_history.add_turn('assistant', error_msg)
            return error_msg