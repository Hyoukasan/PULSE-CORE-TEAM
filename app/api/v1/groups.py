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

bp = Blueprint("groups_v1", __name__, url_prefix="/api/v1/groups")

@bp.post("/assign")
def assign_user_to_group_route() -> tuple:
    data = request.get_json(silent=True) or {}
    try:
        payload = AssignUserToGroupInput(
            user_id=int(data["user_id"]),
            group_number=data["group_number"],
        )
        group = assign_user_to_group(payload)
        return jsonify({"group_id": group.id, "group_number": group.number}), 200
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200
    except TypeError:
        return jsonify({"error": "user_id must be integer."}), 200


@bp.post("/sync")
def sync_groups_route() -> tuple:
    expected_key = current_app.config.get("SHEETS_SYNC_API_KEY")
    provided_key = request.headers.get("X-API-Key")
    if not expected_key or provided_key != expected_key:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    rows = data.get("rows")
    if not isinstance(rows, list):
        return jsonify({"error": "rows must be a list."}), 200

    try:
        payload_rows = [SheetGroupRow(number=row["number"], name=row["name"]) for row in rows]
        result = sync_groups_from_sheet(payload_rows)
        return jsonify(result), 200
    except KeyError as error:
        return jsonify({"error": f"row missing field: {error.args[0]}"}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200
