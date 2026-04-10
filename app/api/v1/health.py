import json

from flask import Blueprint, jsonify, request

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1/health")

@bp.get("/")
def health() -> tuple:
    return jsonify({"status": "ok"}), 200
