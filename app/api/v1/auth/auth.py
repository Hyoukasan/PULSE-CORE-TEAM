from flask import Blueprint, current_app, jsonify, request

from app.src.core.schemas import (
    AssignUserToGroupInput,
    RegisterUserInput,
    SheetGroupRow,
    BotAuthInput,
)
from app.src.core.services import (
    assign_user_to_group,
    register_user,
    sync_groups_from_sheet,
    bot_authenticate,
)

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


@bp.get("/health")
def health() -> tuple:
    return jsonify({"status": "ok"}), 200


@bp.post("/users/register")
def register_user_route() -> tuple:
    data = request.get_json(silent=True) or {}
    try:
        payload = RegisterUserInput(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            role=data["role"],
        )
        user = register_user(payload)
        return jsonify({"id": user.id, "email": user.email, "username": user.username}), 201
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


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


@bp.post("/auth/bot")
def bot_auth_route() -> tuple:
    data = request.get_json(silent=True) or {}
    try:
        payload = BotAuthInput(
            action=data["action"],
            telegram_id=int(data["telegram_id"]),
            mail=data["mail"],
            password=data["password"],
        )
        response = bot_authenticate(payload)
        return jsonify({"response": response, "role": response}), 200
    except KeyError as error:
        return jsonify({"error": f"missing field: {error.args[0]}"}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except TypeError:
        return jsonify({"error": "telegram_id must be integer."}), 400