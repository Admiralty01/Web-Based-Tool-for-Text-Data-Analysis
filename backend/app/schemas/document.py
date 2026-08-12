from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: int
    title: str
    project_id: int
    s3_key: str
    status: str
    error_message: Optional[str] = None
    language: Optional[str] = None
    char_count: Optional[int] = None
    word_count: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentSearchResponse(BaseModel):
    document_id: str
    title: str
    score: float
    clean_content_snippet: str
