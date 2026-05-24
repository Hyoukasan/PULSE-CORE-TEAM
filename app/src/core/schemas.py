from dataclasses import dataclass
from typing import Optional

from .validators import (
    normalize_component_code,
    parse_calendar_date,
    validate_bot_email,
    validate_email,
    validate_group_name,
    validate_group_number,
    validate_non_empty,
    validate_password,
    validate_role,
    validate_score,
    validate_semester,
)


@dataclass
class RegisterUserInput:
    username: str
    email: str
    password: str
    role: str
    fullname: Optional[str] = None

    def __post_init__(self) -> None:
        self.username = validate_non_empty(self.username, "username")
        self.email = validate_email(self.email)
        self.password = validate_password(self.password)
        self.role = validate_role(self.role)
        if self.fullname is not None:
            self.fullname = validate_non_empty(self.fullname, "fullname")


@dataclass
class AuthLoginInput:
    email: str
    password: str
    platform: Optional[str] = None
    vk_id: Optional[int] = None

    def __post_init__(self) -> None:
        self.email = validate_email(self.email)
        self.password = validate_password(self.password)
        if self.platform is not None:
            self.platform = validate_non_empty(self.platform, "platform")
        if self.vk_id is not None and self.vk_id <= 0:
            raise ValueError("vk_id must be > 0.")


@dataclass
class AssignUserToGroupInput:
    user_id: int
    group_number: str

    def __post_init__(self) -> None:
        if self.user_id <= 0:
            raise ValueError("user_id must be > 0.")
        self.group_number = validate_group_number(self.group_number)


@dataclass
class MessagePayload:
    type: Optional[str]
    text: str
    timestamp: Optional[str] = None

    def __post_init__(self) -> None:
        self.text = validate_non_empty(self.text, "text")
        if self.type is None:
            self.type = "text"


@dataclass
class MessageSenderInput:
    user_id: Optional[int]
    role: Optional[str] = None
    email: Optional[str] = None
    fullname: Optional[str] = None
    group: Optional[str] = None
    platform: Optional[str] = None
    telegram_id: Optional[int] = None
    vk_id: Optional[int] = None

    def __post_init__(self) -> None:
        if self.user_id is not None and self.user_id <= 0:
            raise ValueError("user_id must be > 0.")
        if self.telegram_id is not None and self.telegram_id <= 0:
            raise ValueError("telegram_id must be > 0.")
        if self.vk_id is not None and self.vk_id <= 0:
            raise ValueError("vk_id must be > 0.")
        if self.email is not None:
            self.email = validate_email(self.email)
        if self.role is not None:
            self.role = validate_role(self.role)
        if self.fullname is not None:
            self.fullname = validate_non_empty(self.fullname, "fullname")
        if self.group is not None:
            self.group = validate_non_empty(self.group, "group")
        if self.role in {"practitioner", "listener"}:
            has_telegram = self.telegram_id is not None
            has_vk = self.vk_id is not None
            if not (has_telegram or has_vk):
                raise ValueError("For practitioner/listener sender either telegram_id or vk_id must be provided.")
            if has_telegram and has_vk:
                raise ValueError("For practitioner/listener sender provide either telegram_id or vk_id, not both.")


@dataclass
class SendMessageInput:
    sender: MessageSenderInput
    message: MessagePayload
    to_user_id: Optional[int] = None
    to_telegram_id: Optional[int] = None
    to_vk_id: Optional[int] = None
    external_message_id: Optional[str] = None
    to_group_number: Optional[str] = None

    def __post_init__(self) -> None:
        if self.to_user_id is not None and self.to_user_id <= 0:
            raise ValueError("to_user_id must be > 0.")
        if self.to_telegram_id is not None and self.to_telegram_id <= 0:
            raise ValueError("to_telegram_id must be > 0.")
        if self.to_vk_id is not None and self.to_vk_id <= 0:
            raise ValueError("to_vk_id must be > 0.")


@dataclass
class SheetGroupRow:
    number: str
    name: str

    def __post_init__(self) -> None:
        self.number = validate_group_number(self.number)
        self.name = validate_group_name(self.name)


@dataclass
class SheetUserRow:
    email: str
    fullname: Optional[str] = None
    group_number: Optional[str] = None
    pass_id: Optional[str] = None
    missed_passes: Optional[int] = None

    def __post_init__(self) -> None:
        self.email = validate_email(self.email)
        if self.fullname is not None:
            self.fullname = validate_non_empty(self.fullname, "fullname")
        if self.group_number is not None:
            self.group_number = validate_group_number(self.group_number)
        if self.pass_id is not None:
            self.pass_id = validate_non_empty(self.pass_id, "pass_id")
        if self.missed_passes is not None:
            if not isinstance(self.missed_passes, int) or self.missed_passes < 0:
                raise ValueError("missed_passes must be a non-negative integer.")


@dataclass
class SheetAttendanceRow:
    email: str
    timestamp: str
    attended: bool = True

    def __post_init__(self) -> None:
        self.email = validate_email(self.email)
        self.timestamp = validate_non_empty(self.timestamp, "timestamp")
        try:
            from datetime import datetime as dt
            parsed = dt.fromisoformat(self.timestamp.replace('Z', '+00:00'))
            self.timestamp = parsed
        except ValueError:
            raise ValueError("timestamp must be a valid ISO 8601 datetime string.")
        if not isinstance(self.attended, bool):
            raise ValueError("attended must be a boolean.")


@dataclass
class SheetLectureAttendanceRow:
    email: str
    semester: int
    date: str
    attended: bool = True

    def __post_init__(self) -> None:
        self.email = validate_email(self.email)
        self.semester = validate_semester(self.semester)
        self.date = parse_calendar_date(self.date)
        if not isinstance(self.attended, bool):
            raise ValueError("attended must be a boolean.")


@dataclass
class SheetLabScoreRow:
    email: str
    semester: int
    subject: str
    component: str
    score: Optional[float] = None

    def __post_init__(self) -> None:
        self.email = validate_email(self.email)
        self.semester = validate_semester(self.semester)
        self.subject = validate_non_empty(self.subject, "subject")
        self.component = normalize_component_code(self.component)
        self.score = validate_score(self.score)


@dataclass
class AttendanceExcuseInput:
    email: str
    reason: str
    file_url: Optional[str] = None
    timestamp: Optional[str] = None

    def __post_init__(self) -> None:
        self.email = validate_email(self.email)
        self.reason = validate_non_empty(self.reason, "reason")
        if self.file_url is not None:
            self.file_url = validate_non_empty(self.file_url, "file_url")
        if self.timestamp is not None:
            self.timestamp = validate_non_empty(self.timestamp, "timestamp")


@dataclass
class AttendancePassInput:
    pass_id: str

    def __post_init__(self) -> None:
        self.pass_id = validate_non_empty(self.pass_id, "pass_id")


@dataclass
class BotAuthInput:
    action: str
    mail: str
    password: str
    telegram_id: Optional[int] = None
    vk_id: Optional[int] = None
    fullname: Optional[str] = None

    def __post_init__(self) -> None:
        if self.action not in {"registration", "enter"}:
            raise ValueError("action must be 'registration' or 'enter'.")
        if self.telegram_id is None and self.vk_id is None:
            raise ValueError("telegram_id or vk_id must be provided.")
        if self.telegram_id is not None and self.telegram_id <= 0:
            raise ValueError("telegram_id must be > 0.")
        if self.vk_id is not None and self.vk_id <= 0:
            raise ValueError("vk_id must be > 0.")
        self.mail = validate_bot_email(self.mail)
        self.password = validate_password(self.password)
        if self.fullname is not None:
            self.fullname = validate_non_empty(self.fullname, "fullname")


@dataclass
class AddToQueueInput:
    """Добавить студента в очередь на занятие."""
    student_id: int
    professor_id: int
    lesson_date: Optional[str] = None
    labs_count: int = 1

    def __post_init__(self) -> None:
        if self.student_id <= 0:
            raise ValueError("student_id must be > 0.")
        if self.professor_id <= 0:
            raise ValueError("professor_id must be > 0.")
        if self.labs_count <= 0:
            raise ValueError("labs_count must be > 0.")
        if self.lesson_date is not None:
            self.lesson_date = validate_non_empty(self.lesson_date, "lesson_date")
            try:
                from datetime import datetime as dt
                parsed = dt.fromisoformat(self.lesson_date.replace('Z', '+00:00'))
                self.lesson_date = parsed
            except ValueError:
                raise ValueError("lesson_date must be a valid ISO 8601 datetime string.")


@dataclass
class AddToQueueBotInput:
    telegram_id: Optional[int] = None
    vk_id: Optional[int] = None
    labs_count: int = 1
    lesson_date: Optional[str] = None

    def __post_init__(self) -> None:
        if self.telegram_id is None and self.vk_id is None:
            raise ValueError("telegram_id or vk_id must be provided.")
        if self.telegram_id is not None and self.telegram_id <= 0:
            raise ValueError("telegram_id must be > 0.")
        if self.vk_id is not None and self.vk_id <= 0:
            raise ValueError("vk_id must be > 0.")
        if self.labs_count <= 0:
            raise ValueError("labs_count must be > 0.")
        if self.lesson_date is not None:
            self.lesson_date = validate_non_empty(self.lesson_date, "lesson_date")
            try:
                from datetime import datetime as dt
                parsed = dt.fromisoformat(self.lesson_date.replace('Z', '+00:00'))
                self.lesson_date = parsed
            except ValueError:
                raise ValueError("lesson_date must be a valid ISO 8601 datetime string.")


@dataclass
class RemoveFromQueueInput:
    """Удалить студента из очереди."""
    student_id: int
    professor_id: int
    lesson_date: str  # ISO 8601 datetime string

    def __post_init__(self) -> None:
        if self.student_id <= 0:
            raise ValueError("student_id must be > 0.")
        if self.professor_id <= 0:
            raise ValueError("professor_id must be > 0.")
        self.lesson_date = validate_non_empty(self.lesson_date, "lesson_date")
        try:
            from datetime import datetime as dt
            parsed = dt.fromisoformat(self.lesson_date.replace('Z', '+00:00'))
            self.lesson_date = parsed
        except ValueError:
            raise ValueError("lesson_date must be a valid ISO 8601 datetime string.")


@dataclass
class GetQueuePositionInput:
    """Получить позицию студента в очереди."""
    student_id: int
    professor_id: int
    lesson_date: str  # ISO 8601 datetime string

    def __post_init__(self) -> None:
        if self.student_id <= 0:
            raise ValueError("student_id must be > 0.")
        if self.professor_id <= 0:
            raise ValueError("professor_id must be > 0.")
        self.lesson_date = validate_non_empty(self.lesson_date, "lesson_date")
        try:
            from datetime import datetime as dt
            parsed = dt.fromisoformat(self.lesson_date.replace('Z', '+00:00'))
            self.lesson_date = parsed
        except ValueError:
            raise ValueError("lesson_date must be a valid ISO 8601 datetime string.")


@dataclass
class GetQueueForLessonInput:
    """Получить всю очередь для занятия."""
    professor_id: int
    lesson_date: str  # ISO 8601 datetime string

    def __post_init__(self) -> None:
        if self.professor_id <= 0:
            raise ValueError("professor_id must be > 0.")
        self.lesson_date = validate_non_empty(self.lesson_date, "lesson_date")
        try:
            from datetime import datetime as dt
            parsed = dt.fromisoformat(self.lesson_date.replace('Z', '+00:00'))
            # Normalize to naive date-only datetime (midnight) to match stored queue entries
            self.lesson_date = dt(parsed.year, parsed.month, parsed.day)
        except ValueError:
            raise ValueError("lesson_date must be a valid ISO 8601 datetime string.")


@dataclass
class CreateTaskInput:
    """Создать новое задание."""
    group_id: int
    title: str
    description: Optional[str] = None
    file_url: Optional[str] = None
    due_date: Optional[str] = None

    def __post_init__(self) -> None:
        if self.group_id <= 0:
            raise ValueError("group_id must be > 0.")
        self.title = validate_non_empty(self.title, "title")
        if self.description is not None:
            self.description = validate_non_empty(self.description, "description")
        if self.file_url is not None:
            self.file_url = validate_non_empty(self.file_url, "file_url")
        if self.due_date is not None:
            self.due_date = validate_non_empty(self.due_date, "due_date")
            try:
                from datetime import datetime as dt
                parsed = dt.fromisoformat(self.due_date.replace('Z', '+00:00'))
                self.due_date = parsed
            except ValueError:
                raise ValueError("due_date must be a valid ISO 8601 datetime string.")


@dataclass
class SubmitTaskResponseInput:
    """Отправить ответ на задание."""
    task_id: int
    telegram_id: Optional[int] = None
    vk_id: Optional[int] = None
    response_text: Optional[str] = None
    file_url: Optional[str] = None

    def __post_init__(self) -> None:
        if self.task_id <= 0:
            raise ValueError("task_id must be > 0.")
        if self.telegram_id is None and self.vk_id is None:
            raise ValueError("telegram_id or vk_id must be provided.")
        if self.telegram_id is not None and self.telegram_id <= 0:
            raise ValueError("telegram_id must be > 0.")
        if self.vk_id is not None and self.vk_id <= 0:
            raise ValueError("vk_id must be > 0.")
        if self.response_text is None and self.file_url is None:
            raise ValueError("response_text or file_url must be provided.")
        if self.response_text is not None:
            self.response_text = validate_non_empty(self.response_text, "response_text")
        if self.file_url is not None:
            self.file_url = validate_non_empty(self.file_url, "file_url")
