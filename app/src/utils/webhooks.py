import json
import urllib.request
import urllib.error

from flask import current_app


def send_sync_notification(payload: dict) -> None:
    callback_url = current_app.config.get("SYNC_CALLBACK_URL")
    if not callback_url:
        return

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        callback_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
    except Exception as error:
        current_app.logger.error(
            "Sync callback failed to %s: %s",
            callback_url,
            error,
        )
