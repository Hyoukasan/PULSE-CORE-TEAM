"""Lightweight SQLite schema patches (until Alembic is wired)."""

from sqlalchemy import inspect, text

from app.src.integrations.db import db


def apply_sqlite_schema_patches() -> None:
    if db.engine is None:
        return
    if db.engine.dialect.name != "sqlite":
        return

    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    if "attendance_records" not in table_names:
        return

    columns = {column["name"] for column in inspector.get_columns("attendance_records")}
    if "lecture_session_id" not in columns:
        with db.engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE attendance_records "
                    "ADD COLUMN lecture_session_id INTEGER "
                    "REFERENCES lecture_sessions(id) ON DELETE CASCADE"
                )
            )

    if "student_lab_scores" in table_names:
        score_columns = {
            column["name"] for column in inspector.get_columns("student_lab_scores")
        }
        if "semester" not in score_columns:
            with db.engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE student_lab_scores ADD COLUMN semester INTEGER")
                )
                connection.execute(
                    text(
                        "UPDATE student_lab_scores "
                        "SET semester = ("
                        "  SELECT subjects.semester "
                        "  FROM subject_components "
                        "  JOIN subjects ON subjects.id = subject_components.subject_id "
                        "  WHERE subject_components.id = student_lab_scores.component_id"
                        ")"
                    )
                )
                connection.execute(
                    text(
                        "UPDATE student_lab_scores SET semester = 1 "
                        "WHERE semester IS NULL"
                    )
                )
