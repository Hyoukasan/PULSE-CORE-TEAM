from typing import Iterable

from app.src.integrations.db import db
from app.src.domain.group import Group
from app.src.domain.professor import Professor
from app.src.domain.role import Role
from app.src.domain.student import Student
from app.src.domain.user import User

from .schemas import AssignUserToGroupInput, RegisterUserInput, SheetGroupRow, BotAuthInput
from .validators import determine_user_role_from_email


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

    if user.role.role == "student":
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
        raise ValueError("Only users with roles student/professor can be assigned to group.")

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


def bot_authenticate(payload: BotAuthInput) -> str:
    """
    Обрабатывает аутентификацию от бота.
    Возвращает user_role или ошибку.
    """
    if payload.action == "registration":
        # Проверить, существует ли пользователь с таким email
        existing_user = db.session.execute(
            db.select(User).where(User.email == payload.mail)
        ).scalar_one_or_none()
        if existing_user is not None:
            return "wrong_mail"

        # Определить роль
        user_role, db_role = determine_user_role_from_email(payload.mail)

        # Найти роль в БД
        role = db.session.execute(
            db.select(Role).where(Role.role == db_role)
        ).scalar_one_or_none()
        if role is None:
            raise ValueError(f"Role '{db_role}' not found. Seed roles first.")

        # Создать пользователя
        user = User(
            username=payload.mail,  # Используем email как username
            email=payload.mail,
            telegram_id=payload.telegram_id,
            role_id=role.id,
        )
        user.set_password(payload.password)
        db.session.add(user)
        db.session.commit()
        return user_role

    elif payload.action == "enter":
        # Найти пользователя по email
        user = db.session.execute(
            db.select(User).where(User.email == payload.mail)
        ).scalar_one_or_none()
        if user is None:
            return "wrong_mail"

        # Проверить пароль
        if not user.verify_password(payload.password):
            return "wrong_password"

        # Обновить telegram_id, если отличается
        if user.telegram_id != payload.telegram_id:
            user.telegram_id = payload.telegram_id
            db.session.commit()

        # Вернуть роль
        role_name = user.role.role
        if role_name == "professor":
            return "teacher"
        elif role_name == "student":
            # Для простоты, если lecture — но пока нет, возвращаем student
            return "student"
        elif role_name == "admin":
            return "admin"
        else:
            return "student"  # fallback

    raise ValueError("Invalid action.")

