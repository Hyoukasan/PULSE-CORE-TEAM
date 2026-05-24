from flask import Blueprint, current_app, jsonify, request

from app.src.core.schemas import (
    CreateTaskInput,
    SubmitTaskResponseInput,
)
from app.src.core.services import (
    create_task,
    get_student_tasks,
    submit_task_response,
    get_task_responses,
    get_user_by_id,
)
from app.src.domain.task import Task, TaskResponse
from app.src.domain.student import Student
from app.src.integrations.db import db

bp = Blueprint("tasks_v1", __name__, url_prefix="/api/v1/tasks")


@bp.post("/create")
def create_task_route() -> tuple:
    """
    Создать новое задание для группы.
    
    Только администратор или преподаватель может создать задание.
    
    JSON payload:
    {
        "group_id": 1,
        "title": "Лабораторная работа №1",
        "description": "Описание задания",
        "file_url": "https://example.com/task.pdf",
        "due_date": "2026-06-15T23:59:59Z"
    }
    """
    data = request.get_json(silent=True) or {}
    
    # Проверить авторизацию (временно используем user_id из headers)
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return jsonify({"error": "Authorization required"}), 401
    
    try:
        user = get_user_by_id(int(user_id))
        if user.role.role not in {"admin", "professor"}:
            return jsonify({"error": "Only admin or professor can create tasks"}), 403
        
        payload = CreateTaskInput(
            group_id=data.get("group_id"),
            title=data.get("title"),
            description=data.get("description"),
            file_url=data.get("file_url"),
            due_date=data.get("due_date"),
        )
        
        result = create_task(payload, user.id)
        return jsonify(result), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error creating task: {error}")
        return jsonify({"error": "Internal server error"}), 500


@bp.get("/list")
def get_tasks_route() -> tuple:
    """
    Получить список заданий для студента.
    
    Параметры запроса:
    - telegram_id (опционально): Telegram ID студента
    - vk_id (опционально): VK ID студента
    
    Если оба указаны, используется telegram_id.
    """
    telegram_id = request.args.get("telegram_id", type=int)
    vk_id = request.args.get("vk_id", type=int)
    
    try:
        if telegram_id is None and vk_id is None:
            return jsonify({"error": "telegram_id or vk_id must be provided"}), 400
        
        result = get_student_tasks(telegram_id, vk_id)
        return jsonify(result), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error fetching tasks: {error}")
        return jsonify({"error": "Internal server error"}), 500


@bp.post("/<int:task_id>/submit")
def submit_response_route(task_id: int) -> tuple:
    """
    Отправить ответ на задание.
    
    JSON payload:
    {
        "telegram_id": 123456,
        "vk_id": 789012,
        "response_text": "Ответ на задание",
        "file_url": "https://example.com/response.pdf"
    }
    """
    data = request.get_json(silent=True) or {}
    
    try:
        payload = SubmitTaskResponseInput(
            task_id=task_id,
            telegram_id=data.get("telegram_id"),
            vk_id=data.get("vk_id"),
            response_text=data.get("response_text"),
            file_url=data.get("file_url"),
        )
        
        result = submit_task_response(payload)
        return jsonify(result), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error submitting task response: {error}")
        return jsonify({"error": "Internal server error"}), 500


@bp.get("/<int:task_id>/responses")
def get_responses_route(task_id: int) -> tuple:
    """
    Получить все ответы на задание.
    
    Только преподаватель может просмотреть ответы.
    """
    # Проверить авторизацию (временно используем user_id из headers)
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return jsonify({"error": "Authorization required"}), 401
    
    try:
        user = get_user_by_id(int(user_id))
        if user.role.role not in {"admin", "professor"}:
            return jsonify({"error": "Only admin or professor can view responses"}), 403
        
        result = get_task_responses(task_id)
        return jsonify(result), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        current_app.logger.error(f"Error fetching task responses: {error}")
        return jsonify({"error": "Internal server error"}), 500
