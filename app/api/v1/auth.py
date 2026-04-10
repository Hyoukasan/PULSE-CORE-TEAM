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
from app.src.utils.parsing import *

bp = Blueprint("auth_v1", __name__, url_prefix="/api/v1/auth")

@bp.post("/login")
def login_route() -> tuple:
    data = request.get_json(silent=True) or {}
    try:
        payload = AuthLoginInput(
            email=data["email"],
            password=data["password"],
            platform=data.get("platform"),
            vk_id=int(data["vk_id"]) if data.get("vk_id") is not None else None,
        )
        user = authenticate_user(payload)
        return jsonify({"success": True, "user": serialize_user_info(user)}), 200
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200
    except TypeError:
        return jsonify({"error": "vk_id must be integer."}), 200

@bp.post("/verify")
def verify_user_route() -> tuple:
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    if not email:
        return jsonify({"error": "missing field: email"}), 200

    user = get_user_by_email(email)
    if user is None:
        return jsonify({"role": "wrong_mail"}), 200

    role_name = user.role.role
    if role_name == "professor":
        role_name = "teacher"
    elif role_name not in {"student", "student_lecture", "practitioner", "listener", "admin"}:
        role_name = "student"

    return jsonify({"role": role_name}), 200

@bp.post("/bot")
def bot_auth_route() -> tuple:
    data = parse_bot_webhook_request()

    if data["bot_id"] and data["platform"] and not any(
        data[field] for field in ("action", "telegram_id", "mail", "password")
    ):
        return jsonify({
            "role": "bot_check_ok",
            "bot_id": data["bot_id"],
            "platform": data["platform"],
        }), 200

    if not data["action"] or not data["telegram_id"] or not data["mail"] or not data["password"]:
        missing_fields = [
            field
            for field in ("action", "telegram_id", "mail", "password")
            if not data[field]
        ]
        return jsonify({
            "error": "invalid request",
            "missing": missing_fields,
            "missing_field": missing_fields[0] if len(missing_fields) == 1 else None,
        }), 200

    try:
        payload = BotAuthInput(
            action=data["action"],
            telegram_id=int(data["telegram_id"]),
            mail=data["mail"],
            password=data["password"],
            fullname=data.get("fullname"),
        )
        response = bot_authenticate(payload)
        return jsonify({"role": response}), 200
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 200
    except ValueError as error:
        message = str(error)
        if "email" in message:
            return jsonify({"error": "wrong_mail"}), 200
        if "password" in message:
            return jsonify({"error": "wrong_password"}), 200
        return jsonify({"error": message}), 200
    except TypeError:
        return jsonify({"error": "telegram_id must be integer."}), 200


# @bp.post("/auth/bot")
# @bp.post("/auth/bot/webhook")
# @bp.post("/webhook/bot")
# def bot_auth_route() -> tuple:
#     data = request.get_json(silent=True) or {}
#     try:
#         payload = BotAuthInput(
#             action=data["action"],
#             telegram_id=int(data["telegram_id"]),
#             mail=data["mail"],
#             password=data["password"],
#         )
#         response = bot_authenticate(payload)
#         return jsonify({"response": response, "role": response}), 200
#     except KeyError as error:
#         return jsonify({"error": f"missing field: {error.args[0]}"}), 400
#     except ValueError as error:
#         return jsonify({"error": str(error)}), 400
#     except TypeError:
#         return jsonify({"error": "telegram_id must be integer."}), 400