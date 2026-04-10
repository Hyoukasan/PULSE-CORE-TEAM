from dataclasses import dataclass
from typing import Optional

from .validators import (
    validate_email,
    validate_group_name,
    validate_group_number,
    validate_non_empty,
    validate_password,
    validate_role,
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
    role: str
    email: Optional[str] = None
    fullname: Optional[str] = None
    group: Optional[str] = None
    platform: Optional[str] = None
    telegram_id: Optional[int] = None

    def __post_init__(self) -> None:
        if self.user_id is not None and self.user_id <= 0:
            raise ValueError("user_id must be > 0.")
        if self.telegram_id is not None and self.telegram_id <= 0:
            raise ValueError("telegram_id must be > 0.")
        if self.email is not None:
            self.email = validate_email(self.email)
        self.role = validate_non_empty(self.role, "role")
        if self.fullname is not None:
            self.fullname = validate_non_empty(self.fullname, "fullname")
        if self.group is not None:
            self.group = validate_non_empty(self.group, "group")


@dataclass
class SendMessageInput:
    sender: MessageSenderInput
    message: MessagePayload
    to_user_id: Optional[int] = None
    to_telegram_id: Optional[int] = None

    def __post_init__(self) -> None:
        if self.to_user_id is not None and self.to_user_id <= 0:
            raise ValueError("to_user_id must be > 0.")
        if self.to_telegram_id is not None and self.to_telegram_id <= 0:
            raise ValueError("to_telegram_id must be > 0.")


@dataclass
class SheetGroupRow:
    number: str
    name: str

    def __post_init__(self) -> None:
        self.number = validate_group_number(self.number)
        self.name = validate_group_name(self.name)


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
    telegram_id: int
    mail: str
    password: str
    fullname: Optional[str] = None

    def __post_init__(self) -> None:
        if self.action not in {"registration", "enter"}:
            raise ValueError("action must be 'registration' or 'enter'.")
        if self.telegram_id <= 0:
            raise ValueError("telegram_id must be > 0.")
        self.mail = validate_email(self.mail)
        self.password = validate_password(self.password)
        if self.fullname is not None:
            self.fullname = validate_non_empty(self.fullname, "fullname")

