from sqlalchemy import event
from flask import after_this_request, has_request_context

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

        if not app.config.get("SYNC_CALLBACK_URL"):
            return

        types = set(sync_types)

        def send_sync_callback() -> None:
            try:
                db.session.remove()
                payload: dict = {}
                if "groups" in types:
                    payload["groups"] = export_groups_for_sheet()
                if "users" in types:
                    payload["users"] = export_users_for_sheet()
                if "attendance" in types:
                    payload["attendance"] = export_attendance_for_sheet()
                if not payload:
                    return
                send_sync_notification(payload)
            except Exception:
                app.logger.exception("Sync callback failed after commit")

        if has_request_context():
            @after_this_request
            def _defer_sync_callback(response):
                send_sync_callback()
                return response

            return

        with app.app_context():
            send_sync_callback()
