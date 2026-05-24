import re
from datetime import date, datetime


EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)

BOT_EMAIL_RE = re.compile(
    r"^[a-z]+\.[a-z]{2}@edu\.spbstu\.ru$"
)


def validate_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def validate_email(value: str) -> str:
    email = validate_non_empty(value, "email").lower()
    if not EMAIL_RE.match(email):
        raise ValueError("email has invalid format.")
    return email


def validate_bot_email(value: str) -> str:
    email = validate_non_empty(value, "email").lower()
    if not BOT_EMAIL_RE.match(email):
        raise ValueError("email has invalid format.")
    return email


def validate_role(value: str) -> str:
    role = validate_non_empty(value, "role").lower()
    allowed = {"admin", "practitioner", "listener"}
    if role not in allowed:
        raise ValueError(f"role must be one of: {', '.join(sorted(allowed))}.")
    return role


def validate_password(value: str) -> str:
    password = validate_non_empty(value, "password")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters.")
    return password


def validate_group_number(value: str) -> str:
    number = validate_non_empty(value, "group_number")
    if len(number) > 16:
        raise ValueError("group_number length must be <= 16.")
    return number


def validate_group_name(value: str) -> str:
    name = validate_non_empty(value, "group_name")
    if len(name) > 20:
        raise ValueError("group_name length must be <= 20.")
    return name


def validate_semester(value: int) -> int:
    if not isinstance(value, int) or value not in {1, 2}:
        raise ValueError("semester must be 1 or 2.")
    return value


def parse_calendar_date(value: str) -> date:
    """Parse YYYY-MM-DD or DD.MM.YYYY as a calendar date (no timezone shift)."""
    raw = validate_non_empty(value, "date").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        year, month, day = (int(part) for part in raw.split("-"))
        return date(year, month, day)
    match = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", raw)
    if match:
        day, month, year = (int(match.group(i)) for i in (1, 2, 3))
        return date(year, month, day)
    raise ValueError("date must be YYYY-MM-DD or DD.MM.YYYY.")


def calendar_date_to_lecture_datetime(session_date: date) -> datetime:
    """Store lecture attendance at noon UTC to avoid day-boundary issues."""
    return datetime(session_date.year, session_date.month, session_date.day, 12, 0, 0)


def normalize_component_code(value: str) -> str:
    code = validate_non_empty(value, "component").upper().replace(" ", "")
    code = code.replace("ЛР", "LR").replace("Л", "L").replace("Р", "R")
    if not re.match(r"^LR\d+$", code):
        raise ValueError("component must look like LR1, LR2, ...")
    return code


def validate_score(value: float | int | None) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise ValueError("score must be a number.")
    if value < 0:
        raise ValueError("score must be >= 0.")
    return float(value)


def determine_user_role_from_email(email: str) -> tuple[str, str]:
    """
    Определяет роль пользователя по email.
    Возвращает (user_role для ответа, db_role для БД).
    """
    email_lower = email.lower()
    if "admin" in email_lower:
        return "admin", "admin"
    elif "teacher" in email_lower or "prof" in email_lower:
        return "admin", "admin"
    elif "listener" in email_lower or "audit" in email_lower or "lecture" in email_lower:
        return "listener", "listener"
    elif "praktik" in email_lower or "practice" in email_lower:
        return "practitioner", "practitioner"
    else:
        return "practitioner", "practitioner"

