import json

from flask import Blueprint, current_app, jsonify, request

from app.src.core.schemas import (
    SheetUserRow,
    SheetAttendanceRow,
    SheetLabScoreRow,
    SheetLectureAttendanceRow,
)
from app.src.core.services import (
    sync_users_from_sheet,
    sync_attendance_from_sheet,
    export_users_for_sheet,
    export_attendance_for_sheet,
)
from app.src.core.progress_services import (
    sync_lecture_dates_from_sheet,
    export_lecture_dates_for_sheet,
    sync_lecture_attendance_from_sheet,
    export_lecture_attendance_for_sheet,
    sync_lab_scores_from_sheet,
    export_lab_scores_for_sheet,
    export_lab_subjects_for_sheet,
)

bp = Blueprint("google_v1", __name__, url_prefix="/api/v1/google")


def _verify_api_key() -> tuple | None:
    """Verify X-API-Key header. Returns error response tuple or None if valid."""
    expected_key = current_app.config.get("SHEETS_SYNC_API_KEY")
    provided_key = request.headers.get("X-API-Key")
    if not expected_key or provided_key != expected_key:
        return jsonify({"error": "unauthorized"}), 401
    return None


@bp.post("/in")
def google_import_users() -> tuple:
    """
    Import users and their data from Google Sheets.
    
    Request:
    POST /api/v1/google/in
    Headers: X-API-Key: <SHEETS_SYNC_API_KEY>
    Body:
    {
      "rows": [
        {
          "email": "ivanov.ii@edu.spbstu.ru",
          "fullname": "Иванов Иван Иванович",
          "group_number": "5131001/50001",
          "pass_id": "PASS123",
          "missed_passes": 1
        }
      ]
    }
    """
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    rows = data.get("rows")
    if not isinstance(rows, list):
        return jsonify({"error": "rows must be a list."}), 200

    try:
        payload_rows = [
            SheetUserRow(
                email=row["email"],
                fullname=row.get("fullname"),
                group_number=row.get("group_number"),
                pass_id=row.get("pass_id"),
                missed_passes=int(row["missed_passes"]) if row.get("missed_passes") is not None else None,
            )
            for row in rows
        ]
        result = sync_users_from_sheet(payload_rows)
        return jsonify(result), 200
    except KeyError as error:
        return jsonify({"error": f"row missing field: {error.args[0]}"}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200
    except TypeError:
        return jsonify({"error": "missed_passes must be integer."}), 200


@bp.get("/out")
def google_export_users() -> tuple:
    """
    Export all users and their data to Google Sheets format.
    
    Request:
    GET /api/v1/google/out
    Headers: X-API-Key: <SHEETS_SYNC_API_KEY>
    
    Response: List of users with email, fullname, group_number, pass_id, missed_passes
    """
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    try:
        users = export_users_for_sheet()
        return jsonify({"rows": users}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200


@bp.post("/in-attendance")
def google_import_attendance() -> tuple:
    """
    Import attendance records from Google Sheets.
    
    Request:
    POST /api/v1/google/in-attendance
    Headers: X-API-Key: <SHEETS_SYNC_API_KEY>
    Body:
    {
      "rows": [
        {
          "email": "ivanov.ii@edu.spbstu.ru",
          "timestamp": "2024-05-15T10:30:00Z",
          "attended": true
        }
      ]
    }
    """
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    rows = data.get("rows")
    if not isinstance(rows, list):
        return jsonify({"error": "rows must be a list."}), 200

    try:
        payload_rows = [
            SheetAttendanceRow(
                email=row["email"],
                timestamp=row["timestamp"],
                attended=row.get("attended", True),
            )
            for row in rows
        ]
        result = sync_attendance_from_sheet(payload_rows)
        return jsonify(result), 200
    except KeyError as error:
        return jsonify({"error": f"row missing field: {error.args[0]}"}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200


@bp.get("/out-attendance")
def google_export_attendance() -> tuple:
    """
    Export all attendance records to Google Sheets format.
    
    Request:
    GET /api/v1/google/out-attendance
    Headers: X-API-Key: <SHEETS_SYNC_API_KEY>
    
    Response: List of attendance records with email, timestamp, attended=true
    """
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    try:
        attendance = export_attendance_for_sheet()
        return jsonify({"rows": attendance}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200


@bp.post("/in-lecture-dates")
def google_import_lecture_dates() -> tuple:
    """Import lecture column dates for a semester (sheet headers)."""
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    semester = data.get("semester")
    dates = data.get("dates")
    if semester is None:
        return jsonify({"error": "semester is required."}), 200
    if not isinstance(dates, list):
        return jsonify({"error": "dates must be a list."}), 200

    try:
        result = sync_lecture_dates_from_sheet(int(semester), dates)
        return jsonify(result), 200
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 200


@bp.get("/out-lecture-dates")
def google_export_lecture_dates() -> tuple:
    """Export lecture dates for a semester."""
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    semester = request.args.get("semester", type=int)
    if semester is None:
        return jsonify({"error": "semester query param is required (1 or 2)."}), 200

    try:
        return jsonify(export_lecture_dates_for_sheet(semester)), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200


@bp.post("/in-lecture-attendance")
def google_import_lecture_attendance() -> tuple:
    """
    Import lecture attendance from sheet (П in cell).

    Body:
    {
      "semester": 2,
      "rows": [
        {"email": "averin.mk@edu.spbstu.ru", "date": "2026-02-07", "attended": true}
      ]
    }
    Dates: YYYY-MM-DD or DD.MM.YYYY
    """
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    semester = data.get("semester")
    rows = data.get("rows")
    if semester is None:
        return jsonify({"error": "semester is required."}), 200
    if not isinstance(rows, list):
        return jsonify({"error": "rows must be a list."}), 200

    try:
        payload_rows = [
            SheetLectureAttendanceRow(
                email=row["email"],
                semester=int(semester),
                date=row.get("date") or row.get("session_date"),
                attended=row.get("attended", True),
            )
            for row in rows
        ]
        result = sync_lecture_attendance_from_sheet(payload_rows)
        return jsonify(result), 200
    except KeyError as error:
        return jsonify({"error": f"row missing field: {error.args[0]}"}), 200
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 200


@bp.get("/out-lecture-attendance")
def google_export_lecture_attendance() -> tuple:
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    semester = request.args.get("semester", type=int)
    if semester is None:
        return jsonify({"error": "semester query param is required (1 or 2)."}), 200

    try:
        rows = export_lecture_attendance_for_sheet(semester)
        return jsonify({"semester": semester, "rows": rows}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200


@bp.post("/in-grades")
def google_import_grades() -> tuple:
    """
    Import lab scores from sheet (detailing / practice tabs).

    Body:
    {
      "semester": 2,
      "rows": [
        {
          "email": "averin.mk@edu.spbstu.ru",
          "subject": "Структуры данных",
          "component": "LR1",
          "score": 8
        }
      ]
    }
    """
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    semester = data.get("semester")
    rows = data.get("rows")
    if semester is None:
        return jsonify({"error": "semester is required."}), 200
    if not isinstance(rows, list):
        return jsonify({"error": "rows must be a list."}), 200

    try:
        payload_rows = [
            SheetLabScoreRow(
                email=row["email"],
                semester=int(semester),
                subject=row["subject"],
                component=row["component"],
                score=row.get("score"),
            )
            for row in rows
        ]
        result = sync_lab_scores_from_sheet(payload_rows)
        return jsonify(result), 200
    except KeyError as error:
        return jsonify({"error": f"row missing field: {error.args[0]}"}), 200
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 200


@bp.get("/out-grades")
def google_export_grades() -> tuple:
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    semester = request.args.get("semester", type=int)
    if semester is None:
        return jsonify({"error": "semester query param is required (1 or 2)."}), 200

    try:
        rows = export_lab_scores_for_sheet(semester)
        return jsonify({"semester": semester, "rows": rows}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200


@bp.get("/out-grades-layout")
def google_export_grades_layout() -> tuple:
    """Export subject + LR columns layout for semester sheet setup."""
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error

    semester = request.args.get("semester", type=int)
    if semester is None:
        return jsonify({"error": "semester query param is required (1 or 2)."}), 200

    try:
        subjects = export_lab_subjects_for_sheet(semester)
        return jsonify({"semester": semester, "subjects": subjects}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200
