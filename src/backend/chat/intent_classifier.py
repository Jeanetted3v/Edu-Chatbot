from typing import List
import logging
from pydantic_ai import Agent
from utils.prompt_loader import PromptLoader
from models.intent_types import IntentResult

logger = logging.getLogger(__name__)


class IntentClassifier:
    def __init__(self):
        self.prompts = PromptLoader.load_prompts('intent_classifier')
        self.agent = Agent(
            'openai:gpt-4o-mini',
            result_type=IntentResult,
            system_prompt=self.prompts['system_prompt']
        )

    async def classify(
        self,
        query: str,
        conversation_history: List[dict] | None = None
    ) -> IntentResult:
        context = ""
        if conversation_history:
            last_messages = conversation_history[-5:]
            context = "Previous conversation:\n" + "\n".join(
                f"{msg['role']}: {msg['content']}" for msg in last_messages
            )

        prompt = self.prompts['query_analysis_prompt'].format(
            context=context,
            query=query
        )

        # Run the agent
        result = await self.agent.run(prompt)
        
        return result.data