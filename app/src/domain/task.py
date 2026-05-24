from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so
from datetime import datetime
from typing import Optional

from ..integrations.db import db


class Task(db.Model):
    """Задание (task) от администратора/преподавателя группе студентов."""

    __tablename__ = "tasks"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    
    # Группа-получатель (все студенты в группе)
    group_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("groups.id"), nullable=False, index=True
    )
    
    # Создатель задания (администратор или преподаватель)
    created_by_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("users.id"), nullable=False, index=True
    )
    
    # Содержание задания
    title: so.Mapped[str] = so.mapped_column(sa.String(255), nullable=False)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)
    file_url: so.Mapped[Optional[str]] = so.mapped_column(sa.String(255), nullable=True)
    
    # Сроки
    due_date: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime, nullable=False, default=datetime.utcnow
    )

    # Отношения
    group: so.Mapped["Group"] = so.relationship(back_populates="tasks")
    created_by: so.Mapped["User"] = so.relationship(back_populates="created_tasks")
    responses: so.Mapped[list["TaskResponse"]] = so.relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskResponse(db.Model):
    """Ответ студента на задание."""

    __tablename__ = "task_responses"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    
    # Ссылка на задание
    task_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("tasks.id"), nullable=False, index=True
    )
    
    # Студент, отправивший ответ
    student_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("students.id"), nullable=False, index=True
    )
    
    # Содержание ответа
    response_text: so.Mapped[Optional[str]] = so.mapped_column(sa.Text, nullable=True)
    file_url: so.Mapped[Optional[str]] = so.mapped_column(sa.String(255), nullable=True)
    
    # Оценка (опционально)
    score: so.Mapped[Optional[float]] = so.mapped_column(sa.Float, nullable=True)
    feedback: so.Mapped[Optional[str]] = so.mapped_column(sa.Text, nullable=True)
    
    # Статус
    status: so.Mapped[str] = so.mapped_column(
        sa.String(32), nullable=False, default="submitted"  # submitted, graded, reviewed
    )
    
    # Временные метки
    submitted_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime, nullable=False, default=datetime.utcnow
    )
    graded_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime, nullable=True)

    # Отношения
    task: so.Mapped["Task"] = so.relationship(back_populates="responses")
    student: so.Mapped["Student"] = so.relationship(back_populates="task_responses")
