"""Sync services for lab scores, lecture dates, and lecture attendance."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from app.src.integrations.db import db
from app.src.domain.attendance_record import AttendanceRecord
from app.src.domain.lecture_session import LectureSession
from app.src.domain.student import Student
from app.src.domain.subject import Subject
from app.src.domain.subject_component import SubjectComponent
from app.src.domain.student_lab_score import StudentLabScore
from app.src.domain.user import User

from .schemas import SheetLabScoreRow, SheetLectureAttendanceRow
from .services import get_user_by_email
from .validators import calendar_date_to_lecture_datetime, normalize_component_code, parse_calendar_date


def _get_or_create_subject(semester: int, name: str) -> Subject:
    subject = db.session.execute(
        db.select(Subject).where(Subject.semester == semester, Subject.name == name)
    ).scalar_one_or_none()
    if subject is None:
        subject = Subject(semester=semester, name=name)
        db.session.add(subject)
        db.session.flush()
    return subject


def _find_student_lab_score(
    *,
    student_id: int,
    semester: int,
    subject_name: str,
    component_code: str,
) -> StudentLabScore | None:
    """Resolve a score by semester + subject + LR code (not component_id alone)."""
    normalized_code = normalize_component_code(component_code)
    return db.session.execute(
        db.select(StudentLabScore)
        .join(SubjectComponent, StudentLabScore.component_id == SubjectComponent.id)
        .join(Subject, SubjectComponent.subject_id == Subject.id)
        .where(
            StudentLabScore.student_id == student_id,
            StudentLabScore.semester == semester,
            Subject.semester == semester,
            Subject.name == subject_name,
            SubjectComponent.code == normalized_code,
        )
    ).scalar_one_or_none()


def _get_or_create_component(subject: Subject, code: str, sort_order: int | None = None) -> SubjectComponent:
    normalized = normalize_component_code(code)
    component = db.session.execute(
        db.select(SubjectComponent).where(
            SubjectComponent.subject_id == subject.id,
            SubjectComponent.code == normalized,
        )
    ).scalar_one_or_none()
    if component is None:
        if sort_order is None:
            existing = db.session.execute(
                db.select(db.func.count()).select_from(SubjectComponent).where(
                    SubjectComponent.subject_id == subject.id
                )
            ).scalar() or 0
            sort_order = int(existing) + 1
        component = SubjectComponent(
            subject_id=subject.id,
            code=normalized,
            title=normalized,
            sort_order=sort_order,
        )
        db.session.add(component)
        db.session.flush()
    return component


def _get_or_create_lecture_session(semester: int, session_date: date) -> LectureSession:
    session = db.session.execute(
        db.select(LectureSession).where(
            LectureSession.semester == semester,
            LectureSession.session_date == session_date,
        )
    ).scalar_one_or_none()
    if session is None:
        session = LectureSession(semester=semester, session_date=session_date)
        db.session.add(session)
        db.session.flush()
    return session


def sync_lecture_dates_from_sheet(semester: int, dates: Iterable[str]) -> dict:
    """Replace lecture date schedule for a semester (sheet column headers)."""
    from .validators import validate_semester

    semester = validate_semester(semester)
    parsed_dates: list[date] = []
    errors: list[str] = []

    for index, raw in enumerate(dates):
        try:
            parsed_dates.append(parse_calendar_date(str(raw)))
        except ValueError as error:
            errors.append(f"dates[{index}]: {error}")

    if errors:
        raise ValueError("; ".join(errors))

    unique_dates = sorted(set(parsed_dates))
    existing = db.session.execute(
        db.select(LectureSession).where(LectureSession.semester == semester)
    ).scalars().all()
    existing_by_date = {session.session_date: session for session in existing}

    created = 0
    for session_date in unique_dates:
        if session_date not in existing_by_date:
            db.session.add(LectureSession(semester=semester, session_date=session_date))
            created += 1

    removed = 0
    for session_date, session in existing_by_date.items():
        if session_date not in unique_dates:
            db.session.delete(session)
            removed += 1

    db.session.commit()
    return {
        "semester": semester,
        "processed": len(parsed_dates),
        "unique_dates": len(unique_dates),
        "created": created,
        "removed": removed,
        "dates": [d.isoformat() for d in unique_dates],
    }


def export_lecture_dates_for_sheet(semester: int) -> dict:
    from .validators import validate_semester

    semester = validate_semester(semester)
    sessions = db.session.execute(
        db.select(LectureSession)
        .where(LectureSession.semester == semester)
        .order_by(LectureSession.session_date)
    ).scalars().all()
    return {
        "semester": semester,
        "dates": [session.session_date.isoformat() for session in sessions],
    }


def sync_lecture_attendance_from_sheet(rows: Iterable[SheetLectureAttendanceRow]) -> dict:
    """Import lecture presence from sheet (П in cell) using calendar dates."""
    processed = 0
    created = 0
    removed = 0
    skipped = 0
    errors: list[str] = []

    for row in rows:
        processed += 1
        user = get_user_by_email(row.email)
        if user is None:
            skipped += 1
            errors.append(f"user not found: {row.email}")
            continue

        student = db.session.get(Student, user.id)
        if student is None:
            skipped += 1
            errors.append(f"{row.email}: not a student")
            continue

        session = _get_or_create_lecture_session(row.semester, row.date)
        timestamp = calendar_date_to_lecture_datetime(row.date)

        existing = db.session.execute(
            db.select(AttendanceRecord).where(
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.lecture_session_id == session.id,
            )
        ).scalar_one_or_none()

        if not row.attended:
            if existing is not None:
                db.session.delete(existing)
                removed += 1
            else:
                skipped += 1
            continue

        if existing is not None:
            continue

        db.session.add(
            AttendanceRecord(
                student_id=student.id,
                timestamp=timestamp,
                lecture_session_id=session.id,
            )
        )
        created += 1

    db.session.commit()
    return {
        "processed": processed,
        "created": created,
        "removed": removed,
        "skipped": skipped,
        "errors": errors,
    }


def export_lecture_attendance_for_sheet(semester: int) -> list[dict]:
    from .validators import validate_semester

    semester = validate_semester(semester)
    records = db.session.execute(
        db.select(AttendanceRecord)
        .join(LectureSession, AttendanceRecord.lecture_session_id == LectureSession.id)
        .where(LectureSession.semester == semester)
    ).scalars().all()

    result = []
    for record in records:
        if record.student is None or record.student.user is None:
            continue
        session_date = (
            record.lecture_session.session_date.isoformat()
            if record.lecture_session is not None
            else record.timestamp.date().isoformat()
        )
        result.append({
            "email": record.student.user.email,
            "semester": semester,
            "date": session_date,
            "attended": True,
        })
    return result


def sync_lab_scores_from_sheet(rows: Iterable[SheetLabScoreRow]) -> dict:
    processed = 0
    updated = 0
    created = 0
    skipped = 0
    errors: list[str] = []

    for row in rows:
        processed += 1
        user = get_user_by_email(row.email)
        if user is None:
            skipped += 1
            errors.append(f"user not found: {row.email}")
            continue

        student = db.session.get(Student, user.id)
        if student is None:
            skipped += 1
            errors.append(f"{row.email}: not a student")
            continue

        subject = _get_or_create_subject(row.semester, row.subject)
        if subject.semester != row.semester:
            skipped += 1
            errors.append(
                f"{row.email}: subject semester mismatch for {row.subject!r}."
            )
            continue

        component = _get_or_create_component(subject, row.component)
        if component.subject.semester != row.semester:
            skipped += 1
            errors.append(
                f"{row.email}: component {row.component} does not belong to semester {row.semester}."
            )
            continue

        existing = _find_student_lab_score(
            student_id=student.id,
            semester=row.semester,
            subject_name=row.subject,
            component_code=row.component,
        )

        if existing is None:
            db.session.add(
                StudentLabScore(
                    student_id=student.id,
                    component_id=component.id,
                    semester=row.semester,
                    score=row.score,
                )
            )
            created += 1
            continue

        if existing.component_id != component.id:
            existing.component_id = component.id
        if existing.semester != row.semester:
            existing.semester = row.semester
        if existing.score != row.score:
            existing.score = row.score
            updated += 1

    db.session.commit()
    return {
        "processed": processed,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


def export_lab_scores_for_sheet(semester: int) -> list[dict]:
    from .validators import validate_semester

    semester = validate_semester(semester)
    scores = db.session.execute(
        db.select(StudentLabScore)
        .join(SubjectComponent)
        .join(Subject)
        .where(
            StudentLabScore.semester == semester,
            Subject.semester == semester,
        )
    ).scalars().all()

    result = []
    for entry in scores:
        if entry.student is None or entry.student.user is None:
            continue
        result.append({
            "email": entry.student.user.email,
            "semester": semester,
            "subject": entry.component.subject.name,
            "component": entry.component.code,
            "score": entry.score,
        })
    return result


def export_lab_subjects_for_sheet(semester: int) -> list[dict]:
    """Subject + component layout for sheet headers (semester tab setup)."""
    from .validators import validate_semester

    semester = validate_semester(semester)
    subjects = db.session.execute(
        db.select(Subject).where(Subject.semester == semester).order_by(Subject.name)
    ).scalars().all()

    result = []
    for subject in subjects:
        components = db.session.execute(
            db.select(SubjectComponent)
            .where(SubjectComponent.subject_id == subject.id)
            .order_by(SubjectComponent.sort_order, SubjectComponent.code)
        ).scalars().all()
        result.append({
            "semester": semester,
            "subject": subject.name,
            "short_code": subject.short_code,
            "components": [component.code for component in components],
        })
    return result
