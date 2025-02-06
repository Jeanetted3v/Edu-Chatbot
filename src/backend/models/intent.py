from typing import List, Optional
from enum import Enum
from pydantic import BaseModel


class IntentType(str, Enum):
    COURSE_INQUIRY = "course_inquiry"
    SCHEDULE_INQUIRY = "schedule_inquiry"
    FEE_INQUIRY = "fee_inquiry"
    LEVEL_INQUIRY = "level_inquiry"
    GENERAL_INQUIRY = "general_inquiry"


class QueryParameters(BaseModel):
    age: Optional[int]
    school_type: Optional[str]
    level: Optional[int]
    subject: Optional[str]
    english_level: Optional[str]
    lexile_score: Optional[str]
    current_reading: Optional[str]
    student_name: Optional[str]
    interest: Optional[List[str]]
    original_query: str


class IntentResult(BaseModel):
    intent: IntentType
    parameters: QueryParameters
    response: str
    missing_info: List[str]
