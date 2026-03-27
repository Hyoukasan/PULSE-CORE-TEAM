import re


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


def validate_role(value: str) -> str:
    role = validate_non_empty(value, "role").lower()
    allowed = {"admin", "student", "professor"}
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
    if len(name) > 8:
        raise ValueError("group_name length must be <= 8.")
    return name

