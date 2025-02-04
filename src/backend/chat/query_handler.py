from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime
from pydantic_ai import Agent
import logging

from src.backend.chat.chat_history import ChatHistory
from src.backend.chat.course_service import CourseService
from src.backend.dataloaders.local_doc_loader import LocalDocLoader
from src.backend.dataprocesser.hybrid_search import HybridSearcher
from src.backend.models.intent import IntentType, IntentResult

logger = logging.getLogger(__name__)


class QueryHandler:
    def __init__(self, doc_loader: LocalDocLoader):
        self.agent = Agent(
            'openai:gpt-4o-mini',
            result_type=IntentResult,
            system_prompt=self.prompts['system_prompt']
        )
        self.course_service = CourseService(doc_loader, "courses.xlsx", self.agent)
        self.chat_history = ChatHistory()
        
        # Log course data metadata
        metadata = self.course_service.get_metadata()
        logger.info(f"Loaded {metadata['total_courses']} courses")
        logger.info(f"Available levels: {metadata['available_levels']}")
        
    async def handle_course_recommendation(self, intent_result: IntentResult) -> str:
        """Handle course recommendations based on intent"""
        age = intent_result.parameters.get("age")
        interests = intent_result.parameters.get("interests", [])
        
        try:
            # Filter courses using semantic matching
            filtered_courses = await self.course_service.filter_courses(
                CourseFilter(age=age, interests=interests)
            )
            
            if not filtered_courses:
                if interests:
                    # If we have interests but no matches, try without interests
                    filtered_courses = await self.course_service.filter_courses(
                        CourseFilter(age=age)
                    )
                    if filtered_courses:
                        return ("I couldn't find exact matches for your interests, but here are some courses "
                               "suitable for the age group. Would you like to hear about these alternatives?")
                return "I couldn't find any courses suitable for that age group. Would you like to try a different age range?"

            # Format courses for LLM recommendation
            courses_text = "\n".join([
                f"Course: {c.course_name}\n"
                f"Level: {c.course_level}\n"
                f"Schedule: {c.course_date_time}\n"
                f"Teacher: {c.teacher}\n"
                f"Price: ${c.half_year_full_price:,.2f} (half year) / "
                f"${c.whole_year_full_price:,.2f} (full year)\n"
                for c in filtered_courses
            ])

            recommendation_prompt = f"""
            Based on these available courses:
            {courses_text}

            Please recommend the most suitable courses for a {age} year old student
            {f'interested in {", ".join(interests)}' if interests else ''}.
            
            Consider their age and development stage. For each recommended course, explain:
            1. Why it matches their interests (if interests were provided)
            2. How it benefits their development
            3. Key features of the course
            
            Format your response in a friendly, conversational way.
            Include specific details about schedule and pricing to help with decision making.
            
            Limit your response to 3-4 top recommendations.
            """

            recommendation_result = await self.agent.run(recommendation_prompt)
            return recommendation_result.response
            
        except Exception as e:
            logger.error(f"Error generating course recommendations: {e}")
            return "I apologize, but I encountered an error while processing the course recommendations. Please try again or contact support if the issue persists."

    async def handle_course_details(self, course_id: str) -> str:
        """Handle requests for detailed course information"""
        course = self.course_service.get_course_details(course_id)
        if not course:
            return f"I couldn't find any course with ID {course_id}."
        
        try:
            course_details = f"""
            Course Name: {course.course_name}
            Level: {course.course_level}
            Age Range: {course.min_age}-{course.max_age} years
            Teacher: {course.teacher}
            Schedule: {course.course_date_time}
            Pricing: 
            - Half Year: ${course.half_year_full_price:,.2f}
            - Full Year: ${course.whole_year_full_price:,.2f}
            """
            
            details_prompt = f"""
            Please provide a detailed, friendly description of this course:
            {course_details}
            
            Include key highlights and what makes it special. Format the response
            in a conversational way that would help parents understand the value
            of the course.
            """
            
            details_result = await self.agent.run(details_prompt)
            return details_result.response
            
        except Exception as e:
            logger.error(f"Error getting course details: {e}")
            return "I apologize, but I encountered an error while retrieving the course details. Please try again or contact support if the issue persists."

    async def handle_query(self, intent_result: IntentResult) -> str:
        """Main entry point for handling queries based on intent"""
        if intent_result.intent == "course_recommendation":
            response = await self.handle_course_recommendation(intent_result)
        elif intent_result.intent == "course_details":
            course_id = intent_result.parameters.get("course_id")
            response = await self.handle_course_details(course_id)
        else:
            response = "I'm not sure how to handle that type of request. Could you please rephrase it?"
        
        self.chat_history.add_turn('assistant', response)
        return response