from typing import List, Optional
import pandas as pd
import logging
from src.backend.models.course import Course, CourseFilter, CourseMatch
from src.backend.dataloaders.local_doc_loader import LocalDocLoader, LoadedStructuredDocument
from utils.prompt_loader import PromptLoader
from pydantic_ai import Agent

logger = logging.getLogger(__name__)


class CourseService:
    def __init__(self, doc_loader: LocalDocLoader, excel_path: str):
        self.excel_path = excel_path
        self.excel_path = excel_path
        self.courses = self._load_courses()
        self.prompts = PromptLoader.load_prompts('course_service')
        self.agent = Agent(
            'openai:gpt-4o-mini',
            result_type=CourseMatch,
            system_prompt=self.prompts['system_prompt']
        )

    def _load_courses(self) -> List[Course]:
        """Load courses from Excel file using LocalDocLoader"""
        try:
            # Load document using LocalDocLoader
            loaded_doc = self.doc_loader.load_document(self.excel_path)
            
            if not isinstance(loaded_doc, LoadedStructuredDocument):
                raise ValueError("Expected structured document for course data")
            
            df = loaded_doc.content
            
            # Handle datetime conversion for start_date
            if 'start_date' in df.columns:
                df['start_date'] = pd.to_datetime(df['start_date'])
            
            # Convert DataFrame rows to Course objects
            courses = []
            for _, row in df.iterrows():
                try:
                    course_dict = row.to_dict()
                    # Handle any NaN values for optional fields
                    for key in ['half_year_discount_price', 'whole_year_discount_price']:
                        if pd.isna(course_dict.get(key)):
                            course_dict[key] = None
                    courses.append(Course(**course_dict))
                except Exception as e:
                    print(f"Error processing course row: {e}")
                    continue
                    
            return courses
            
        except FileNotFoundError:
            print(f"Course data file not found: {self.excel_path}")
            return []
        except Exception as e:
            print(f"Error loading course data: {e}")
            return []
        
    def _is_age_suitable(self, age: int, course: Course) -> bool:
        """Check if a course is suitable for given age"""
        return course.min_age <= age <= course.max_age

    async def _get_semantic_matches(
        self,
        interests: List[str],
        age_filtered_courses: List[Course]
    ) -> List[str]:
        if not interests or not age_filtered_courses:
            return [(course, 1.0) for course in age_filtered_courses]  # Return all courses with full score if no interests

        # Create a context string for each course
        course_contexts = [
            f"Course: {course.course_name}\n"
            for course in age_filtered_courses
        ]
        prompt = self.prompts['user_prompt'].format(
            course_contexts=course_contexts
        )
        try:
            result = await self.agent.run(prompt)
            matches = result.data.matches

            # Convert to list of (course, score) tuples, using 0 score for unmatched courses
            scored_courses = []
            for course in age_filtered_courses:
                match = next(
                    (m for m in matches if m['index'] == age_filtered_courses.index(course)), 
                    {'score': 0, 'reason': None}
                )
                scored_courses.append((course, match['score']))
            return scored_courses
        except Exception as e:
            print(f"Error in semantic matching: {e}")
            # Fallback to returning all courses with neutral score
            return [(course, 0.5) for course in age_filtered_courses]

    async def filter_courses(self, filter_params: CourseFilter) -> List[Course]:
        """Filter courses by age and optional interests"""
        # First filter by age (required)
        age_filtered = [
            course for course in self.courses
            if self._is_age_suitable(filter_params.age, course.recommend_age)
        ]
        if not filter_params.interests:
            return age_filtered
        
        # Get semantic matches using LLM
        scored_courses = await self._get_semantic_matches(filter_params.interests, age_filtered)
        
        # Sort by score and return courses with score > 0.3
        return [
            course for course, score in sorted(scored_courses, key=lambda x: x[1], reverse=True)
            if score > 0.3
        ]

    def get_course_details(self, course_id: str) -> Optional[Course]:
        """Get detailed information about a specific course"""
        for course in self.courses:
            if course.course_id == course_id:
                return course
        return None
    
    def get_metadata(self) -> dict:
        """Get metadata about loaded courses"""
        return {
            'total_courses': len(self.courses),
            'available_levels': sorted(list(set(c.course_level for c in self.courses))),
            'age_ranges': [
                f"{c.min_age}-{c.max_age}" 
                for c in sorted(self.courses, key=lambda x: (x.min_age, x.max_age))
            ],
            'teachers': sorted(list(set(c.teacher for c in self.courses)))
        }