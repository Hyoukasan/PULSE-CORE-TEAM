from datetime import datetime
from typing import Iterable

import sqlalchemy.orm as so

from app.src.integrations.db import db
from app.src.domain.attendance_excuse import AttendanceExcuse
from app.src.domain.attendance_record import AttendanceRecord
from app.src.domain.approach_queue import ApproachQueue
from app.src.domain.group import Group
from app.src.domain.message import Message
from app.src.domain.professor import Professor
from app.src.domain.role import Role
from app.src.domain.student import Student
from app.src.domain.user import User
from app.src.domain.user_pass_key import UserPassKey
from app.src.domain.student_lab_score import StudentLabScore
from app.src.domain.task import Task, TaskResponse

from .schemas import (
    AddToQueueBotInput,
    AddToQueueInput,
    AssignUserToGroupInput,
    AttendanceExcuseInput,
    AttendancePassInput,
    AuthLoginInput,
    BotAuthInput,
    GetQueueForLessonInput,
    GetQueuePositionInput,
    MessagePayload,
    MessageSenderInput,
    RegisterUserInput,
    RemoveFromQueueInput,
    SendMessageInput,
    SheetGroupRow,
    SheetUserRow,
    SheetAttendanceRow,
    CreateTaskInput,
    SubmitTaskResponseInput,
)
from .validators import determine_user_role_from_email


def _generate_unique_username(email: str) -> str:
    base_username = email.split("@")[0]
    username = base_username
    suffix = 1
    while db.session.execute(db.select(User).where(User.username == username)).scalar_one_or_none() is not None:
        username = f"{base_username}_{suffix}"
        suffix += 1
    return username


def _normalize_user_role(role_name: str) -> str:
    if role_name == "professor":
        return "teacher"
    if role_name in {"student", "student_lecture", "practitioner", "listener", "admin"}:
        return role_name
    return role_name


def ensure_user_not_banned(user: User) -> None:
    """Raise ValueError if the user is currently banned.

    A NULL/None `ban_expires_at` means the user is not banned.
    """
    if user is None:
        return
    if user.ban_expires_at is not None and user.ban_expires_at > datetime.utcnow():
        raise ValueError(f"User is banned until {user.ban_expires_at.isoformat()}")


def authenticate_user(payload: AuthLoginInput) -> User:
    user = db.session.execute(
        db.select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    
    # Если пользователя нет и указана платформа (социальная аутентификация)
    if user is None and payload.platform:
        existing_by_vk = None
        if payload.vk_id is not None:
            existing_by_vk = get_user_by_vk_id(payload.vk_id)

        if existing_by_vk is not None:
            if existing_by_vk.email != payload.email:
                raise ValueError("Email does not match existing bot account.")
            user = existing_by_vk

        if user is None:
            # Определить роль по email
            user_role, db_role = determine_user_role_from_email(payload.email)
            
            # Найти роль в БД
            role = db.session.execute(
                db.select(Role).where(Role.role == db_role)
            ).scalar_one_or_none()
            if role is None:
                raise ValueError(f"Role '{db_role}' not found. Seed roles first.")
            
            # Создать нового пользователя
            username = _generate_unique_username(payload.email)
            user = User(
                username=username,
                email=payload.email,
                role_id=role.id,
            )
            # Для социальной аутентификации используем пароль из пейлода
            user.set_password(payload.password)
            if role.role in {"practitioner", "listener"}:
                ensure_student_profile(user)
        else:
            # Уже существует пользователь с таким бот-идентификатором, проверяем пароль
            if not user.verify_password(payload.password):
                raise ValueError("Invalid email or password.")

        # Если есть vk_id, сохранить его (или подтвердить соответствие)
        if payload.vk_id is not None and user.vk_id != payload.vk_id:
            if user.vk_id is not None:
                raise ValueError("VK ID does not match user account.")
            user.vk_id = payload.vk_id

        if user not in db.session:
            db.session.add(user)
        try:
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            raise ValueError("Unable to create or update user during social login.") from error
        ensure_user_not_banned(user)
        return user
    
    # Обычная аутентификация по паролю
    if user is None or not user.verify_password(payload.password):
        raise ValueError("Invalid email or password.")
    
    # Обновить vk_id если приходит при каждом логине
    if payload.vk_id is not None and user.vk_id != payload.vk_id:
        user.vk_id = payload.vk_id
        db.session.commit()
    ensure_user_not_banned(user)
    return user


def get_user_by_id(user_id: int) -> User | None:
    return db.session.get(User, user_id)


def get_user_by_email(email: str) -> User | None:
    return db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()


def set_user_ban(user: User, ban: bool, ban_expires_at: str | None = None) -> None:
    if not ban:
        user.ban_expires_at = None
        return

    if ban_expires_at is None:
        user.ban_expires_at = datetime(9999, 12, 31, 23, 59, 59)
        return

    ban_value = ban_expires_at
    if isinstance(ban_value, str) and ban_value.endswith("Z"):
        ban_value = ban_value.replace("Z", "+00:00")
    try:
        user.ban_expires_at = datetime.fromisoformat(ban_value)
    except Exception as error:
        raise ValueError("ban_expires_at must be ISO 8601 string or null") from error


def is_user_currently_banned(user: User) -> bool:
    if user.ban_expires_at is None:
        return False
    return user.ban_expires_at > datetime.utcnow()


def banned_status_response() -> dict:
    return {"status": "banned"}


def _resolve_user_ref(
    data: dict,
    *,
    user_id_keys: tuple[str, ...] = ("user_id",),
    telegram_id_keys: tuple[str, ...] = ("telegram_id",),
    vk_id_keys: tuple[str, ...] = ("vk_id",),
    email_keys: tuple[str, ...] = ("email",),
    fallback_system_id_for_vk: bool = False,
) -> User | None:
    # Сначала проверяем system ID (приоритет выше)
    for key in user_id_keys:
        if data.get(key) is not None:
            user = get_user_by_id(int(data[key]))
            if user is not None:
                return user
    # Потом telegram_id
    for key in telegram_id_keys:
        if data.get(key) is not None:
            user = get_user_by_telegram_id(int(data[key]))
            if user is not None:
                return user
    # Потом vk_id
    vk_value = None
    for key in vk_id_keys:
        if data.get(key) is not None:
            vk_value = int(data[key])
            user = get_user_by_vk_id(vk_value)
            if user is not None:
                return user
    # Если нет пользователя по vk_id, можно попробовать system id с тем же значением
    if fallback_system_id_for_vk and vk_value is not None:
        user = get_user_by_id(vk_value)
        if user is not None:
            return user
    # И в конце email
    for key in email_keys:
        if data.get(key) is not None:
            user = get_user_by_email(str(data[key]))
            if user is not None:
                return user
    return None


def resolve_admin_from_request(data: dict) -> User:
    from_block = data.get("from") or {}
    admin = _resolve_user_ref(
        from_block,
        user_id_keys=("id", "user_id", "admin_id"),
        telegram_id_keys=("telegram_id", "admin_telegram_id"),
        vk_id_keys=("vk_id", "admin_vk_id"),
        email_keys=("email", "admin_email"),
        fallback_system_id_for_vk=True,
    )
    if admin is None:
        admin = _resolve_user_ref(
            data,
            user_id_keys=("admin_id", "user_id", "id"),
            telegram_id_keys=("admin_telegram_id", "telegram_id"),
            vk_id_keys=("admin_vk_id", "vk_id"),
            email_keys=("admin_email", "email"),
            fallback_system_id_for_vk=True,
        )
    if admin is None:
        raise ValueError(
            "Admin identifier required: from.id, from.user_id, from.telegram_id, from.vk_id "
            "or admin_id / admin_telegram_id / admin_vk_id."
        )
    if admin.role.role != "admin":
        raise ValueError("Only admin can manage bans.")
    return admin


def resolve_ban_target_from_request(data: dict) -> User:
    target_block = data.get("target") or {}
    target = _resolve_user_ref(
        target_block,
        user_id_keys=("id", "user_id", "target_user_id"),
        telegram_id_keys=("telegram_id", "target_telegram_id"),
        vk_id_keys=("vk_id", "target_vk_id"),
        email_keys=("email", "target_email"),
        fallback_system_id_for_vk=True,
    )
    if target is None:
        target = _resolve_user_ref(
            data,
            user_id_keys=("target_user_id", "user_id", "id"),
            telegram_id_keys=("target_telegram_id", "telegram_id"),
            vk_id_keys=("target_vk_id", "vk_id"),
            email_keys=("target_email", "email"),
            fallback_system_id_for_vk=True,
        )
    if target is None:
        raise ValueError(
            "Target user required: target.id, target.user_id, target.telegram_id, target.vk_id, target.email "
            "or target_user_id / target_telegram_id / target_vk_id."
        )
    return target


def ban_user_as_admin(admin: User, target: User, ban_expires_at: str | None = None, permanent: bool = False) -> User:
    if admin.role.role != "admin":
        raise ValueError("Only admin can ban users.")
    if target.role.role == "admin":
        raise ValueError("Cannot ban admin users.")
    if permanent or ban_expires_at is None:
        set_user_ban(target, True, None)
    else:
        set_user_ban(target, True, ban_expires_at)
    db.session.commit()
    return target


def unban_user_as_admin(admin: User, target: User) -> User:
    if admin.role.role != "admin":
        raise ValueError("Only admin can unban users.")
    set_user_ban(target, False)
    db.session.commit()
    return target


def list_banned_users() -> list[dict]:
    now = datetime.utcnow()
    users = db.session.execute(
        db.select(User).where(User.ban_expires_at.isnot(None), User.ban_expires_at > now)
    ).scalars().all()

    result = []
    for user in users:
        row = serialize_user_info(user)
        row["ban_expires_at"] = user.ban_expires_at.isoformat() if user.ban_expires_at else None
        row["is_banned"] = True
        result.append(row)
    return result


def get_user_by_telegram_id(telegram_id: int) -> User | None:
    return db.session.execute(
        db.select(User).where(User.telegram_id == telegram_id)
    ).scalar_one_or_none()


def get_user_by_vk_id(vk_id: int) -> User | None:
    return db.session.execute(
        db.select(User).where(User.vk_id == vk_id)
    ).scalar_one_or_none()


def ensure_student_profile(user: User, group_id: int | None = None) -> Student:
    student = db.session.get(Student, user.id)
    if student is None:
        student = Student(user=user, group_id=group_id)
        db.session.add(student)
    elif group_id is not None and student.group_id != group_id:
        student.group_id = group_id
    return student


def get_user_by_bot_ids(telegram_id: int | None, vk_id: int | None) -> User | None:
    if telegram_id is not None:
        user = get_user_by_telegram_id(telegram_id)
        if user is not None:
            return user
    if vk_id is not None:
        return get_user_by_vk_id(vk_id)
    return None


def get_user_by_system_or_bot_id(user_id: int) -> User | None:
    user = db.session.get(User, user_id)
    if user is not None:
        return user
    user = get_user_by_telegram_id(user_id)
    if user is not None:
        return user
    return get_user_by_vk_id(user_id)


def get_admin_user() -> User | None:
    """Return a single admin user (lowest id) when several exist in DB."""
    role = db.session.execute(
        db.select(Role).where(Role.role == "admin")
    ).scalar_one_or_none()
    if role is None:
        return None
    return db.session.execute(
        db.select(User)
        .where(User.role_id == role.id)
        .order_by(User.id)
        .limit(1)
    ).scalar_one_or_none()


def _parse_lesson_date(lesson_date: str | datetime | None) -> datetime:
    if lesson_date is None:
        today = datetime.utcnow().date()
        return datetime(today.year, today.month, today.day)

    if isinstance(lesson_date, datetime):
        return datetime(lesson_date.year, lesson_date.month, lesson_date.day)

    if lesson_date.endswith("Z"):
        lesson_date = lesson_date.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(lesson_date)
    except ValueError as error:
        raise ValueError("lesson_date must be a valid ISO 8601 datetime string.") from error

    return datetime(parsed.year, parsed.month, parsed.day)


def _resolve_student_by_bot_ids(telegram_id: int | None, vk_id: int | None) -> Student:
    if telegram_id is not None:
        user = get_user_by_telegram_id(telegram_id)
    elif vk_id is not None:
        user = get_user_by_vk_id(vk_id)
    else:
        raise ValueError("telegram_id or vk_id must be provided.")

    if user is None:
        raise ValueError("Student account not found for provided bot id.")

    if user.role.role != "practitioner":
        raise ValueError("Only practitioners can join the approach queue.")

    student = db.session.get(Student, user.id)
    if student is None:
        student = Student(id=user.id, group_id=None)
        db.session.add(student)
        db.session.commit()
    if student.group_id is None:
        raise ValueError("Student is not assigned to a group.")

    return student


def _resolve_professor_for_student(student: Student) -> Professor:
    professor = db.session.execute(
        db.select(Professor)
        .where(Professor.group_id == student.group_id)
        .order_by(Professor.id)
        .limit(1)
    ).scalar_one_or_none()
    if professor is not None:
        return professor

    admin = get_admin_user()
    if admin is None:
        raise ValueError("No professor found for student's group, and no admin user is available.")

    professor = db.session.get(Professor, admin.id)
    if professor is None:
        professor = Professor(id=admin.id, group_id=student.group_id)
        db.session.add(professor)
        db.session.commit()
    elif professor.group_id != student.group_id:
        professor.group_id = student.group_id
        db.session.commit()

    return professor


def get_user_by_pass_key(pass_key: str) -> User | None:
    record = db.session.execute(
        db.select(UserPassKey).where(UserPassKey.pass_key == pass_key)
    ).scalar_one_or_none()
    return record.user if record is not None else None


def get_message_recipient(
    sender: User,
    to_user_id: int | None = None,
    to_telegram_id: int | None = None,
    to_vk_id: int | None = None,
) -> User:
    # Users (practitioner/listener/student) send messages only to admin.
    if sender.role.role in {"practitioner", "listener", "student", "student_lecture"}:
        admin = get_admin_user()
        if admin is None:
            raise ValueError("Admin user not found.")
        return admin

    if sender.role.role == "admin":
        if not any((to_user_id, to_telegram_id, to_vk_id)):
            raise ValueError("Admin must specify recipient user_id, telegram_id, or vk_id.")

        recipient = None
        if to_user_id is not None:
            recipient = get_user_by_id(to_user_id)
        elif to_telegram_id is not None:
            recipient = get_user_by_telegram_id(to_telegram_id)
        elif to_vk_id is not None:
            recipient = get_user_by_vk_id(to_vk_id)

        if recipient is None:
            raise ValueError("Recipient not found.")
        if recipient.role.role not in {"practitioner", "listener", "student", "student_lecture"}:
            raise ValueError("Recipient must be a practitioner or listener.")
        return recipient

    raise ValueError("Only practitioner, listener, and admin can send messages.")


def _resolve_message_sender(sender_input: MessageSenderInput) -> User | None:
    sender = None
    if sender_input.user_id is not None:
        sender = get_user_by_system_or_bot_id(sender_input.user_id)
    if sender is None and sender_input.telegram_id is not None:
        sender = get_user_by_telegram_id(sender_input.telegram_id)
    if sender is None and sender_input.vk_id is not None:
        sender = get_user_by_vk_id(sender_input.vk_id)
    return sender


def send_message(payload: SendMessageInput) -> Message:
    sender = _resolve_message_sender(payload.sender)
    if sender is None:
        raise ValueError("Sender not found.")

    ensure_user_not_banned(sender)

    recipient = get_message_recipient(
        sender,
        to_user_id=payload.to_user_id,
        to_telegram_id=payload.to_telegram_id,
        to_vk_id=payload.to_vk_id,
    )
    # If an external message ID is provided, avoid storing duplicates.
    external_id = getattr(payload, "external_message_id", None)
    if external_id:
        existing = db.session.execute(db.select(Message).where(Message.external_id == external_id)).scalar_one_or_none()
        if existing is not None:
            return existing

    message = Message(
        sender_id=sender.id,
        recipient_id=recipient.id,
        external_id=external_id,
        message_type=payload.message.type or "text",
        text=payload.message.text,
    )
    db.session.add(message)
    db.session.commit()
    return message


def send_broadcast(payload: SendMessageInput) -> dict:
    """Send message from admin to all students in a group (broadcast).

    Returns dict with number of created messages.
    """
    if payload.to_group_number is None:
        raise ValueError("to_group_number is required for broadcast")

    sender = _resolve_message_sender(payload.sender)
    if sender is None:
        raise ValueError("Sender not found.")

    if sender.role.role != "admin":
        raise ValueError("Only admin can send broadcast messages.")

    group = db.session.execute(db.select(Group).where(Group.number == payload.to_group_number)).scalar_one_or_none()
    if group is None:
        raise ValueError("Group not found.")

    # Collect students in the group: select only student ids to avoid joined eager-load duplication issues
    student_ids = db.session.execute(db.select(Student.id).where(Student.group_id == group.id)).scalars().all()
    created = 0
    external_id = getattr(payload, "external_message_id", None)

    for student_id in student_ids:
        user = db.session.get(User, student_id)
        if user is None:
            continue
        per_recipient_external_id = None
        if external_id is not None:
            per_recipient_external_id = f"{external_id}:{user.id}"
            exists = db.session.execute(
                db.select(Message).where(Message.external_id == per_recipient_external_id)
            ).scalar_one_or_none()
            if exists is not None:
                continue

        message = Message(
            sender_id=sender.id,
            recipient_id=user.id,
            external_id=per_recipient_external_id,
            message_type="broadcast",
            text=payload.message.text,
        )
        db.session.add(message)
        created += 1

    db.session.commit()
    return {"created": created}


def _normalize_broadcast_platform(platform: str) -> str:
    normalized = platform.strip().lower()
    if normalized in {"telegram", "tg"}:
        return "telegram"
    if normalized in {"vk", "vkontakte"}:
        return "vk"
    raise ValueError("platform must be 'telegram' or 'vk'.")


def poll_broadcast_messages_for_platform(platform: str) -> dict:
    """
    Return pending broadcast messages deliverable on the given bot platform.

    Only recipients with telegram_id (platform=telegram) or vk_id (platform=vk)
    are included. Marks those rows as message_type=used_broadcast.
    """
    platform = _normalize_broadcast_platform(platform)

    recipient_join = so.joinedload(Message.recipient)
    if platform == "telegram":
        pending = db.session.execute(
            db.select(Message)
            .join(Message.recipient)
            .where(
                Message.message_type == "broadcast",
                User.telegram_id.isnot(None),
            )
            .options(recipient_join)
        ).scalars().all()
    else:
        pending = db.session.execute(
            db.select(Message)
            .join(Message.recipient)
            .where(
                Message.message_type == "broadcast",
                User.vk_id.isnot(None),
            )
            .options(recipient_join)
        ).scalars().all()

    grouped: dict[tuple[int, str, datetime], dict] = {}

    for message in pending:
        recipient = message.recipient
        if recipient is None:
            continue

        bot_id = recipient.telegram_id if platform == "telegram" else recipient.vk_id
        if bot_id is None:
            continue

        created_key = message.created_at.replace(microsecond=0)
        group_key = (message.sender_id, message.text, created_key)
        bucket = grouped.setdefault(
            group_key,
            {
                "text": message.text,
                "recipient_bot_ids": [],
                "recipients": [],
                "message_ids": [],
            },
        )
        bucket["recipient_bot_ids"].append(bot_id)
        bucket["message_ids"].append(message.id)

        recipient_payload = serialize_user_for_platform(recipient, platform)
        if recipient_payload is not None:
            bucket["recipients"].append(recipient_payload)

    broadcasts = []
    delivered_message_ids: list[int] = []

    for bucket in grouped.values():
        bucket["recipient_bot_ids"] = sorted(set(bucket["recipient_bot_ids"]))
        seen_user_ids: set[int] = set()
        unique_recipients: list[dict] = []
        for recipient in bucket["recipients"]:
            user_id = recipient["id"]
            if user_id in seen_user_ids:
                continue
            seen_user_ids.add(user_id)
            unique_recipients.append(recipient)
        bucket["recipients"] = unique_recipients
        broadcasts.append(bucket)
        delivered_message_ids.extend(bucket["message_ids"])

    for message_id in delivered_message_ids:
        row = db.session.get(Message, message_id)
        if row is not None:
            row.message_type = "used_broadcast"

    db.session.commit()

    return {
        "platform": platform,
        "broadcasts": broadcasts,
        "deliveries": sum(len(item["recipient_bot_ids"]) for item in broadcasts),
    }


def serialize_message(message: Message) -> dict:
    return {
        "id": message.id,
        "external_id": message.external_id,
        "sender": serialize_user_info(message.sender),
        "recipient": serialize_user_info(message.recipient),
        "type": message.message_type,
        "text": message.text,
        "status": message.status,
        "created_at": message.created_at.isoformat(),
    }


def get_messages_for_admin() -> list[dict]:
    admin = get_admin_user()
    if admin is None:
        raise ValueError("Admin user not found.")

    messages = db.session.execute(
        db.select(Message)
        .where(Message.recipient_id == admin.id)
        .order_by(Message.created_at.desc())
    ).scalars().all()

    return [serialize_message(message) for message in messages]


def get_messages_for_user(user_id: int) -> list[dict]:
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("User not found.")

    messages = db.session.execute(
        db.select(Message)
        .where(Message.recipient_id == user.id)
        .order_by(Message.created_at.desc())
    ).scalars().all()

    return [serialize_message(message) for message in messages]


def get_messages_for_bot_user(
    telegram_id: int | None = None,
    vk_id: int | None = None,
) -> list[dict]:
    if telegram_id is None and vk_id is None:
        raise ValueError("telegram_id or vk_id must be provided.")

    user = get_user_by_bot_ids(telegram_id, vk_id)
    if user is None:
        raise ValueError("User not found.")

    messages = db.session.execute(
        db.select(Message)
        .where(Message.recipient_id == user.id)
        .order_by(Message.created_at.desc())
    ).scalars().all()

    return [serialize_message(message) for message in messages]


def serialize_user_info(user: User) -> dict:
    group = None
    if user.student_profile is not None:
        group = user.student_profile.group
    elif user.professor_profile is not None:
        group = user.professor_profile.group

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "fullname": user.fullname,
        "role": user.role.role,
        "group": {
            "number": group.number,
            "name": group.name,
        } if group is not None else None,
        "telegram_id": user.telegram_id,
        "vk_id": user.vk_id,
    }


def serialize_user_for_platform(user: User, platform: str) -> dict:
    """User payload for bot delivery: only the messenger id for the requested platform."""
    info = serialize_user_info(user)
    if platform == "telegram":
        info.pop("vk_id", None)
        if info.get("telegram_id") is None:
            return None
    else:
        info.pop("telegram_id", None)
        if info.get("vk_id") is None:
            return None
    return info


def get_all_students() -> list[dict]:
    users = db.session.execute(
        db.select(User).join(Student)
    ).scalars().all()
    return [serialize_user_info(user) for user in users]


def register_user(payload: RegisterUserInput) -> User:
    existing_user = db.session.execute(
        db.select(User).where((User.email == payload.email) | (User.username == payload.username))
    ).scalar_one_or_none()
    if existing_user is not None:
        raise ValueError("User with the same email or username already exists.")

    role = db.session.execute(
        db.select(Role).where(Role.role == payload.role)
    ).scalar_one_or_none()
    if role is None:
        raise ValueError(f"Role '{payload.role}' not found. Seed roles first.")

    user = User(
        username=payload.username,
        email=payload.email,
        fullname=payload.fullname or payload.username,
        role_id=role.id,
    )
    user.set_password(payload.password)

    db.session.add(user)
    if role.role in {"practitioner", "listener"}:
        ensure_student_profile(user)
    db.session.commit()
    return user


def assign_user_to_group(payload: AssignUserToGroupInput) -> Group:
    user = db.session.get(User, payload.user_id)
    if user is None:
        raise ValueError("User not found.")

    group = db.session.execute(
        db.select(Group).where(Group.number == payload.group_number)
    ).scalar_one_or_none()
    if group is None:
        raise ValueError("Group not found.")

    if user.role.role in {"student", "student_lecture", "practitioner", "listener"}:
        profile = db.session.get(Student, user.id)
        if profile is None:
            profile = Student(id=user.id, group_id=group.id)
            db.session.add(profile)
        else:
            profile.group_id = group.id
    elif user.role.role == "admin":
        profile = db.session.get(Professor, user.id)
        if profile is None:
            profile = Professor(id=user.id, group_id=group.id)
            db.session.add(profile)
        else:
            profile.group_id = group.id
    elif user.role.role == "professor":
        profile = db.session.get(Professor, user.id)
        if profile is None:
            profile = Professor(id=user.id, group_id=group.id)
            db.session.add(profile)
        else:
            profile.group_id = group.id
    else:
        raise ValueError("Only users with student-like roles or admin/professor can be assigned to group.")

    db.session.commit()
    return group


def sync_groups_from_sheet(rows: Iterable[SheetGroupRow]) -> dict:
    created = 0
    updated = 0
    processed = 0

    # Проверяем коллизии имен групп внутри запроса
    seen_numbers: set[str] = set()
    seen_names: set[str] = set()
    for row in rows:
        if row.number in seen_numbers:
            raise ValueError(f"Duplicate group number in payload: {row.number}")
        if row.name in seen_names:
            raise ValueError(f"Duplicate group name in payload: {row.name}")
        seen_numbers.add(row.number)
        seen_names.add(row.name)

    for row in rows:
        processed += 1
        group = db.session.execute(
            db.select(Group).where(Group.number == row.number)
        ).scalar_one_or_none()
        if group is None:
            existing_name = db.session.execute(
                db.select(Group).where(Group.name == row.name)
            ).scalar_one_or_none()
            if existing_name is not None:
                raise ValueError(
                    f"Group name '{row.name}' already exists for another group number."
                )
            db.session.add(Group(number=row.number, name=row.name))
            created += 1
            continue

        if group.name != row.name:
            if db.session.execute(
                db.select(Group).where(Group.name == row.name, Group.id != group.id)
            ).scalar_one_or_none() is not None:
                raise ValueError(
                    f"Group name '{row.name}' is already used by another group."
                )
            group.name = row.name
            updated += 1

    db.session.commit()
    return {
        "processed": processed,
        "created": created,
        "updated": updated,
    }


def sync_users_from_sheet(rows: Iterable[SheetUserRow]) -> dict:
    processed = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    for row in rows:
        processed += 1
        user = get_user_by_email(row.email)
        if user is None:
            skipped += 1
            errors.append(f"email not found: {row.email}")
            continue

        row_changed = False
        if row.fullname is not None and user.fullname != row.fullname:
            user.fullname = row.fullname
            row_changed = True

        group = None
        if row.group_number is not None:
            group = db.session.execute(
                db.select(Group).where(Group.number == row.group_number)
            ).scalar_one_or_none()
            if group is None:
                errors.append(f"{row.email}: group not found: {row.group_number}")
                continue

            if user.role.role in {"student", "student_lecture", "practitioner", "listener"}:
                student = db.session.get(Student, user.id)
                if student is None:
                    student = Student(id=user.id, group_id=group.id)
                    db.session.add(student)
                    row_changed = True
                elif student.group_id != group.id:
                    student.group_id = group.id
                    row_changed = True
            elif user.role.role == "admin":
                professor = db.session.get(Professor, user.id)
                if professor is None:
                    professor = Professor(id=user.id, group_id=group.id)
                    db.session.add(professor)
                    row_changed = True
                elif professor.group_id != group.id:
                    professor.group_id = group.id
                    row_changed = True
            elif user.role.role == "professor":
                professor = db.session.get(Professor, user.id)
                if professor is None:
                    professor = Professor(id=user.id, group_id=group.id)
                    db.session.add(professor)
                    row_changed = True
                elif professor.group_id != group.id:
                    professor.group_id = group.id
                    row_changed = True
            else:
                errors.append(f"{row.email}: role '{user.role.role}' cannot be assigned to group")
                continue

        if row.pass_id is not None or row.missed_passes is not None:
            if user.role.role not in {"student", "student_lecture", "practitioner", "listener"}:
                errors.append(f"{row.email}: pass data only supported for students")
                continue

            student = db.session.get(Student, user.id)
            if student is None:
                if group is None:
                    errors.append(f"{row.email}: student profile missing; group_number required to create profile")
                    continue
                student = Student(id=user.id, group_id=group.id)
                db.session.add(student)
                row_changed = True

            if row.pass_id is not None and student.pass_id != row.pass_id:
                student.pass_id = row.pass_id
                row_changed = True
            if row.missed_passes is not None and student.missed_passes != row.missed_passes:
                student.missed_passes = row.missed_passes
                row_changed = True

        if row_changed:
            updated += 1

    db.session.commit()
    return {
        "processed": processed,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


def submit_attendance_excuse(payload: AttendanceExcuseInput) -> AttendanceExcuse:
    timestamp_value = None
    if payload.timestamp is not None:
        parsed_timestamp = payload.timestamp
        if parsed_timestamp.endswith("Z"):
            parsed_timestamp = parsed_timestamp.replace("Z", "+00:00")
        try:
            timestamp_value = datetime.fromisoformat(parsed_timestamp)
        except ValueError:
            raise ValueError("timestamp must be a valid ISO 8601 string.")

    excuse = AttendanceExcuse(
        email=payload.email,
        reason=payload.reason,
        file_url=payload.file_url,
        timestamp=timestamp_value,
    )
    db.session.add(excuse)
    db.session.commit()
    return excuse


def check_attendance_pass(payload: AttendancePassInput) -> dict:
    student = db.session.execute(
        db.select(Student).where(Student.pass_id == payload.pass_id)
    ).scalar_one_or_none()

    if student is None:
        return {"status": "bad_pass"}

    attendance = AttendanceRecord(student_id=student.id)
    db.session.add(attendance)
    student.missed_passes += 1
    db.session.commit()

    attendance_list = [record.timestamp.isoformat() for record in student.attendance_records]

    return {
        "status": "normal_pass",
        "student_id": student.id,
        "email": student.user.email,
        "fullname": student.user.fullname,
        "missed_passes": student.missed_passes,
        "attendance": attendance_list,
    }


def bot_authenticate(payload: BotAuthInput) -> str:
    """
    Обрабатывает аутентификацию от бота.
    Возвращает user_role или ошибку.
    """
    if payload.action == "registration":
        user = db.session.execute(
            db.select(User).where(User.email == payload.mail)
        ).scalar_one_or_none()

        if user is not None:
            if not user.verify_password(payload.password):
                return "wrong_password"

            if payload.telegram_id is not None:
                existing_user_by_telegram = get_user_by_telegram_id(payload.telegram_id)
                if existing_user_by_telegram is not None and existing_user_by_telegram.id != user.id:
                    return "user_exist"
                if user.telegram_id is None:
                    user.telegram_id = payload.telegram_id
                elif user.telegram_id != payload.telegram_id:
                    return "user_exist"

            if payload.vk_id is not None:
                existing_user_by_vk = get_user_by_vk_id(payload.vk_id)
                if existing_user_by_vk is not None and existing_user_by_vk.id != user.id:
                    return "user_exist"
                if user.vk_id is None:
                    user.vk_id = payload.vk_id
                elif user.vk_id != payload.vk_id:
                    return "user_exist"

            db.session.commit()
            return user.role.role

        if payload.telegram_id is not None:
            existing_user_by_telegram = get_user_by_telegram_id(payload.telegram_id)
            if existing_user_by_telegram is not None:
                return "user_exist"

        if payload.vk_id is not None:
            existing_user_by_vk = get_user_by_vk_id(payload.vk_id)
            if existing_user_by_vk is not None:
                return "user_exist"

        role = db.session.execute(
            db.select(Role).where(Role.role == "listener")
        ).scalar_one_or_none()
        if role is None:
            raise ValueError("Role 'listener' not found. Seed roles first.")

        user = User(
            username=payload.mail,
            email=payload.mail,
            fullname=payload.fullname,
            telegram_id=payload.telegram_id,
            vk_id=payload.vk_id,
            role_id=role.id,
        )
        user.set_password(payload.password)
        db.session.add(user)
        db.session.commit()
        return role.role

    elif payload.action == "enter":
        user = db.session.execute(
            db.select(User).where(User.email == payload.mail)
        ).scalar_one_or_none()
        if user is None:
            return "there is not such user"

        if not user.verify_password(payload.password):
            return "wrong_password"

        if payload.telegram_id is not None and user.telegram_id is not None and user.telegram_id != payload.telegram_id:
            return "user_exist"

        if payload.vk_id is not None and user.vk_id is not None and user.vk_id != payload.vk_id:
            return "user_exist"

        if payload.telegram_id is not None and user.telegram_id is None:
            user.telegram_id = payload.telegram_id

        if payload.vk_id is not None and user.vk_id is None:
            user.vk_id = payload.vk_id

        if payload.telegram_id is not None or payload.vk_id is not None:
            db.session.commit()

        return user.role.role

    raise ValueError("Invalid action.")


def export_users_for_sheet() -> list[dict]:
    """
    Экспортирует всех пользователей для Google Sheets.
    Возвращает список с email, fullname, group_number, pass_id, missed_passes.
    """
    users = db.session.execute(db.select(User)).scalars().all()
    result = []

    for user in users:
        ban_expires_at = user.ban_expires_at
        row = {
            "email": user.email,
            "fullname": user.fullname,
            "group_number": None,
            "pass_id": None,
            "missed_passes": None,
            "ban_expires_at": ban_expires_at.isoformat() if ban_expires_at else None,
            "is_banned": ban_expires_at is not None and ban_expires_at > datetime.utcnow(),
        }

        if user.student_profile is not None:
            student = user.student_profile
            row["group_number"] = student.group.number if student.group else None
            row["pass_id"] = student.pass_id
            row["missed_passes"] = student.missed_passes
        elif user.professor_profile is not None:
            professor = user.professor_profile
            row["group_number"] = professor.group.number if professor.group else None

        result.append(row)

    return result


def export_groups_for_sheet() -> list[dict]:
    """
    Экспортирует все группы для Google Sheets.
    Возвращает список с number и name.
    """
    groups = db.session.execute(db.select(Group)).scalars().all()
    return [{"number": group.number, "name": group.name} for group in groups]


def sync_attendance_from_sheet(rows: Iterable[SheetAttendanceRow]) -> dict:
    """
    Импортирует записи посещений из Google Sheets.
    Создаёт AttendanceRecord для каждой строки (только для attended=True).
    """
    processed = 0
    created = 0
    skipped = 0
    errors: list[str] = []

    for row in rows:
        processed += 1
        user = get_user_by_email(row.email)
        if user is None:
            skipped += 1
            errors.append(f"user not found for email: {row.email}")
            continue

        student = db.session.get(Student, user.id)
        if student is None:
            skipped += 1
            errors.append(f"{row.email}: not a student")
            continue

        existing = db.session.execute(
            db.select(AttendanceRecord).where(
                (AttendanceRecord.student_id == student.id)
                & (AttendanceRecord.timestamp == row.timestamp)
            )
        ).scalar_one_or_none()

        if not row.attended:
            if existing is not None:
                db.session.delete(existing)
                created += 1
            else:
                skipped += 1
            continue

        if existing is not None:
            continue

        attendance = AttendanceRecord(student_id=student.id, timestamp=row.timestamp)
        db.session.add(attendance)
        created += 1

    db.session.commit()
    return {
        "processed": processed,
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }


def export_attendance_for_sheet() -> list[dict]:
    """
    Экспортирует все записи посещений для Google Sheets.
    Возвращает список с email, timestamp, attended=True.
    """
    records = db.session.execute(db.select(AttendanceRecord)).scalars().all()
    result = []

    for record in records:
        if record.student and record.student.user:
            row = {
                "email": record.student.user.email,
                "timestamp": record.timestamp.isoformat(),
                "attended": True,
            }
            result.append(row)

    return result


# ============================================================================
# Approach Queue Management Functions
# ============================================================================

def _recalculate_queue_positions(professor_id: int, lesson_date: datetime) -> None:
    """
    Пересчитать позиции в очереди на основе количества сданных лаб.
    Студенты с большим количеством сданных лаб получают меньший номер позиции.
    """
    queue_entries = db.session.execute(
        db.select(ApproachQueue).where(
            (ApproachQueue.professor_id == professor_id) &
            (ApproachQueue.lesson_date == lesson_date) &
            (ApproachQueue.status == "pending")
        )
    ).scalars().all()
    
    # Для каждого студента вычислить количество сданных лаб
    entries_with_scores = []
    for entry in queue_entries:
        lab_count = db.session.execute(
            db.select(db.func.count(StudentLabScore.id)).where(
                (StudentLabScore.student_id == entry.student_id) &
                (StudentLabScore.score.isnot(None)) &
                (StudentLabScore.score > 0)
            )
        ).scalar() or 0
        entries_with_scores.append((entry, lab_count))
    
    # Отсортировать по количеству лаб (по убыванию), затем по времени добавления в очередь
    entries_with_scores.sort(key=lambda x: (-x[1], x[0].created_at))
    
    # Обновить позиции
    for idx, (entry, lab_count) in enumerate(entries_with_scores, start=1):
        entry.position = idx


def add_to_queue(payload) -> dict:
    """
    Добавить студента в очередь на занятие.
    
    Правила:
    - Студент должен быть с ролью 'practitioner'
    - Студент может быть только в одной очереди на одно занятие у одного преподавателя
    - Позиция автоматически рассчитывается на основе количества сданных лаб
    """
    payload = AddToQueueInput(
        student_id=payload.get("student_id"),
        professor_id=payload.get("professor_id"),
        lesson_date=payload.get("lesson_date"),
        labs_count=payload.get("labs_count", 1),
    )
    
    lesson_date = payload.lesson_date
    if lesson_date is None:
        lesson_date = _parse_lesson_date(None)
    elif isinstance(lesson_date, str):
        lesson_date = _parse_lesson_date(lesson_date)
    payload.lesson_date = lesson_date
    
    # Проверить, что студент существует и имеет роль practitioner
    student = db.session.get(Student, payload.student_id)
    if student is None:
        raise ValueError("Student not found.")
    
    if student.user.role.role != "practitioner":
        raise ValueError("Only practitioners can join the queue.")

    if is_user_currently_banned(student.user):
        return banned_status_response()
    
    # Проверить, что преподаватель существует
    professor = db.session.get(Professor, payload.professor_id)
    if professor is None:
        raise ValueError("Professor not found.")
    
    # Проверить, что студент уже не в очереди для этого преподавателя на эту дату
    existing = db.session.execute(
        db.select(ApproachQueue).where(
            (ApproachQueue.student_id == payload.student_id) &
            (ApproachQueue.professor_id == payload.professor_id) &
            (ApproachQueue.lesson_date == payload.lesson_date) &
            (ApproachQueue.status == "pending")
        )
    ).scalar_one_or_none()
    
    if existing is not None:
        raise ValueError("Student is already in the queue for this lesson.")
    
    # Создать новую запись в очереди
    queue_entry = ApproachQueue(
        student_id=payload.student_id,
        professor_id=payload.professor_id,
        lesson_date=payload.lesson_date,
        position=1,  # Временная позиция, будет пересчитана ниже
        status="pending",
        labs_count=payload.labs_count,
    )
    db.session.add(queue_entry)
    db.session.flush()
    
    # Пересчитать позиции для всей очереди (включая только что добавленного студента)
    _recalculate_queue_positions(payload.professor_id, payload.lesson_date)
    db.session.commit()
    
    return {
        "status": "success",
        "queue_id": queue_entry.id,
        "position": queue_entry.position,
        "labs_count": queue_entry.labs_count,
        "message": f"Added to queue at position {queue_entry.position}"
    }


def add_to_queue_by_bot(payload) -> dict:
    payload = AddToQueueBotInput(
        telegram_id=payload.get("telegram_id"),
        vk_id=payload.get("vk_id"),
        labs_count=payload.get("labs_count", 1),
        lesson_date=payload.get("lesson_date"),
    )
    
    student = _resolve_student_by_bot_ids(payload.telegram_id, payload.vk_id)
    professor = _resolve_professor_for_student(student)
    lesson_date = _parse_lesson_date(payload.lesson_date)
    
    return add_to_queue({
        "student_id": student.id,
        "professor_id": professor.id,
        "lesson_date": lesson_date.isoformat(),
        "labs_count": payload.labs_count,
    })


def remove_from_queue_by_bot(payload) -> dict:
    payload = AddToQueueBotInput(
        telegram_id=payload.get("telegram_id"),
        vk_id=payload.get("vk_id"),
        labs_count=1,
        lesson_date=payload.get("lesson_date"),
    )
    
    student = _resolve_student_by_bot_ids(payload.telegram_id, payload.vk_id)
    if is_user_currently_banned(student.user):
        return banned_status_response()
    professor = _resolve_professor_for_student(student)
    lesson_date = _parse_lesson_date(payload.lesson_date)
    
    return remove_from_queue({
        "student_id": student.id,
        "professor_id": professor.id,
        "lesson_date": lesson_date.isoformat(),
    })


def get_queue_position_by_bot(payload) -> dict:
    payload = AddToQueueBotInput(
        telegram_id=payload.get("telegram_id"),
        vk_id=payload.get("vk_id"),
        labs_count=1,
        lesson_date=payload.get("lesson_date"),
    )
    
    student = _resolve_student_by_bot_ids(payload.telegram_id, payload.vk_id)
    if is_user_currently_banned(student.user):
        return banned_status_response()
    professor = _resolve_professor_for_student(student)
    lesson_date = _parse_lesson_date(payload.lesson_date)
    
    return get_queue_position({
        "student_id": student.id,
        "professor_id": professor.id,
        "lesson_date": lesson_date.isoformat(),
    })


def remove_from_queue(payload) -> dict:
    """
    Удалить студента из очереди.
    
    При удалении переиндексируются позиции остальных студентов.
    """
    payload = RemoveFromQueueInput(
        student_id=payload.get("student_id"),
        professor_id=payload.get("professor_id"),
        lesson_date=payload.get("lesson_date")
    )
    
    # Найти запись в очереди
    queue_entry = db.session.execute(
        db.select(ApproachQueue).where(
            (ApproachQueue.student_id == payload.student_id) &
            (ApproachQueue.professor_id == payload.professor_id) &
            (ApproachQueue.lesson_date == payload.lesson_date) &
            (ApproachQueue.status == "pending")
        )
    ).scalar_one_or_none()
    
    if queue_entry is None:
        raise ValueError("Student is not in the queue for this lesson.")
    
    db.session.delete(queue_entry)
    db.session.flush()
    
    # Пересчитать позиции для оставшихся студентов
    _recalculate_queue_positions(payload.professor_id, payload.lesson_date)
    db.session.commit()
    
    return {
        "status": "success",
        "message": f"Removed from queue. Remaining students reindexed."
    }


def get_queue_position(payload) -> dict:
    """
    Получить позицию студента в очереди.
    """
    payload = GetQueuePositionInput(
        student_id=payload.get("student_id"),
        professor_id=payload.get("professor_id"),
        lesson_date=payload.get("lesson_date")
    )
    
    queue_entry = db.session.execute(
        db.select(ApproachQueue).where(
            (ApproachQueue.student_id == payload.student_id) &
            (ApproachQueue.professor_id == payload.professor_id) &
            (ApproachQueue.lesson_date == payload.lesson_date) &
            (ApproachQueue.status == "pending")
        )
    ).scalar_one_or_none()
    
    if queue_entry is None:
        return {
            "status": "not_in_queue",
            "position": None,
            "message": "Student is not in the queue."
        }
    
    return {
        "status": "in_queue",
        "position": queue_entry.position,
        "created_at": queue_entry.created_at.isoformat(),
        "lesson_date": queue_entry.lesson_date.isoformat(),
    }


def get_queue_for_lesson(payload) -> dict:
    """
    Получить всю очередь для занятия (список студентов в порядке ожидания).
    """
    payload = GetQueueForLessonInput(
        professor_id=payload.get("professor_id"),
        lesson_date=payload.get("lesson_date")
    )
    
    queue_entries = db.session.execute(
        db.select(ApproachQueue).where(
            (ApproachQueue.professor_id == payload.professor_id) &
            (ApproachQueue.lesson_date == payload.lesson_date) &
            (ApproachQueue.status == "pending")
        ).order_by(ApproachQueue.position)
    ).scalars().all()
    
    queue_list = []
    for entry in queue_entries:
        queue_list.append({
            "position": entry.position,
            "student_id": entry.student_id,
            "student_email": entry.student.user.email,
            "student_fullname": entry.student.user.fullname,
            "created_at": entry.created_at.isoformat(),
        })
    
    return {
        "status": "success",
        "lesson_date": payload.lesson_date.isoformat(),
        "professor_id": payload.professor_id,
        "queue_length": len(queue_list),
        "queue": queue_list
    }


# ============================================================================
# Broadcast Helper Functions (for bot)
# ============================================================================

def get_all_groups() -> list[dict]:
    """Get all existing groups.
    
    Returns list of groups with id, number, and name.
    """
    groups = db.session.execute(db.select(Group)).scalars().all()
    return [
        {
            "id": group.id,
            "number": group.number,
            "name": group.name,
        }
        for group in groups
    ]


def get_students_by_group_number(group_number: str) -> dict:
    """Get all student user IDs in a group by group number.
    
    Returns dict with user_ids list.
    """
    group = db.session.execute(
        db.select(Group).where(Group.number == group_number)
    ).scalar_one_or_none()
    
    if group is None:
        raise ValueError("Group not found.")
    
    student_ids = db.session.execute(
        db.select(Student.id).where(Student.group_id == group.id)
    ).scalars().all()

    user_ids = student_ids
    return {
        "group_number": group.number,
        "group_name": group.name,
        "user_ids": user_ids,
    }


def get_students_by_group_id(group_id: int) -> dict:
    """Get all student user IDs in a group by group id.

    Returns dict with user_ids list.
    """
    group = db.session.get(Group, group_id)

    if group is None:
        raise ValueError("Group not found.")

    student_ids = db.session.execute(
        db.select(Student.id).where(Student.group_id == group.id)
    ).scalars().all()

    user_ids = student_ids
    return {
        "group_id": group.id,
        "group_number": group.number,
        "group_name": group.name,
        "user_ids": user_ids,
    }


# ============================================================================
# Task Management Functions
# ============================================================================

def create_task(payload, created_by_id: int) -> dict:
    """
    Создать новое задание для группы.
    
    Параметры:
    - payload: CreateTaskInput с данными задания
    - created_by_id: ID пользователя, создающего задание
    """
    from app.src.domain.task import Task
    
    # Проверить, что группа существует
    group = db.session.get(Group, payload.group_id)
    if group is None:
        raise ValueError("Group not found.")
    
    # Создать новое задание
    task = Task(
        group_id=payload.group_id,
        created_by_id=created_by_id,
        title=payload.title,
        description=payload.description,
        file_url=payload.file_url,
        due_date=payload.due_date,
    )
    db.session.add(task)
    db.session.commit()
    
    return {
        "status": "success",
        "task_id": task.id,
        "title": task.title,
        "group_id": task.group_id,
        "message": "Task created successfully"
    }


def get_student_tasks(telegram_id: int = None, vk_id: int = None) -> dict:
    """
    Получить список заданий для студента.
    
    Студент ищется по telegram_id или vk_id.
    """
    # Найти студента
    student = _resolve_student_by_bot_ids(telegram_id, vk_id)
    
    if student.group_id is None:
        return {
            "status": "success",
            "tasks": [],
            "message": "Student has no group"
        }
    
    # Получить все задания для группы студента
    tasks = db.session.execute(
        db.select(Task).where(Task.group_id == student.group_id).order_by(Task.created_at.desc())
    ).scalars().all()
    
    task_list = []
    for task in tasks:
        # Проверить, есть ли уже ответ от этого студента
        student_response = db.session.execute(
            db.select(TaskResponse).where(
                (TaskResponse.task_id == task.id) &
                (TaskResponse.student_id == student.id)
            )
        ).scalar_one_or_none()
        
        task_list.append({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "file_url": task.file_url,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "created_at": task.created_at.isoformat(),
            "submitted": student_response is not None,
        })
    
    return {
        "status": "success",
        "tasks": task_list,
        "count": len(task_list)
    }


def submit_task_response(payload) -> dict:
    """
    Отправить ответ на задание.
    """
    from app.src.domain.task import TaskResponse
    
    # Найти студента
    student = _resolve_student_by_bot_ids(payload.telegram_id, payload.vk_id)
    
    # Проверить, что задание существует
    task = db.session.get(Task, payload.task_id)
    if task is None:
        raise ValueError("Task not found.")
    
    # Проверить, что студент в группе, к которой назначено задание
    if student.group_id != task.group_id:
        raise ValueError("Student does not have access to this task.")
    
    # Проверить, есть ли уже ответ от этого студента
    existing_response = db.session.execute(
        db.select(TaskResponse).where(
            (TaskResponse.task_id == payload.task_id) &
            (TaskResponse.student_id == student.id)
        )
    ).scalar_one_or_none()
    
    if existing_response:
        # Обновить существующий ответ
        existing_response.response_text = payload.response_text
        existing_response.file_url = payload.file_url
        existing_response.submitted_at = datetime.utcnow()
        db.session.commit()
        return {
            "status": "success",
            "response_id": existing_response.id,
            "message": "Response updated successfully"
        }
    else:
        # Создать новый ответ
        response = TaskResponse(
            task_id=payload.task_id,
            student_id=student.id,
            response_text=payload.response_text,
            file_url=payload.file_url,
        )
        db.session.add(response)
        db.session.commit()
        return {
            "status": "success",
            "response_id": response.id,
            "message": "Response submitted successfully"
        }


def get_task_responses(task_id: int) -> dict:
    """
    Получить все ответы на задание.
    """
    # Проверить, что задание существует
    task = db.session.get(Task, task_id)
    if task is None:
        raise ValueError("Task not found.")
    
    # Получить все ответы
    responses = db.session.execute(
        db.select(TaskResponse).where(TaskResponse.task_id == task_id).order_by(TaskResponse.submitted_at.desc())
    ).scalars().all()
    
    response_list = []
    for resp in responses:
        response_list.append({
            "id": resp.id,
            "student_id": resp.student_id,
            "student_email": resp.student.user.email,
            "student_fullname": resp.student.user.fullname,
            "response_text": resp.response_text,
            "file_url": resp.file_url,
            "score": resp.score,
            "feedback": resp.feedback,
            "status": resp.status,
            "submitted_at": resp.submitted_at.isoformat(),
            "graded_at": resp.graded_at.isoformat() if resp.graded_at else None,
        })
    
    return {
        "status": "success",
        "task_id": task_id,
        "task_title": task.title,
        "responses": response_list,
        "response_count": len(response_list)
    }
