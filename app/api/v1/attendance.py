import json

from flask import Blueprint, current_app, jsonify, request

from app.src.core.schemas import (
    AssignUserToGroupInput,
    AuthLoginInput,
    AttendanceExcuseInput,
    AttendancePassInput,
    MessagePayload,
    MessageSenderInput,
    RegisterUserInput,
    SendMessageInput,
    SheetGroupRow,
    BotAuthInput,
)
from app.src.core.services import (
    assign_user_to_group,
    authenticate_user,
    check_attendance_pass,
    get_user_by_email,
    get_user_by_id,
    register_user,
    send_message,
    serialize_user_info,
    submit_attendance_excuse,
    sync_groups_from_sheet,
    bot_authenticate,
)

bp = Blueprint("attendance_v1", __name__, url_prefix="/api/v1/attendance")



@bp.post("/excuse")
def submit_attendance_excuse_route() -> tuple:
    data = request.get_json(silent=True) or {}
    try:
        payload = AttendanceExcuseInput(
            email=data["email"],
            reason=data["reason"],
            file_url=data.get("file_url"),
            timestamp=data.get("timestamp"),
        )
        excuse = submit_attendance_excuse(payload)
        return jsonify({
            "success": True,
            "excuse_id": excuse.id,
            "created_at": excuse.created_at.isoformat(),
        }), 201
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200


@bp.post("/pass")
def attendance_pass_route() -> tuple:
    data = request.get_json(silent=True) or {}
    try:
        payload = AttendancePassInput(pass_id=data["pass_id"])
        result = check_attendance_pass(payload)
        if result["status"] == "normal_pass":
            return jsonify({"message": "visit confirmed"}), 200
        return jsonify(result), 200
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200
