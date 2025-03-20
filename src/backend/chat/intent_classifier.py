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

