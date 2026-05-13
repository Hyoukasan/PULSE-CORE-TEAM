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
    get_messages_for_admin,
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
        sender_data = data.get("from") or {}
        message_data = data.get("message")
        to_data = data.get("to") or {}

        if message_data is None:
            message_data = {
                "type": data.get("type"),
                "text": data.get("text"),
                "timestamp": data.get("timestamp"),
            }

        if not data.get("from") and not (data.get("telegram_id") is not None or data.get("vk_id") is not None):
            raise ValueError("Flat bot payload must include either telegram_id or vk_id.")
        if not data.get("from") and data.get("telegram_id") is not None and data.get("vk_id") is not None:
            raise ValueError("Flat bot payload must include either telegram_id or vk_id, not both.")

        if isinstance(message_data, str):
            message_data = {"type": "text", "text": message_data}

        if message_data.get("text") is None:
            raise KeyError("text")

        is_bot_flat_payload = (
            not data.get("from")
            and (data.get("telegram_id") is not None or data.get("vk_id") is not None)
        )

        if is_bot_flat_payload:
            from app.src.core.services import get_user_by_telegram_id, get_user_by_vk_id
            
            user = None
            if data.get("telegram_id") is not None:
                user = get_user_by_telegram_id(int(data["telegram_id"]))
            elif data.get("vk_id") is not None:
                user = get_user_by_vk_id(int(data["vk_id"]))
            
            if user is None:
                raise ValueError("Sender not found.")
            if user.role.role not in {"practitioner", "listener"}:
                raise ValueError("Only practitioner or listener can send messages via flat payload.")
            
            sender = MessageSenderInput(
                user_id=user.id,
                role=user.role.role,
                telegram_id=user.telegram_id,
                vk_id=user.vk_id,
            )
        else:
            sender = MessageSenderInput(
                user_id=(
                    int(sender_data["user_id"])
                    if sender_data.get("user_id") is not None
                    else (
                        int(data["user_id"])
                        if data.get("user_id") is not None
                        else None
                    )
                ),
                role=(
                    sender_data.get("role")
                    if sender_data.get("role") is not None
                    else data.get("role")
                ),
                email=(
                    sender_data.get("email")
                    if sender_data.get("email") is not None
                    else data.get("email")
                ),
                fullname=(
                    sender_data.get("fullname")
                    if sender_data.get("fullname") is not None
                    else data.get("fullname")
                ),
                group=(
                    sender_data.get("group")
                    if sender_data.get("group") is not None
                    else data.get("group")
                ),
                platform=(
                    sender_data.get("platform")
                    if sender_data.get("platform") is not None
                    else data.get("platform")
                ),
                telegram_id=(
                    int(sender_data["telegram_id"])
                    if sender_data.get("telegram_id") is not None
                    else (
                        int(data["telegram_id"])
                        if data.get("telegram_id") is not None
                        else None
                    )
                ),
                vk_id=(
                    int(sender_data["vk_id"])
                    if sender_data.get("vk_id") is not None
                    else (
                        int(data["vk_id"])
                        if data.get("vk_id") is not None
                        else None
                    )
                ),
            )

        payload = SendMessageInput(
            sender=sender,
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
            to_vk_id=(
                int(data["to_vk_id"])
                if data.get("to_vk_id") is not None
                else (
                    int(to_data["vk_id"])
                    if to_data.get("vk_id") is not None
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
        return jsonify({"error": "telegram_id, vk_id and user_id must be integers."}), 200


@bp.get("")
def get_admin_messages_route() -> tuple:
    try:
        messages = get_messages_for_admin()
        return jsonify({"success": True, "messages": messages}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error fetching admin messages: {error}")
        return jsonify({"error": "Internal server error"}), 500

