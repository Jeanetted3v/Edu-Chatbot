from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    COURSE_INQUIRY = "course_inquiry"
    GENERAL_INQUIRY = "general_inquiry"


class QueryParameters(BaseModel):
    age: Optional[int] = Field(None, description="Student's age")
    subject: Optional[str] = Field(None, description="Course subject")
    student_name: Optional[str] = Field(None, description="Student's name")
    interest: Optional[List[str]] = Field(
        None,
        description="Student's interests",
        min_items=1
    )


class IntentResult(BaseModel):
    intent: IntentType
    parameters: QueryParameters
    response: str
    missing_info: List[str] = Field(
        default_factory=list,
        description="List of missing required information",
        min_intems=0
    )
