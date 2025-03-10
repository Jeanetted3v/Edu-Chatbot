import logging
from pydantic_ai import Agent
from src.backend.models.intent import IntentResult

logger = logging.getLogger(__name__)


class IntentClassifier:
    def __init__(self, cfg):
        self.prompts = cfg.intent_classifier_prompts
        self.agent = Agent(
            'openai:gpt-4o-mini',
            result_type=IntentResult,
            system_prompt=self.prompts['system_prompt']
        )

    async def classify_intent(
        self,
        query: str,
        message_history: str
    ) -> IntentResult:
        logger.info(f"Processing initial query: {query}")

        result = await self.agent.run(
            self.prompts['user_prompt'].format(
                query=query,
                message_history=message_history
            )
        )
        intent_result = result.data
        logger.info(f"Intent classification result: {intent_result}")
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

