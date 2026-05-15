import json

from flask import Blueprint, current_app, jsonify, request

from app.src.core.schemas import (
    SheetUserRow,
    SheetAttendanceRow,
)
from app.src.core.services import (
    sync_users_from_sheet,
    sync_attendance_from_sheet,
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
