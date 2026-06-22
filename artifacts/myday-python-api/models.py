from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date,
    ForeignKey, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    # Provenance (Phase 3)
    source_ref = Column(String, nullable=True)
    imported_at = Column(String, nullable=True)
    # Notion export (Phase 4)
    notion_page_id = Column(String, nullable=True)
    notion_url = Column(String, nullable=True)
    exported_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    # Billing bridge: default Client (CC1) + Project (CC2) this project bills to
    billing_client_id = Column(Integer, ForeignKey("billing_clients.id", ondelete="SET NULL"), nullable=True)
    billing_project_id = Column(Integer, ForeignKey("billing_projects.id", ondelete="SET NULL"), nullable=True)
    # Daily commitment: if set (>0), this project is a continuous commitment with a
    # daily time target shown as a rail on the Kanban. NULL/0 = not a commitment.
    daily_minutes_goal = Column(Integer, nullable=True)

    tasks = relationship("Task", back_populates="project")
    recurring_tasks = relationship("RecurringTask", back_populates="project")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    owner = Column(String, default="me")
    status = Column(String, default="todo")
    priority = Column(String, default="medium")
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    is_today = Column(Boolean, default=False)
    is_now = Column(Boolean, default=False)
    energy_type = Column(String(20), nullable=True)
    time_estimate_minutes = Column(Integer, nullable=True)
    today_flag = Column(Boolean, default=False)
    today_category = Column(String(10), nullable=True)  # "win" | "nice"
    source_type = Column(String, default="self")
    source_ref = Column(String, nullable=True)

    # New fields for Now/Next/Later, time blocks, and energy
    focus_state = Column(String, nullable=True)   # now | next | later_today | later | None
    time_block = Column(String, nullable=True)    # morning | afternoon | evening | None
    energy_tag = Column(String, nullable=True)    # creative | admin | social | low_energy | None

    # Bridge: linked Kanban card
    card_id = Column(Integer, nullable=True)      # cards.id (React Kanban)

    # Collaboration / context
    status_note = Column(Text, nullable=True)     # why it's in this status / blockers
    assignee = Column(String(100), nullable=True) # person responsible
    # Billing bridge — CC1/CC2/CC3 for this block (default inherited from project, overridable)
    billing_client_id = Column(Integer, ForeignKey("billing_clients.id", ondelete="SET NULL"), nullable=True)
    billing_project_id = Column(Integer, ForeignKey("billing_projects.id", ondelete="SET NULL"), nullable=True)
    billing_task_id = Column(Integer, ForeignKey("billing_tasks.id", ondelete="SET NULL"), nullable=True)
    # Weekly planner block + Outlook calendar push (idempotent)
    scheduled_start = Column(DateTime, nullable=True)   # planned block start
    scheduled_minutes = Column(Integer, nullable=True)  # planned block duration
    calendar_event_id = Column(String, nullable=True)   # Outlook event id (re-push/update)
    calendar_pushed_at = Column(DateTime, nullable=True)
    plan_reason = Column(String, nullable=True)         # why the LLM placed this block here

    project = relationship("Project", back_populates="tasks")
    subtasks = relationship("Subtask", back_populates="task", cascade="all, delete-orphan")
    task_tags = relationship("TaskTag", back_populates="task", cascade="all, delete-orphan")


class Subtask(Base):
    __tablename__ = "subtasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    is_done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="subtasks")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    task_tags = relationship("TaskTag", back_populates="tag", cascade="all, delete-orphan")


class TaskTag(Base):
    __tablename__ = "task_tags"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)

    task = relationship("Task", back_populates="task_tags")
    tag = relationship("Tag", back_populates="task_tags")


class RecurringTask(Base):
    __tablename__ = "recurring_tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    priority = Column(String, default="medium")
    recurrence_type = Column(String, nullable=False)
    recurrence_rule = Column(String, nullable=False)
    active = Column(Boolean, default=True)

    project = relationship("Project", back_populates="recurring_tasks")


class CommitmentLog(Base):
    """Append-only log of time given to a daily-commitment project on a given day.

    Daily progress = SUM(minutes) for (project_id, date). It resets every day
    automatically because reads filter by date. `source` keeps provenance so a
    focus-timer feed can be added later alongside manual entries.
    """
    __tablename__ = "commitment_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, default=date.today, index=True)
    minutes = Column(Integer, nullable=False, default=0)
    source = Column(String(20), nullable=False, default="manual")  # manual | focus | calendar
    created_at = Column(DateTime, default=datetime.utcnow)


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    morning_ritual_time = Column(String, default="08:30")
    wip_limit_doing = Column(Integer, default=3)
    default_priority = Column(String, default="medium")


class DailyLog(Base):
    """One row per calendar day. Tracks morning ritual start and completions."""
    __tablename__ = "daily_logs"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    started = Column(Boolean, default=False)
    started_at = Column(DateTime, nullable=True)
    has_completed_task = Column(Boolean, default=False)
    has_morning_checkin = Column(Boolean, default=False)  # did the brain-dump check-in today
    energy_today = Column(String(30), nullable=True)      # high | flow | low | scattered
    day_closed = Column(Boolean, default=False)           # did the evening reset today


class NoteItem(Base):
    """
    A saved reference note — promoted from Inbox or created directly.
    Preserves source provenance; supports Notion export.
    """
    __tablename__ = "note_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=True)       # full text / transcript
    summary = Column(Text, nullable=True)       # short summary
    source = Column(String, nullable=False, default="self")  # whisper | notion | self
    external_id = Column(String, nullable=True) # Notion page ID, whisper file ID, etc.
    external_url = Column(String, nullable=True)# original URL (Notion page URL, etc.)
    linked_inbox_id = Column(Integer, nullable=True)  # inbox_items.id (no FK — SQLite compat)
    imported_at = Column(DateTime, nullable=True)     # when imported into MyDay
    created_at = Column(DateTime, default=datetime.utcnow)
    # Notion export
    notion_page_id = Column(String, nullable=True)
    notion_url = Column(String, nullable=True)
    exported_at = Column(DateTime, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)


class NotionSource(Base):
    """Notion page or database configured as an import source."""
    __tablename__ = "notion_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    source_type = Column(String, nullable=False, default="page")  # page | database
    notion_id = Column(String, nullable=False)                    # Notion page/database UUID
    import_mode = Column(String, nullable=False, default="inbox") # inbox | linked_note
    is_active = Column(Boolean, default=True)
    last_imported_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class InboxItem(Base):
    """Meeting notes / Whisper-derived content waiting for triage."""
    __tablename__ = "inbox_items"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, default="whisper")
    source_type = Column(String, nullable=False, default="meeting")
    external_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    raw_content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    suggested_actions_json = Column(Text, nullable=True)  # JSON-encoded list[str]
    status = Column(String, nullable=False, default="new")  # new|reviewing|promoted|archived
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    linked_task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    linked_project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    linked_note_id = Column(Integer, nullable=True)  # note_items.id (no FK — SQLite compat)
    linked_note_url = Column(String, nullable=True)  # kept for backwards compat / direct URL refs


class CoPInitiative(Base):
    """Community of Practice initiative."""
    __tablename__ = "cop_initiatives"

    id = Column(Integer, primary_key=True, index=True)
    effort = Column(String, nullable=True)
    topic = Column(String, nullable=True)
    topic_description = Column(String, nullable=True)
    subtopic = Column(String, nullable=True)
    type_of_effort = Column(String, nullable=True)
    focus_market = Column(String, nullable=True)
    leader = Column(String, nullable=True)
    cop_collaboration = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    active_jan = Column(Boolean, default=False)
    active_feb = Column(Boolean, default=False)
    active_mar = Column(Boolean, default=False)
    active_apr = Column(Boolean, default=False)
    active_may = Column(Boolean, default=False)
    active_jun = Column(Boolean, default=False)
    active_jul = Column(Boolean, default=False)
    active_aug = Column(Boolean, default=False)
    active_sep = Column(Boolean, default=False)
    active_oct = Column(Boolean, default=False)
    active_nov = Column(Boolean, default=False)
    active_dec = Column(Boolean, default=False)


class FocusSession(Base):
    """Tracks individual focus timer sessions for analytics and weekly review."""
    __tablename__ = "focus_sessions"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=True)        # focused task (no FK for compat)
    started_at = Column(DateTime, nullable=True)    # approximate start time
    duration_minutes = Column(Integer, nullable=False)
    completed = Column(Boolean, default=True)       # did the timer reach 0?
    date = Column(Date, nullable=False, default=date.today)
    created_at = Column(DateTime, default=datetime.utcnow)


class Briefing(Base):
    """One cached proactive briefing per day (morning objective + stall radar)."""
    __tablename__ = "briefings"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    content = Column(Text, nullable=False)        # JSON-encoded briefing
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    """A chat thread with the MyDay assistant (Phase 0: single-user, local)."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)          # auto-derived from first message
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    """One turn in a conversation. Only user/assistant text turns are persisted;
    tool round-trips happen within a single request and are rebuilt each turn."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)          # user | assistant
    content = Column(Text, nullable=False)
    tool_trace = Column(Text, nullable=True)       # JSON list of tools used this turn (display only)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class NotionExportTarget(Base):
    """
    A configured Notion destination for exporting notes and projects.
    Separate from NotionSource (import) to keep concerns clean.
    Webhook sync can reuse the same notion_client helpers later.
    """
    __tablename__ = "notion_export_targets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    notion_id = Column(String, nullable=False)      # page or database UUID (no dashes)
    target_type = Column(String, nullable=False, default="page")  # page | database
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── Billing codes catalog (MyDay↔TimeTracker bridge) ─────────────────────────
# Mirrors V2A's Paylocity coding: Client (CC1) → Project (CC2) → Task (CC3),
# where Client↔Project is many-to-many and Project→Task is one-to-many.
# Imported from TimeTracker's catalog / the "Time and attendance" workbooks.

class BillingClient(Base):
    """CC1 — client / service-line / practice bucket (e.g. 'Public Sector' 5.6)."""
    __tablename__ = "billing_clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)            # may be blank in a partial catalog
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BillingProject(Base):
    """CC2 — project / engagement (e.g. 'Knowledge 4 Impact' V2A006)."""
    __tablename__ = "billing_projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BillingTask(Base):
    """CC3 — task / work type (e.g. 'Meetings & Work Sessions' 8)."""
    __tablename__ = "billing_tasks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BillingClientProject(Base):
    """Valid Client↔Project pairing (many-to-many)."""
    __tablename__ = "billing_client_project"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("billing_clients.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Integer, ForeignKey("billing_projects.id", ondelete="CASCADE"), nullable=False)
    __table_args__ = (UniqueConstraint("client_id", "project_id", name="uq_client_project"),)


class BillingProjectTask(Base):
    """Valid Project→Task pairing (which task types apply to a project)."""
    __tablename__ = "billing_project_task"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("billing_projects.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("billing_tasks.id", ondelete="CASCADE"), nullable=False)
    __table_args__ = (UniqueConstraint("project_id", "task_id", name="uq_project_task"),)
