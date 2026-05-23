import threading
import time
import traceback
import requests

from flask import current_app

from app.src.core.services import (
    export_users_for_sheet,
    export_groups_for_sheet,
    export_attendance_for_sheet,
)


def _export_once(app) -> None:
    with app.app_context():
        export_url = app.config.get("DB_EXPORT_URL")
        if not export_url:
            app.logger.debug("DB_EXPORT_URL not configured; skipping export.")
            return

        payload = {
            "users": export_users_for_sheet(),
            "groups": export_groups_for_sheet(),
            "attendance": export_attendance_for_sheet(),
            "timestamp": int(time.time()),
        }

        try:
            resp = requests.post(export_url, json=payload, timeout=30)
            app.logger.info(f"DB export posted: status={resp.status_code}")
        except Exception as e:
            app.logger.error(f"Failed to post DB export: {e}\n{traceback.format_exc()}")


def _worker_loop(app, interval_seconds: int) -> None:
    app.logger.info(f"DB export worker started, interval={interval_seconds}s")
    while True:
        try:
            _export_once(app)
        except Exception:
            app.logger.exception("Unhandled exception in DB export worker")
        time.sleep(interval_seconds)


def start_db_export_worker(app, interval_seconds: int | None = None) -> threading.Thread:
    """Start background thread that periodically exports DB snapshot to configured URL.

    Returns the Thread object (daemon).
    """
    if interval_seconds is None:
        interval_seconds = app.config.get("DB_EXPORT_INTERVAL_SECONDS", 300)

    thread = threading.Thread(target=_worker_loop, args=(app, interval_seconds), daemon=True, name="db-exporter")
    thread.start()
    return thread
