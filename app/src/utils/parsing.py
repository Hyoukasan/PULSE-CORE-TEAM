import json

from flask import request

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