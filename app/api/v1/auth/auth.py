import json

from flask import Blueprint, current_app, jsonify, request

from app.src.core.schemas import (
    AssignUserToGroupInput,
    AuthLoginInput,
    RegisterUserInput,
    SheetGroupRow,
    BotAuthInput,
)
from app.src.core.services import (
    assign_user_to_group,
    authenticate_user,
    get_user_by_email,
    get_user_by_id,
    register_user,
    serialize_user_info,
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
        return jsonify({
            "error": "invalid request",
            "missing": [
                field
                for field in ("action", "telegram_id", "mail", "password")
                if not data[field]
            ],
            "received": data["raw"],
        }), 400

    try:
        payload = BotAuthInput(
            action=data["action"],
            telegram_id=int(data["telegram_id"]),
            mail=data["mail"],
            password=data["password"],
        )
        response = bot_authenticate(payload)
        return jsonify({"role": response}), 200
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except TypeError:
        return jsonify({"error": "telegram_id must be integer."}), 400


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