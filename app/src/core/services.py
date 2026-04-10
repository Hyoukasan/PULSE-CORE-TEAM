from datetime import datetime
from typing import Iterable

from app.src.integrations.db import db
from app.src.domain.attendance_excuse import AttendanceExcuse
from app.src.domain.attendance_record import AttendanceRecord
from app.src.domain.group import Group
from app.src.domain.message import Message
from app.src.domain.professor import Professor
from app.src.domain.role import Role
from app.src.domain.student import Student
from app.src.domain.user import User

from .schemas import (
    AuthLoginInput,
    AssignUserToGroupInput,
    AttendanceExcuseInput,
    AttendancePassInput,
    MessagePayload,
    MessageSenderInput,
    RegisterUserInput,
    SendMessageInput,
    SheetGroupRow,
    BotAuthInput,
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


def authenticate_user(payload: AuthLoginInput) -> User:
    user = db.session.execute(
        db.select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    
    # Если пользователя нет и указана платформа (социальная аутентификация)
    if user is None and payload.platform:
        existing_by_vk = None
        if payload.vk_id is not None:
            existing_by_vk = get_user_by_telegram_id(payload.vk_id)

        if existing_by_vk is not None:
            if existing_by_vk.email != payload.email:
                raise ValueError("Email does not match existing telegram account.")
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
        else:
            # Уже существует пользователь с таким telegram_id, проверяем пароль
            if not user.verify_password(payload.password):
                raise ValueError("Invalid email or password.")

        # Если есть vk_id, сохранить его (или подтвердить соответствие)
        if payload.vk_id is not None and user.telegram_id != payload.vk_id:
            if user.telegram_id is not None:
                raise ValueError("Telegram ID does not match user account.")
            user.telegram_id = payload.vk_id

        if user not in db.session:
            db.session.add(user)
        try:
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            raise ValueError("Unable to create or update user during social login.") from error
        return user
    
    # Обычная аутентификация по паролю
    if user is None or not user.verify_password(payload.password):
        raise ValueError("Invalid email or password.")
    
    # Обновить vk_id если приходит при каждом логине
    if payload.vk_id is not None and user.telegram_id != payload.vk_id:
        user.telegram_id = payload.vk_id
        db.session.commit()
    
    return user


def get_user_by_id(user_id: int) -> User | None:
    return db.session.get(User, user_id)


def get_user_by_email(email: str) -> User | None:
    return db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()


def get_user_by_telegram_id(telegram_id: int) -> User | None:
    return db.session.execute(
        db.select(User).where(User.telegram_id == telegram_id)
    ).scalar_one_or_none()


def get_message_recipient(
    sender: User,
    to_user_id: int | None = None,
    to_telegram_id: int | None = None,
) -> User:
    if sender.role.role in {"student", "student_lecture", "practitioner", "listener"}:
        profile = db.session.get(Student, sender.id)
        if profile is None or profile.group_id is None:
            raise ValueError("Student is not assigned to a group.")
        recipient = db.session.execute(
            db.select(Professor).where(Professor.group_id == profile.group_id)
        ).scalar_one_or_none()
        if recipient is None:
            raise ValueError("No professor found for student's group.")
        return recipient.user

    if sender.role.role == "professor":
        if not any((to_user_id, to_telegram_id)):
            raise ValueError("Professor must specify recipient user_id or telegram_id.")

        recipient = None
        if to_user_id is not None:
            recipient = get_user_by_id(to_user_id)
        elif to_telegram_id is not None:
            recipient = get_user_by_telegram_id(to_telegram_id)

        if recipient is None:
            raise ValueError("Student recipient not found.")
        if recipient.role.role not in {"student", "student_lecture", "practitioner", "listener"}:
            raise ValueError("Recipient must be a student.")
        return recipient

    raise ValueError("Only students and professors can send messages.")


def send_message(payload: SendMessageInput) -> Message:
    sender = None
    if payload.sender.user_id is not None:
        sender = db.session.get(User, payload.sender.user_id)
    if sender is None and payload.sender.telegram_id is not None:
        sender = get_user_by_telegram_id(payload.sender.telegram_id)
    if sender is None:
        raise ValueError("Sender not found.")

    recipient = get_message_recipient(
        sender,
        to_user_id=payload.to_user_id,
        to_telegram_id=payload.to_telegram_id,
    )
    
    message = Message(
        sender_id=sender.id,
        recipient_id=recipient.id,
        message_type=payload.message.type or "text",
        text=payload.message.text,
    )
    db.session.add(message)
    db.session.commit()
    return message


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
    }


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
    elif user.role.role == "professor":
        profile = db.session.get(Professor, user.id)
        if profile is None:
            profile = Professor(id=user.id, group_id=group.id)
            db.session.add(profile)
        else:
            profile.group_id = group.id
    else:
        raise ValueError("Only users with student-like roles or professor can be assigned to group.")

    db.session.commit()
    return group


def sync_groups_from_sheet(rows: Iterable[SheetGroupRow]) -> dict:
    created = 0
    updated = 0
    processed = 0

    for row in rows:
        processed += 1
        group = db.session.execute(
            db.select(Group).where(Group.number == row.number)
        ).scalar_one_or_none()
        if group is None:
            db.session.add(Group(number=row.number, name=row.name))
            created += 1
            continue

        if group.name != row.name:
            group.name = row.name
            updated += 1

    db.session.commit()
    return {
        "processed": processed,
        "created": created,
        "updated": updated,
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
            return "user_exist"

        if payload.telegram_id is not None:
            existing_user_by_telegram = get_user_by_telegram_id(payload.telegram_id)
            if existing_user_by_telegram is not None:
                return "user_exist"

        user_role, db_role = determine_user_role_from_email(payload.mail)
        role = db.session.execute(
            db.select(Role).where(Role.role == db_role)
        ).scalar_one_or_none()
        if role is None:
            raise ValueError(f"Role '{db_role}' not found. Seed roles first.")

        user = User(
            username=payload.mail,
            email=payload.mail,
            fullname=payload.fullname,
            telegram_id=payload.telegram_id,
            role_id=role.id,
        )
        user.set_password(payload.password)
        db.session.add(user)
        db.session.commit()
        return _normalize_user_role(user.role.role)

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

        if payload.telegram_id is not None and user.telegram_id is None:
            user.telegram_id = payload.telegram_id
            db.session.commit()

        return _normalize_user_role(user.role.role)

    raise ValueError("Invalid action.")

