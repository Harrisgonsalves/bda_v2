from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field

EventType = Literal["resource_opened", "resource_completed", "search_performed",
                    "feedback_useful", "feedback_not_useful"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EventIn(BaseModel):
    event_type: EventType
    resource_id: Optional[int] = None
    code_module: str = Field(min_length=1, max_length=10)
    code_presentation: str = Field(min_length=1, max_length=10)
    client_event_id: Optional[str] = Field(default=None, max_length=64)
    query: Optional[str] = Field(default=None, max_length=200)
    metadata: Optional[dict] = None


class EventBatch(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=500)


class FeedbackIn(BaseModel):
    resource_id: int
    code_module: str
    code_presentation: str
    useful: bool
    client_event_id: Optional[str] = Field(default=None, max_length=64)
