import json
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from app.src.core.schemas import (
    RegisterUserInput,
)
from app.src.core.services import (
    get_user_by_id,
    get_user_by_telegram_id,
    get_user_by_vk_id,
    get_all_students,
    register_user,
    serialize_user_info,
)

bp = Blueprint("users_v1", __name__, url_prefix="/api/v1/users")


@bp.post("/register")
def register_user_route() -> tuple:
    data = request.get_json(silent=True) or {}
    try:
        payload = RegisterUserInput(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            role=data.get("role", "practitioner"),
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
        return jsonify({"error": f"missing field: {error.args[0]}"}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200


@bp.get("/<int:user_id>")
def get_user_route(user_id: int) -> tuple:
    user = get_user_by_id(user_id)
    if user is None:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"success": True, "user": serialize_user_info(user)}), 200


@bp.get("/students")
def get_students_route() -> tuple:
    students = get_all_students()
    return jsonify({"success": True, "students": students}), 200


@bp.post("/ban")
def ban_user_route() -> tuple:
    """Admin can set or clear `ban_expires_at` for a user.

    Payload JSON (examples):
    - Ban until specific time:
      {"admin_id": 1, "user_id": 42, "ban_expires_at": "2026-05-20T12:00:00Z"}
    - Unban (clear ban):
      {"admin_id": 1, "user_id": 42, "ban_expires_at": null}
    """
    data = request.get_json(silent=True) or {}
    # Identify admin: accept admin_id or admin_telegram_id or admin_vk_id
    admin = None
    if data.get("admin_id") is not None:
        admin = get_user_by_id(int(data["admin_id"]))
        if admin is None:
            admin = get_user_by_telegram_id(int(data["admin_id"]))
        if admin is None:
            admin = get_user_by_vk_id(int(data["admin_id"]))
    elif data.get("admin_telegram_id") is not None:
        admin = get_user_by_telegram_id(int(data["admin_telegram_id"]))
    elif data.get("admin_vk_id") is not None:
        admin = get_user_by_vk_id(int(data["admin_vk_id"]))
    else:
        return jsonify({"error": "missing admin identifier (admin_id or admin_telegram_id or admin_vk_id)"}), 200

    if admin is None or admin.role.role != "admin":
        return jsonify({"error": "admin not found or not authorized"}), 403

    # Identify target user: accept user_id, target_user_id, target_telegram_id or target_vk_id
    user = None
    if data.get("user_id") is not None:
        user = get_user_by_id(int(data["user_id"]))
    elif data.get("target_user_id") is not None:
        user = get_user_by_id(int(data["target_user_id"]))
    elif data.get("target_telegram_id") is not None:
        user = get_user_by_telegram_id(int(data["target_telegram_id"]))
    elif data.get("target_vk_id") is not None:
        user = get_user_by_vk_id(int(data["target_vk_id"]))
    else:
        return jsonify({"error": "missing target identifier (user_id or target_user_id or target_telegram_id or target_vk_id)"}), 200

    if user is None:
        return jsonify({"error": "target user not found"}), 404

    # Determine ban action: explicit null -> unban; "ban_expires_at" string -> parse; "permanent": true -> set far future
    ban_provided = "ban_expires_at" in data
    permanent = bool(data.get("permanent"))
    if ban_provided and data.get("ban_expires_at") is None:
        # clear ban
        user.ban_expires_at = None
    elif ban_provided and data.get("ban_expires_at") is not None:
        ban_value = data.get("ban_expires_at")
        if isinstance(ban_value, str) and ban_value.endswith("Z"):
            ban_value = ban_value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(ban_value)
        except Exception:
            return jsonify({"error": "ban_expires_at must be ISO 8601 string or null"}), 200
        user.ban_expires_at = parsed
    elif permanent:
        user.ban_expires_at = datetime(9999, 12, 31, 23, 59, 59)
    else:
        return jsonify({"error": "provide 'ban_expires_at' (string or null) or 'permanent': true"}), 200

    # Commit change
    try:
        from app.src.integrations.db import db

        db.session.add(user)
        db.session.commit()
    except Exception:
        return jsonify({"error": "unable to update user ban status"}), 500

    return jsonify({"success": True, "user": serialize_user_info(user), "ban_expires_at": user.ban_expires_at.isoformat() if user.ban_expires_at else None}), 200
