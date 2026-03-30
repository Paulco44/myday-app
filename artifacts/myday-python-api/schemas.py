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
    focus_state: Optional[str] = None
    time_block: Optional[str] = None
    energy_tag: Optional[str] = None


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
    focus_state: Optional[str] = None
    time_block: Optional[str] = None
    energy_tag: Optional[str] = None


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
    focus_state: Optional[str]
    time_block: Optional[str]
    energy_tag: Optional[str]

    class Config:
        from_attributes = True


# ─── Notion Integration ──────────────────────────────────────────────────────

class NotionSourceCreate(BaseModel):
    name: str
    source_type: str = "page"   # page | database
    notion_id: str
    import_mode: str = "inbox"  # inbox | linked_note
    is_active: bool = True


class NotionSourceRead(BaseModel):
    id: int
    name: str
    source_type: str
    notion_id: str
    import_mode: str
    is_active: bool
    last_imported_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Inbox ───────────────────────────────────────────────────────────────────

class WhisperIngest(BaseModel):
    title: str
    raw_content: Optional[str] = None
    summary: Optional[str] = None
    suggested_actions: Optional[List[str]] = []
    external_id: Optional[str] = None
    source_created_at: Optional[datetime] = None


class InboxItemRead(BaseModel):
    id: int
    source: str
    source_type: str
    external_id: Optional[str]
    title: str
    raw_content: Optional[str]
    summary: Optional[str]
    suggested_actions_json: Optional[str]
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime]
    linked_task_id: Optional[int]
    linked_project_id: Optional[int]
    linked_note_url: Optional[str]

    class Config:
        from_attributes = True


# ─── CoP Initiative ──────────────────────────────────────────────────────────

class CoPInitiativeCreate(BaseModel):
    effort: Optional[str] = None
    topic: Optional[str] = None
    topic_description: Optional[str] = None
    subtopic: Optional[str] = None
    type_of_effort: Optional[str] = None
    focus_market: Optional[str] = None
    leader: Optional[str] = None
    cop_collaboration: Optional[str] = None
    notes: Optional[str] = None
    active_jan: bool = False
    active_feb: bool = False
    active_mar: bool = False
    active_apr: bool = False
    active_may: bool = False
    active_jun: bool = False
    active_jul: bool = False
    active_aug: bool = False
    active_sep: bool = False
    active_oct: bool = False
    active_nov: bool = False
    active_dec: bool = False


class CoPInitiativeUpdate(BaseModel):
    effort: Optional[str] = None
    topic: Optional[str] = None
    topic_description: Optional[str] = None
    subtopic: Optional[str] = None
    type_of_effort: Optional[str] = None
    focus_market: Optional[str] = None
    leader: Optional[str] = None
    cop_collaboration: Optional[str] = None
    notes: Optional[str] = None
    active_jan: Optional[bool] = None
    active_feb: Optional[bool] = None
    active_mar: Optional[bool] = None
    active_apr: Optional[bool] = None
    active_may: Optional[bool] = None
    active_jun: Optional[bool] = None
    active_jul: Optional[bool] = None
    active_aug: Optional[bool] = None
    active_sep: Optional[bool] = None
    active_oct: Optional[bool] = None
    active_nov: Optional[bool] = None
    active_dec: Optional[bool] = None


class CoPInitiativeRead(BaseModel):
    id: int
    effort: Optional[str]
    topic: Optional[str]
    topic_description: Optional[str]
    subtopic: Optional[str]
    type_of_effort: Optional[str]
    focus_market: Optional[str]
    leader: Optional[str]
    cop_collaboration: Optional[str]
    notes: Optional[str]
    active_jan: bool
    active_feb: bool
    active_mar: bool
    active_apr: bool
    active_may: bool
    active_jun: bool
    active_jul: bool
    active_aug: bool
    active_sep: bool
    active_oct: bool
    active_nov: bool
    active_dec: bool

    class Config:
        from_attributes = True
