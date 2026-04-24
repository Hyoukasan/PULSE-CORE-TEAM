import base64
import os
from flask import Blueprint, request, jsonify, current_app
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature

from app.src.domain.user_pass_key import UserPassKey
from app.src.integrations.db import db

publickey = None


def load_public_key(app):
    global publickey
    key_path = app.config.get("ARDUINO_PUBLIC_KEY_PATH")
    if not key_path or not os.path.exists(key_path):
        app.logger.warning(f"Arduino public key not found at: {key_path}")
        return False
    try:
        with open(key_path, "rb") as f:
            publickey = load_pem_public_key(f.read())
        app.logger.info(f"Arduino public key loaded from: {key_path}")
        return True
    except Exception as e:
        app.logger.error(f"Failed to load Arduino public key: {e}")
        return False


def verify(data, sign):
    global publickey
    if publickey is None:
        return False
    try:
        signature = base64.b64decode(sign)
        publickey.verify(
            signature,
            data.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except (InvalidSignature, Exception):
        return False


bp = Blueprint("arduino_v1", __name__, url_prefix="/api/v1/arduino")


@bp.before_request
def load_key_if_needed():
    global publickey
    if publickey is None:
        load_public_key(current_app)


@bp.route("/verify", methods=["POST"])
def verify_pass_key():
    req = request.get_json(silent=True) or {}
    pass_key = req.get("pass_key")
    sign = req.get("sign")
    if not pass_key or not sign:
        return jsonify({"status": 400, "message": "Missing fields"}), 400

    user_pass = db.session.execute(
        db.select(UserPassKey).where(UserPassKey.pass_key == pass_key)
    ).scalar_one_or_none()

    if not user_pass:
        return jsonify({"status": 404, "message": "User not found"}), 404

    if verify(pass_key, sign):
        return jsonify({"status": 200, "message": "OK"}), 200
    else:
        return jsonify({"status": 400, "message": "Invalid signature"}), 400