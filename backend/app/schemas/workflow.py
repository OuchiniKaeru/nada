from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class WorkflowStep(BaseModel):
    kind: Literal["agent", "squad"]
    ref_id: str
    prompt_template: str = ""


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    visibility: str = "private"
    steps: list[WorkflowStep] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    steps: Optional[list[WorkflowStep]] = None


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str
    visibility: str
    steps: list[dict]
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
