from sqlalchemy import event

from app.src.integrations.db import db


def register_db_listeners(app) -> None:
    from app.src.core.services import (
        export_attendance_for_sheet,
        export_groups_for_sheet,
        export_users_for_sheet,
    )
    from app.src.domain.attendance_record import AttendanceRecord
    from app.src.domain.group import Group
    from app.src.domain.professor import Professor
    from app.src.domain.student import Student
    from app.src.domain.user import User
    from app.src.utils.webhooks import send_sync_notification

    @event.listens_for(db.session, "after_flush")
    def after_flush(session, flush_context):
        sync_types = session.info.setdefault("sync_change_types", set())
        changed_objects = set(session.new) | set(session.dirty) | set(session.deleted)

        for obj in changed_objects:
            if isinstance(obj, Group):
                sync_types.add("groups")
            if isinstance(obj, AttendanceRecord):
                sync_types.add("attendance")
            if isinstance(obj, (User, Student, Professor)):
                sync_types.add("users")

    @event.listens_for(db.session, "after_commit")
    def after_commit(session):
        sync_types = session.info.pop("sync_change_types", None)
        if not sync_types:
            return

        callback_url = app.config.get("SYNC_CALLBACK_URL")
        if not callback_url:
            return

        payload: dict = {}
        if "groups" in sync_types:
            payload["groups"] = export_groups_for_sheet()
        if "users" in sync_types:
            payload["users"] = export_users_for_sheet()
        if "attendance" in sync_types:
            payload["attendance"] = export_attendance_for_sheet()

        if not payload:
            return

        try:
            with app.app_context():
                send_sync_notification(payload)
        except Exception:
            # Do not interrupt the database commit path.
            pass
