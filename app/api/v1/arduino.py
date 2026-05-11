import base64
import os
from flask import Blueprint, request, jsonify, current_app
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key, load_pem_private_key
from cryptography.exceptions import InvalidSignature 

from app.src.domain.user_pass_key import UserPassKey
from app.src.integrations.db import db

publickey = None
privatekey = None

def load_public_key(app):
    global publickey, privatekey
    pub_path = app.config.get("ARDUINO_PUBLIC_KEY_PATH")
    if pub_path and os.path.exists(pub_path):
        with open(pub_path, "rb") as f:
            publickey = load_pem_public_key(f.read())
    
    priv_path = app.config.get("SERVER_PRIVATE_KEY_PATH", "private.pem")
    if os.path.exists(priv_path):
        with open(priv_path, "rb") as f:
            privatekey = load_pem_private_key(f.read(), password=None)

def verify(data, sign):
    global publickey
    if publickey is None:
        return False
    
    data_clean = data.strip()
    
    try:

        try:
            if all(c in "0123456789abcdefABCDEF" for c in sign) and len(sign) > 128:
                signature = bytes.fromhex(sign)
            else:
                signature = base64.b64decode(sign)
        except:
            signature = base64.b64decode(sign)

        for p in [data_clean.encode("utf-8"), (data_clean + "\0").encode("utf-8")]:
            try:
                publickey.verify(signature, p, padding.PKCS1v15(), hashes.SHA256())
                return True 
            except InvalidSignature:
                continue
        return False
    except Exception as e:
        current_app.logger.error(f"Error: {e}")
        return False

def sign_data(data):
    global privatekey
    if not privatekey: return None
    signature = privatekey.sign(data.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("utf-8")

bp = Blueprint("arduino_v1", __name__, url_prefix="/api/v1/arduino")

@bp.before_request
def check_keys():
    if publickey is None: load_public_key(current_app)

@bp.route("/verify", methods=["POST"])
def verify_pass_key():
    req = request.get_json(silent=True) or {}
    pass_key = req.get("pass_key")
    sign = req.get("sign")
    
    if not pass_key or not sign:
        return jsonify({"status": 400, "message": "Missing fields"}), 400

    if not verify(pass_key, sign):
        return jsonify({"status": 400, "message": "Invalid signature"}), 400

    user_pass_key = db.session.query(UserPassKey).filter_by(pass_key=pass_key).first()
    if user_pass_key is None:
        return jsonify({"status": 400, "message": "Invalid pass key"}), 400

    server_sign = sign_data(f"OK:{pass_key}")

    return jsonify({
        "status": 200, 
        "message": "OK",
        "server_sign": server_sign
    }), 200