from typing import Optional
import logging
from pydantic_ai import Agent
from utils.prompt_loader import PromptLoader
from src.backend.models.intent import IntentResult, IntentType
from src.backend.chat.chat_history import ChatHistory

logger = logging.getLogger(__name__)


class IntentClassifier:
    def __init__(self):
        self.prompts = PromptLoader.load_prompts('intent_classifier')
        self.agent = Agent(
            'openai:gpt-4o-mini',
            result_type=IntentResult,
            system_prompt=self.prompts['system_prompt']
        )

    async def _classify_intent(
        self,
        query: str,
        message_history: str
    ) -> IntentResult:
        logger.info(f"Processing query: {query}")

        result = await self.agent.run(
            self.prompts['user_prompt'].format(
                query=query,
                message_history=message_history
            )
        )
        intent_result = result.data

        self.chat_history.add_turn('assistant', intent_result.response)
        logger.info(f"Intent classification result: {result.data}")
        return result

    # async def get_complete_intent(
    #     self,
    #     query: str
    # ) -> IntentResult:
    #     """Get complete intent, gathering missing information if needed"""
    #     # Reset conversation history for new conversation
    #     self.chat_history = ChatHistory()

    #     current_result = await self._classify_intent(query)
    #     intent_result: IntentResult = current_result.data

    #     while intent_result.missing_info:
    #         # Print question asking for missing info
    #         print(intent_result.response)
    #         # Get user's response
    #         user_response = input("User: ")
    #         # Process the response with conversation history
    #         current_result = await self._classify_intent(
    #             user_response,
    #             current_result
    #         )
    #         intent_result = current_result.data
    #         logger.info(f"Updated intent result: {intent_result}")
    #         # If still missing info, continue loop
    #         if intent_result.missing_info:
    #             logger.info(f"Still missing info: {intent_result.missing_info}")

    #     # Return final complete result
    #     logger.info(f"Complete intent identified: {intent_result.intent}")
    #     return intent_result

