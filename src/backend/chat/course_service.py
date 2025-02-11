from typing import Dict
import pandas as pd
import logging
from src.backend.utils.llm import LLM
from src.backend.models.intent import IntentResult, IntentType
from src.backend.chat.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)


class CourseService:
    def __init__(self, csv_path: str, cfg: Dict):
        self.df = pd.read_csv(csv_path, encoding='utf-8-sig')
        self.prompts = cfg.course_service
        self.llm = LLM()
        self.hybrid_retriever = HybridRetriever(
            cfg,
            cfg.hybrid_retriever.persist_dir,
            cfg.hybrid_retriever.collection
        )

    def _get_available_courses(self, age: int) -> str:
        """Get age-appropriate courses as JSON string"""
        if not isinstance(age, int) or age < 0:
            raise ValueError(f"Invalid age value: {age}")
        age_filtered = self.df[
            (self.df['min_age'] <= age) &
            (self.df['max_age'] >= age)
        ]
        return age_filtered.to_json(
            orient='records', force_ascii=False, indent=2)

    async def handle_course_query(
        self,
        intent_result: IntentResult,
        message_history: str
    ) -> str:
        try:
            if intent_result.intent == IntentType.GENERAL_INQUIRY:
                search_results = await self.hybrid_retriever.search(
                    intent_result.parameters.original_query
                )
                search_context = self.hybrid_retriever.format_search_results(
                    search_results)
                base_context = self.prompts['base_context_general'].format(
                    message_history=message_history,
                    search_results=search_context,
                    intent_result=intent_result
                )
                user_prompt = self.prompts['general_inquiry'].format(
                    base_context=base_context
                )
            else:
                age = intent_result.parameters.age
                courses_json = self._get_available_courses(age)
                logger.info(f"Course JSON: {courses_json}")

                base_context = self.prompts['base_context_course'].format(
                    message_history=message_history,
                    age=age,
                    courses_json=courses_json,
                    intent_result=intent_result
                )
                prompt_key = intent_result.intent.value
                logger.info(f"Prompt Key: {prompt_key}")
                if prompt_key not in self.prompts:
                    logger.error(
                        f"Unsupported intent type: {prompt_key}"
                    )
                    return (
                        "I apologize, but I'm not able to handle this "
                        "request at the moment."
                    )
                user_prompt = self.prompts[prompt_key].format(
                    base_context=base_context)
            
            response = await self.llm.llm(
                self.prompts.system_prompt,
                user_prompt
            )
            logger.info(f"reponse to course inquiry: {response}")
            return response
        except Exception as e:
            logger.error(f"Error in handle_course_query: {e}")
            raise