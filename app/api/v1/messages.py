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
    send_broadcast,
    serialize_message,
    serialize_user_info,
    submit_attendance_excuse,
    sync_groups_from_sheet,
    bot_authenticate,
    get_messages_for_user,
    get_messages_for_bot_user,
    get_all_groups,
    get_students_by_group_id,
    poll_broadcast_messages_for_platform,
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
        # If both IDs are provided in the request, prefer telegram_id silently.
        # Previously this raised an error; prefer telegram where available.

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
            # Lookup: prefer telegram lookup if provided, otherwise try vk
            if data.get("telegram_id") is not None:
                user = get_user_by_telegram_id(int(data["telegram_id"]))
            elif data.get("vk_id") is not None:
                user = get_user_by_vk_id(int(data["vk_id"]))

            if user is None:
                raise ValueError("Sender not found.")
            if user.role.role not in {"practitioner", "listener"}:
                raise ValueError("Only practitioner or listener can send messages via flat payload.")

            # Prefer telegram_id when the user has both IDs set in DB.
            if user.telegram_id is not None:
                sender = MessageSenderInput(
                    user_id=user.id,
                    role=user.role.role,
                    telegram_id=user.telegram_id,
                    vk_id=None,
                )
            else:
                sender = MessageSenderInput(
                    user_id=user.id,
                    role=user.role.role,
                    telegram_id=None,
                    vk_id=user.vk_id,
                )
        else:
            sender = MessageSenderInput(
                user_id=(
                    int(sender_data["user_id"]) if sender_data.get("user_id") is not None
                    else (int(sender_data["admin_id"]) if sender_data.get("admin_id") is not None
                    else (int(data["user_id"]) if data.get("user_id") is not None else (int(data["admin_id"]) if data.get("admin_id") is not None else None)))
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
            to_group_number=(
                data.get("to_group_number")
                if data.get("to_group_number") is not None
                else (
                    to_data.get("group_number")
                    if to_data.get("group_number") is not None
                    else None
                )
            ),
        )

        # If admin requests broadcast to group
        if payload.to_group_number is not None:
            result = send_broadcast(payload)
            return jsonify({"success": True, "broadcast_created": result.get("created", 0)}), 200

        message = send_message(payload)
        return jsonify({
            "success": True,
            "message": serialize_message(message),
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
        telegram_id = request.args.get("telegram_id")
        vk_id = request.args.get("vk_id")

        if telegram_id is not None or vk_id is not None:
            if telegram_id is not None:
                telegram_id = int(telegram_id)
            if vk_id is not None:
                vk_id = int(vk_id)
            messages = get_messages_for_bot_user(
                telegram_id=telegram_id,
                vk_id=vk_id,
            )
            return jsonify({"success": True, "messages": messages}), 200

        messages = get_messages_for_admin()
        return jsonify({"success": True, "messages": messages}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error fetching admin messages: {error}")
        return jsonify({"error": "Internal server error"}), 500


@bp.get("/broadcast/poll")
def poll_broadcast_route() -> tuple:
    """
    Poll pending group broadcasts for delivery via Telegram or VK bot.

    Query: platform=telegram | vk

    Returns grouped broadcast text, recipient_bot_ids and recipients
    (only telegram_id or vk_id for the requested platform).
    Included messages are marked message_type=used_broadcast.
  """
    platform = request.args.get("platform")
    if not platform:
        return jsonify({"error": "platform query param is required (telegram or vk)."}), 200

    try:
        result = poll_broadcast_messages_for_platform(platform)
        current_app.logger.info(
            "broadcast poll platform=%s deliveries=%s",
            result.get("platform"),
            result.get("deliveries"),
        )
        return jsonify({"success": True, "kind": "broadcast_poll", **result}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200
    except Exception as error:
        current_app.logger.error(f"Error polling broadcast messages: {error}")
        return jsonify({"error": "Internal server error"}), 500


@bp.get("/<int:user_id>")
def get_user_messages_route(user_id: int) -> tuple:
    try:
        try:
            messages = get_messages_for_user(user_id)
        except ValueError:
            messages = get_messages_for_bot_user(
                telegram_id=user_id,
                vk_id=user_id,
            )
        return jsonify({"success": True, "messages": messages}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error fetching user messages for {user_id}: {error}")
        return jsonify({"error": "Internal server error"}), 500


@bp.get("/groups/list")
def get_groups_route() -> tuple:
    """Get all existing groups.
    
    Returns list with id, number, and name for each group.
    Used by bot to fetch available groups before sending broadcast.
    """
    try:
        groups = get_all_groups()
        return jsonify({"success": True, "groups": groups}), 200
    except Exception as error:
        current_app.logger.error(f"Error fetching groups: {error}")
        return jsonify({"error": "Internal server error"}), 500


@bp.get("/groups/<int:group_id>/students")
def get_group_students_route(group_id: int) -> tuple:
    """Get all student user IDs in a specific group.
    
    Returns list of user.id for each student in the group.
    Used by bot to get student IDs before sending individual messages.
    """
    try:
        result = get_students_by_group_id(group_id)
        return jsonify({"success": True, **result}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error fetching students for group {group_id}: {error}")
        return jsonify({"error": "Internal server error"}), 500

