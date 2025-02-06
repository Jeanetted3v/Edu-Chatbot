from typing import List, Optional
import pandas as pd
import logging
from src.backend.models.intent import IntentResult
from src.backend.dataloaders.local_doc_loader import LocalDocLoader, LoadedStructuredDocument
from utils.prompt_loader import PromptLoader
from pydantic_ai import Agent

logger = logging.getLogger(__name__)


class CourseService:
    def __init__(self, csv_path: str):
        self.df = pd.read_csv(csv_path, encoding='utf-8-sig')
        self.prompts = PromptLoader.load_prompts('course_service')
        self.agent = Agent(
            'openai:gpt-4o-mini',
            result_type=CourseMatch,
            system_prompt=self.prompts['system_prompt']
        )

    def _get_available_courses(self, age: int) -> str:
        """Get age-appropriate courses as JSON string"""
        age_filtered = self.df[
            (self.df['min_age'] <= age) & 
            (self.df['max_age'] >= age)
        ]
        return age_filtered.to_json(orient='records', force_ascii=False, indent=2)

    async def handle_query(
        self,
        intent_result: IntentResult,
        message_history: str
    ) -> str:
        age = intent_result.parameters.age
        courses_json = self._get_available_courses(age)

        base_context = self.prompts['base_context'].format(
            message_history=message_history,
            age=age,
            courses_json=courses_json,
            intent_result=intent_result.json(indent=2)
        )

        prompt_key = f"{intent_result.intent.value}"
        if prompt_key not in self.prompts:
            return "Unsupported intent type"

        prompt = self.prompts[prompt_key].format(base_context=base_context)
        response = await self.agent.run(prompt)
        return response