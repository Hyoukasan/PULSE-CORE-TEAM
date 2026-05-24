from flask import Blueprint, current_app, jsonify, request

from app.src.core.schemas import (
    AddToQueueInput,
    RemoveFromQueueInput,
    GetQueuePositionInput,
    GetQueueForLessonInput,
)
from app.src.core.services import (
    add_to_queue,
    add_to_queue_by_bot,
    remove_from_queue,
    remove_from_queue_by_bot,
    get_queue_position,
    get_queue_position_by_bot,
    get_queue_for_lesson,
    get_admin_user,
)

bp = Blueprint("queue_v1", __name__, url_prefix="/api/v1/queue")


@bp.post("/add")
def add_to_queue_route() -> tuple:
    """
    Добавить студента в очередь на занятие.

    JSON payload (direct):
    {
        "student_id": 1,
        "professor_id": 2,
        "lesson_date": "2026-05-15T10:00:00Z",
        "labs_count": 2
    }

    JSON payload (bot):
    {
        "telegram_id": 123456,
        "vk_id": 789012,
        "labs_count": 2,
        "lesson_date": "2026-05-15T10:00:00Z"
    }
    """
    data = request.get_json(silent=True) or {}
    current_app.logger.debug("Queue add request data: %s", data)
    try:
        if data.get("student_id") and data.get("professor_id"):
            result = add_to_queue(data)
        else:
            result = add_to_queue_by_bot(data)
        if result.get("status") == "banned":
            return jsonify(result), 200
        return jsonify(result), 201
    except ValueError as error:
        current_app.logger.info("Queue add validation failed: %s; data=%s", str(error), data)
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.exception("Error adding to queue; data=%s", data)
        return jsonify({"error": "Internal server error"}), 500


@bp.post("/remove")
def remove_from_queue_route() -> tuple:
    """
    Удалить студента из очереди.

    JSON payload (direct):
    {
        "student_id": 1,
        "professor_id": 2,
        "lesson_date": "2026-05-15T10:00:00Z"
    }

    JSON payload (bot):
    {
        "telegram_id": 123456,
        "vk_id": 789012,
        "lesson_date": "2026-05-15T10:00:00Z"
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        if data.get("student_id") and data.get("professor_id"):
            result = remove_from_queue(data)
        else:
            result = remove_from_queue_by_bot(data)
        return jsonify(result), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error removing from queue: {error}")
        return jsonify({"error": "Internal server error"}), 500


@bp.post("/position")
def get_queue_position_route() -> tuple:
    """
    Получить позицию студента в очереди.

    JSON payload (direct):
    {
        "student_id": 1,
        "professor_id": 2,
        "lesson_date": "2026-05-15T10:00:00Z"
    }

    JSON payload (bot):
    {
        "telegram_id": 123456,
        "vk_id": 789012,
        "lesson_date": "2026-05-15T10:00:00Z"
    }
    """
    data = request.get_json(silent=True) or {}
    try:
        if data.get("student_id") and data.get("professor_id"):
            result = get_queue_position(data)
        else:
            result = get_queue_position_by_bot(data)
        return jsonify(result), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error getting queue position: {error}")
        return jsonify({"error": "Internal server error"}), 500


@bp.get("/lesson/<lesson_date>")
def get_queue_for_lesson_route_default(lesson_date: str) -> tuple:
    """
    Получить всю очередь для занятия (по умолчанию для админа).
    
    URL: /api/v1/queue/lesson/2026-05-15T00:00:00Z
    
    Используется для случаев, когда один админ управляет очередью.
    В будущем можно расширить для нескольких преподавателей.
    """
    try:
        admin = get_admin_user()
        if admin is None:
            return jsonify({"error": "Admin user not found."}), 404
        
        payload = {
            "professor_id": admin.id,
            "lesson_date": lesson_date
        }
        result = get_queue_for_lesson(payload)
        return jsonify(result), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error getting queue for lesson: {error}")
        return jsonify({"error": "Internal server error"}), 500


@bp.get("/lesson/<int:professor_id>/<lesson_date>")
def get_queue_for_lesson_route(professor_id: int, lesson_date: str) -> tuple:
    """
    Получить всю очередь для занятия конкретного преподавателя.
    
    URL: /api/v1/queue/lesson/2/2026-05-15T00:00:00Z
    """
    try:
        payload = {
            "professor_id": professor_id,
            "lesson_date": lesson_date
        }
        result = get_queue_for_lesson(payload)
        return jsonify(result), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error getting queue for lesson: {error}")
        return jsonify({"error": "Internal server error"}), 500
