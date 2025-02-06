from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime
from pydantic_ai import Agent
import logging

from src.backend.chat.chat_history import ChatHistory
from src.backend.chat.course_service import CourseService
from src.backend.chat.intent_classifier import IntentClassifier
from src.backend.models.intent import IntentResult

logger = logging.getLogger(__name__)


class QueryHandler:
    def __init__(self, csv_path: str, cfg):
        self.intent_classifier = IntentClassifier(cfg)
        self.course_service = CourseService(csv_path, cfg)
        self.chat_history = ChatHistory()
        
    async def _get_intent(
        self,
        query: str
    ) -> IntentResult:
        """Get intent classification with context from chat history"""
        self.chat_history.add_turn('user', query)
        message_history = self.chat_history.format_history_for_prompt()
        logger.info(f"Message History: {message_history}")
        result = await self.intent_classifier.classify_intent(
            query,
            message_history
        )
        intent_result = result.data
        self.chat_history.add_turn('assistant', intent_result.response)
        return intent_result

    async def handle_query(self, query: str) -> str:
        """Main entry point for handling user queries"""
        try:
            self.chat_history = ChatHistory()  # Reset history for new convo
            intent_result = await self._get_intent(query)
            logger.info(f"Intent Result: {intent_result}")
            
            while True:
                if intent_result.missing_info:
                    print(intent_result.response)
                    user_response = input("User: ")
                    intent_result = await self._get_intent(
                        user_response)
                    self.chat_history.add_turn('user', user_response)
                    self.chat_history.add_turn('assistant', intent_result.response)
                    continue
                
                message_history = self.chat_history.format_history_for_prompt()
                logger.info(f"Message History: {message_history}")
                response = await self.course_service.handle_course_query(
                    intent_result,
                    message_history
                )
                logger.info(f"Response: {response}")
                self.chat_history.add_turn('assistant', response)
                return response
                
        except Exception as e:
            logger.error(f"Error handling query: {e}")
            error_msg = ("抱歉，处理您的询问时出现了错误。请稍后再试或联系我们的客服。" 
                         if any(char in query for char in '你的是我们') 
                         else "Sorry, there was an error processing your query. Please try again later or contact our support.")
            self.chat_history.add_turn('assistant', error_msg)
            return error_msg