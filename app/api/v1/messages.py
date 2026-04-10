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

bp = Blueprint("messages_v1", __name__, url_prefix="/api/v1/messages")

@bp.post("/send")
def send_message_route() -> tuple:
    data = request.get_json(silent=True) or {}
    try:
        sender_data = data["from"]
        message_data = data["message"]
        to_data = data.get("to") or {}
        payload = SendMessageInput(
            sender=MessageSenderInput(
                user_id=sender_data.get("user_id"),
                email=sender_data.get("email"),
                fullname=sender_data.get("fullname"),
                group=sender_data.get("group"),
                role=sender_data["role"],
                platform=sender_data.get("platform"),
                telegram_id=(
                    int(sender_data["telegram_id"])
                    if sender_data.get("telegram_id") is not None
                    else None
                ),
            ),
            message=MessagePayload(
                type=message_data.get("type"),
                text=message_data["text"],
                timestamp=message_data.get("timestamp"),
            ),
            to_user_id=(
                int(data["to_user_id"])
                if data.get("to_user_id") is not None
                else (
                    int(to_data["user_id"])
                    if to_data.get("user_id") is not None
                    else None
                )
            ),
            to_telegram_id=(
                int(data["to_telegram_id"])
                if data.get("to_telegram_id") is not None
                else (
                    int(to_data["telegram_id"])
                    if to_data.get("telegram_id") is not None
                    else None
                )
            ),
        )
        message = send_message(payload)
        return jsonify({
            "success": True,
            "message_id": message.id,
            "status": message.status,
            "created_at": message.created_at.isoformat(),
        }), 200
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200
    except TypeError:
        return jsonify({"error": "telegram_id and user_id must be integers."}), 200

