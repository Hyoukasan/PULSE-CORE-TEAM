from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm as so
from datetime import datetime
from typing import Optional

from ..integrations.db import db


class ApproachQueue(db.Model):
    """
    Очередь физических подходов студентов-практиков на занятие.
    
    Связывает: студент + преподаватель + дата занятия
    Позволяет управлять очередью: добавление, удаление, проверка позиции.
    """

    __tablename__ = "approach_queues"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    
    # FK к Student (практики)
    student_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("students.id"), 
        nullable=False, 
        index=True
    )
    
    # FK к Professor (преподаватель, ведущий занятие)
    professor_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("professors.id"), 
        nullable=False, 
        index=True
    )
    
    # Дата занятия (используется для группировки очереди)
    lesson_date: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime, 
        nullable=False, 
        index=True
    )
    
    # Позиция в очереди (1, 2, 3, ...)
    # Автоматически пересчитывается при удалении из очереди
    position: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    labs_count: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=1)
    
    # Статус: pending (ожидание), attended (допущен/пришел), cancelled (отменено)
    status: so.Mapped[str] = so.mapped_column(
        sa.String(16), 
        nullable=False, 
        default="pending"
    )
    
    # Временные метки
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime, 
        nullable=False, 
        default=datetime.utcnow
    )
    updated_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime, 
        nullable=False, 
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Отношения
    student: so.Mapped["Student"] = so.relationship(
        "Student", 
        back_populates="approach_queues"
    )
    professor: so.Mapped["Professor"] = so.relationship(
        "Professor", 
        back_populates="approach_queues"
    )
    
    # Уникальное ограничение: один студент только в одной очереди на одно занятие
    __table_args__ = (
        sa.UniqueConstraint(
            'student_id', 'professor_id', 'lesson_date',
            name='uq_student_professor_lesson'
        ),
    )
