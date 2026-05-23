import json

from flask import Blueprint, current_app, jsonify, request

from app.src.integrations.db import db
from app.src.core.services import (
    get_user_by_email,
    set_user_ban,
    sync_attendance_from_sheet,
)
from app.src.core.schemas import SheetAttendanceRow

bp = Blueprint("sync_v1", __name__, url_prefix="/sync")


def _verify_api_key() -> tuple | None:
    expected_key = current_app.config.get("SHEETS_SYNC_API_KEY")
    provided_key = request.headers.get("X-API-Key")
    if not expected_key or provided_key != expected_key:
        return jsonify({"error": "unauthorized"}), 401
    return None


@bp.post("/ban")
def sync_ban_route() -> tuple:
    """External sync endpoint to set ban status for multiple students."""
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    students = data.get("students")
    if not isinstance(students, list):
        return jsonify({"error": "students must be a list."}), 200

    results = []
    for index, student in enumerate(students):
        if not isinstance(student, dict):
            results.append({"index": index, "status": "error", "error": "student must be an object"})
            continue

        email = student.get("email")
        ban = student.get("ban")
        ban_expires_at = student.get("ban_expires_at")

        if not email:
            results.append({"index": index, "status": "error", "error": "email is required"})
            continue
        if not isinstance(ban, bool):
            results.append({"index": index, "email": email, "status": "error", "error": "ban must be a boolean"})
            continue

        user = get_user_by_email(email)
        if user is None:
            results.append({"index": index, "email": email, "status": "error", "error": "user not found"})
            continue

        try:
            set_user_ban(user, ban, ban_expires_at)
            results.append({
                "index": index,
                "email": email,
                "status": "ok",
                "ban_expires_at": user.ban_expires_at.isoformat() if user.ban_expires_at else None,
            })
        except ValueError as error:
            results.append({"index": index, "email": email, "status": "error", "error": str(error)})

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "unable to save ban updates"}), 500

    return jsonify({"results": results}), 200


@bp.post("/attendance")
def sync_attendance_route() -> tuple:
    """External sync endpoint to import attendance status for multiple students."""
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    students = data.get("students")
    if not isinstance(students, list):
        return jsonify({"error": "students must be a list."}), 200

    rows = []
    results = []
    for index, student in enumerate(students):
        if not isinstance(student, dict):
            results.append({"index": index, "status": "error", "error": "student must be an object"})
            continue

        email = student.get("email")
        date_value = student.get("date")
        status = student.get("status")

        if not email:
            results.append({"index": index, "status": "error", "error": "email is required"})
            continue
        if not date_value:
            results.append({"index": index, "email": email, "status": "error", "error": "date is required"})
            continue
        if status not in {"present", "absent"}:
            results.append({"index": index, "email": email, "status": "error", "error": "status must be 'present' or 'absent'"})
            continue

        timestamp = f"{date_value}T00:00:00"
        attended = status == "present"
        try:
            rows.append(SheetAttendanceRow(email=email, timestamp=timestamp, attended=attended))
            results.append({"index": index, "email": email, "status": "ok", "attendance_status": status})
        except ValueError as error:
            results.append({"index": index, "email": email, "status": "error", "error": str(error)})

    if not rows:
        return jsonify({"results": results}), 200

    try:
        sync_result = sync_attendance_from_sheet(rows)
    except ValueError as error:
        return jsonify({"error": str(error)}), 200

    return jsonify({"results": results, "sync_result": sync_result}), 200
