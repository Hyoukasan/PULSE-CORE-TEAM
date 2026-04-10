import json

from flask import Blueprint, current_app, jsonify, request

from app.src.core.schemas import (
    RegisterUserInput,
)
from app.src.core.services import (
    get_user_by_id,
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
