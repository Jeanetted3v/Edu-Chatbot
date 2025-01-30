from typing import List, Optional
from enum import Enum
from pydantic import BaseModel


class IntentType(str, Enum):
    COURSE_INQUIRY = "course_inquiry"
    SCHEDULE_INQUIRY = "schedule_inquiry"
    TEACHER_INQUIRY = "teacher_inquiry"
    FEES_INQUIRY = "fees_inquiry"
    ENROLLMENT_INQUIRY = "enrollment_inquiry"
    GENERAL_INQUIRY = "general_inquiry"


class ExtractedParameters(BaseModel):
    age: Optional[int] = None
    subject: Optional[str] = None
    course_id: Optional[str] = None
    teacher_id: Optional[str] = None
    preferred_timing: Optional[str] = None
    student_name: Optional[str] = None


class IntentResult(BaseModel):
    intent: IntentType
    parameters: ExtractedParameters
    is_followup: bool
    missing_info: List[str]