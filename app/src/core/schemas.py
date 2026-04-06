from dataclasses import dataclass

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

    def __post_init__(self) -> None:
        self.username = validate_non_empty(self.username, "username")
        self.email = validate_email(self.email)
        self.password = validate_password(self.password)
        self.role = validate_role(self.role)


@dataclass
class AssignUserToGroupInput:
    user_id: int
    group_number: str

    def __post_init__(self) -> None:
        if self.user_id <= 0:
            raise ValueError("user_id must be > 0.")
        self.group_number = validate_group_number(self.group_number)


@dataclass
class SheetGroupRow:
    number: str
    name: str

    def __post_init__(self) -> None:
        self.number = validate_group_number(self.number)
        self.name = validate_group_name(self.name)


@dataclass
class BotAuthInput:
    action: str
    telegram_id: int
    mail: str
    password: str

    def __post_init__(self) -> None:
        if self.action not in {"registration", "enter"}:
            raise ValueError("action must be 'registration' or 'enter'.")
        if self.telegram_id <= 0:
            raise ValueError("telegram_id must be > 0.")
        self.mail = validate_email(self.mail)
        self.password = validate_password(self.password)

