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
    source_type = Column(String, default="self")
    source_ref = Column(String, nullable=True)

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
