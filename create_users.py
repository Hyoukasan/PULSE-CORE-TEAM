from app.main import create_app
from app.src.integrations.db import db
from app.src.domain.group import Group
from app.src.domain.professor import Professor
from app.src.domain.role import Role
from app.src.domain.student import Student
from app.src.domain.user import User

app = create_app()

def ensure_group(number: str, name: str) -> Group:
    group = db.session.execute(db.select(Group).where(Group.number == number)).scalar_one_or_none()
    if group is None:
        group = Group(number=number, name=name)
        db.session.add(group)
        db.session.commit()
        print(f'✓ Создана группа: {number} / {name}')
    else:
        print(f'✓ Группа уже существует: {number} / {name}')
    return group

def ensure_roles() -> None:
    base_roles = ["admin", "student", "professor"]
    created = 0
    for role_name in base_roles:
        exists = db.session.execute(db.select(Role).where(Role.role == role_name)).scalar_one_or_none()
        if exists is None:
            db.session.add(Role(role=role_name))
            created += 1
    if created > 0:
        db.session.commit()
        print(f'✓ Создано ролей: {created}')
    else:
        print('✓ Роли уже существуют: admin, student, professor')


with app.app_context():
    ensure_roles()
    group = ensure_group('TEST_GROUP', 'TESTGRP1')

    users = [
        ('golomazov.rs@edu.spbstu.ru', 'golomazov.rs', 'Golomazov RS', 'admin'),
        ('kolesnikova.sm@edu.spbstu.ru', 'kolesnikova.sm', 'Kolesnikova SM', 'professor'),
        ('karpov.ds@edu.spbstu.ru', 'Karpov.ds', 'Karpov DS', 'professor'),
        ('avtodeevivan@gmail.com', 'avtodeevivan', 'Avtodeev Ivan', 'student'),
    ]

    for email, username, fullname, role in users:
        existing = db.session.execute(db.select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            print(f'✓ Уже существует: {email}')
        else:
            r = db.session.execute(db.select(Role).where(Role.role == role)).scalar_one_or_none()
            if r is None:
                raise RuntimeError(f"Роль {role} не найдена. Запустите seed-roles.")
            u = User(username=username, email=email, fullname=fullname, role_id=r.id)
            u.set_password('demo-pass')
            db.session.add(u)
            db.session.commit()
            existing = u
            print(f'✓ Создан: {email} (роль: {role})')

    student_role = db.session.execute(db.select(Role).where(Role.role == 'student')).scalar_one_or_none()
    professor_role = db.session.execute(db.select(Role).where(Role.role == 'professor')).scalar_one_or_none()

    if student_role is None or professor_role is None:
        raise RuntimeError('Роли student/professor не найдены. Запустите seed-roles.')

    users_to_assign = db.session.execute(
        db.select(User).where(User.role_id.in_([student_role.id, professor_role.id]))
    ).scalars().all()

    assigned_students = 0
    assigned_professors = 0

    for user in users_to_assign:
        if user.role_id == student_role.id:
            profile = db.session.get(Student, user.id)
            if profile is None:
                db.session.add(Student(id=user.id, group_id=group.id))
                assigned_students += 1
            elif profile.group_id != group.id:
                profile.group_id = group.id
                assigned_students += 1
        elif user.role_id == professor_role.id:
            profile = db.session.get(Professor, user.id)
            if profile is None:
                db.session.add(Professor(id=user.id, group_id=group.id))
                assigned_professors += 1
            elif profile.group_id != group.id:
                profile.group_id = group.id
                assigned_professors += 1

    db.session.commit()

    print(f'✓ Пользователи student/professor назначены в группу {group.number}:')
    print(f'  students assigned/updated: {assigned_students}')
    print(f'  professors assigned/updated: {assigned_professors}')
