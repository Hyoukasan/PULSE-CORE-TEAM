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

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


@bp.get("/health")
def health() -> tuple:
    return jsonify({"status": "ok"}), 200


@bp.get("/")
def api_root() -> tuple:
    return jsonify({"status": "ok", "api": "v1"}), 200


@bp.post("/users/register")
def register_user_route() -> tuple:
    data = request.get_json(silent=True) or {}
    try:
        payload = RegisterUserInput(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            role=data["role"],
            fullname=data.get("fullname"),
        )
        user = register_user(payload)
        return jsonify({
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "fullname": user.fullname,
        }), 201
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.post("/auth/login")
@bp.post("/auth/enter")
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
        return jsonify({"error": f"missing field: {error.args[0]}"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except TypeError:
        return jsonify({"error": "vk_id must be integer."}), 400


@bp.post("/messages/send")
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
        return jsonify({"error": f"missing field: {error.args[0]}"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except TypeError:
        return jsonify({"error": "telegram_id and user_id must be integers."}), 400


@bp.post("/auth/verify")
def verify_user_route() -> tuple:
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    if not email:
        return jsonify({"error": "missing field: email"}), 400

    user = get_user_by_email(email)
    if user is None:
        return jsonify({"role": "wrong_mail"}), 200

    role_name = user.role.role
    if role_name == "professor":
        role_name = "teacher"
    elif role_name not in {"student", "student_lecture", "admin"}:
        role_name = "student"

    return jsonify({"role": role_name}), 200


@bp.post("/attendance/excuse")
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
        return jsonify({"error": f"missing field: {error.args[0]}"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.post("/attendance/pass")
def attendance_pass_route() -> tuple:
    data = request.get_json(silent=True) or {}
    try:
        payload = AttendancePassInput(pass_id=data["pass_id"])
        result = check_attendance_pass(payload)
        if result["status"] == "normal_pass":
            return jsonify({"message": "visit confirmed"}), 200
        return jsonify(result), 200
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@bp.get("/users/<int:user_id>")
def get_user_route(user_id: int) -> tuple:
    user = get_user_by_id(user_id)
    if user is None:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"success": True, "user": serialize_user_info(user)}), 200


@bp.post("/groups/assign")
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
        return jsonify({"error": f"missing field: {error.args[0]}"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except TypeError:
        return jsonify({"error": "user_id must be integer."}), 400


@bp.post("/groups/sync")
def sync_groups_route() -> tuple:
    expected_key = current_app.config.get("SHEETS_SYNC_API_KEY")
    provided_key = request.headers.get("X-API-Key")
    if not expected_key or provided_key != expected_key:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    rows = data.get("rows")
    if not isinstance(rows, list):
        return jsonify({"error": "rows must be a list."}), 400

    try:
        payload_rows = [SheetGroupRow(number=row["number"], name=row["name"]) for row in rows]
        result = sync_groups_from_sheet(payload_rows)
        return jsonify(result), 200
    except KeyError as error:
        return jsonify({"error": f"row missing field: {error.args[0]}"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


def parse_bot_webhook_request() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        try:
            payload = request.get_data(as_text=True)
            data = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            data = {}

    if isinstance(data.get("user_data"), dict):
        data = data["user_data"]

    return {
        "action": data.get("action"),
        "telegram_id": data.get("telegram_id") or data.get("telegramId") or data.get("telegramid"),
        "mail": data.get("mail") or data.get("email"),
        "password": data.get("password"),
        "fullname": data.get("fullname"),
        "bot_id": data.get("bot_id") or data.get("botId") or data.get("botid"),
        "platform": data.get("platform"),
        "raw": data,
    }


@bp.post("/auth/bot")
@bp.post("/auth/bot/webhook")
@bp.post("/webhook/bot")
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