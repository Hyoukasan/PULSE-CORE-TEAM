from flask import Blueprint, jsonify, request

from app.src.core.services import (
    ban_user_as_admin,
    list_banned_users,
    resolve_admin_from_request,
    resolve_ban_target_from_request,
    serialize_user_info,
    unban_user_as_admin,
)

bp = Blueprint("bans_v1", __name__, url_prefix="/api/v1/bans")


def _ban_response(user) -> dict:
    return {
        "success": True,
        "user": serialize_user_info(user),
        "ban_expires_at": user.ban_expires_at.isoformat() if user.ban_expires_at else None,
        "is_banned": user.ban_expires_at is not None,
    }


@bp.post("/ban")
def ban_user_bot_route() -> tuple:
    """
    Ban a user (admin only).

    Body example:
    {
      "from": { "telegram_id": 1240188543 },
      "target": { "telegram_id": 987654321 },
      "permanent": true
    }

    Or timed ban:
    {
      "from": { "admin_id": 1 },
      "target": { "email": "student@edu.spbstu.ru" },
      "ban_expires_at": "2026-06-01T00:00:00Z"
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        admin = resolve_admin_from_request(data)
        target = resolve_ban_target_from_request(data)
        permanent = bool(data.get("permanent"))
        ban_expires_at = data.get("ban_expires_at")
        user = ban_user_as_admin(
            admin,
            target,
            ban_expires_at=ban_expires_at,
            permanent=permanent and ban_expires_at is None,
        )
        return jsonify(_ban_response(user)), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200


@bp.post("/unban")
def unban_user_bot_route() -> tuple:
    """
    Unban a user (admin only).

    Body example:
    {
      "from": { "telegram_id": 1240188543 },
      "target": { "telegram_id": 987654321 }
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        admin = resolve_admin_from_request(data)
        target = resolve_ban_target_from_request(data)
        user = unban_user_as_admin(admin, target)
        return jsonify(_ban_response(user)), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200


@bp.get("")
def list_banned_users_route() -> tuple:
    """
    List all currently banned users (admin only).

    Query or JSON-style via query params:
    GET /api/v1/bans?admin_telegram_id=1240188543
    """
    data = dict(request.args)
    if request.is_json:
        data.update(request.get_json(silent=True) or {})

    try:
        resolve_admin_from_request(data)
        banned = list_banned_users()
        return jsonify({"success": True, "count": len(banned), "users": banned}), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 200
