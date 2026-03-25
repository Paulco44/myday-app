from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel


# ─── Project ────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class ProjectRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


# ─── Task ────────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: Optional[int] = None
    owner: str = "me"
    status: str = "todo"
    priority: str = "medium"
    due_date: Optional[date] = None
    is_today: bool = False
    source_type: str = "self"
    source_ref: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[int] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    is_today: Optional[bool] = None
    completed_at: Optional[datetime] = None
    source_type: Optional[str] = None
    source_ref: Optional[str] = None


class TaskRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    project_id: Optional[int]
    owner: str
    status: str
    priority: str
    due_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    is_today: bool
    source_type: str
    source_ref: Optional[str]

    class Config:
        from_attributes = True
