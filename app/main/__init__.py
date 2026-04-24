from datetime import datetime, timezone

import click
from flask import Flask, jsonify, render_template_string
from dotenv import load_dotenv
from swagger_gen.swagger import Swagger
from swagger_gen.lib.wrappers import swagger_metadata

import app.src.domain
from .config import config
from app.src.integrations.db import db
from app.src.integrations.redis_client import init_redis


def register_blueprints(app: Flask) -> None:
    from app.api import v1    

    app.register_blueprint(v1.health.bp)
    app.register_blueprint(v1.auth.bp)
    app.register_blueprint(v1.attendance.bp)
    app.register_blueprint(v1.groups.bp)
    app.register_blueprint(v1.messages.bp)
    app.register_blueprint(v1.users.bp)
    app.register_blueprint(v1.arduino.bp)


def register_cli(app: Flask) -> None:
    @app.cli.command("db-init")
    def db_init() -> None:
        """Create all database tables and seed base roles (dev-only)."""
        with app.app_context():
            db.create_all()
            seed_roles()
        click.echo("DB initialized (create_all) and seeded base roles.")

    @app.cli.command("db-drop")
    def db_drop() -> None:
        """Drop all database tables (DANGEROUS)."""
        click.confirm(
            "This will DROP ALL tables. Are you sure?",
            default=False,
            abort=True,
        )
        with app.app_context():
            db.session.remove()
            engine = db.session.get_bind()
            if engine is not None:
                engine.dispose()
            db.drop_all()
        click.echo("DB dropped (drop_all).")

    @app.cli.command("db-reset")
    def db_reset() -> None:
        """Drop and recreate all tables, then seed base roles (DANGEROUS)."""
        click.confirm(
            "This will DROP and RECREATE ALL tables. Are you sure?",
            default=False,
            abort=True,
        )
        with app.app_context():
            db.session.remove()
            engine = db.session.get_bind()
            if engine is not None:
                engine.dispose()
            db.drop_all()
            db.create_all()
            seed_roles()
        click.echo("DB reset (drop_all + create_all) and seeded base roles.")

    @app.cli.command("seed-roles")
    def seed_roles() -> None:
        """Insert base roles if they do not exist."""
        from app.src.domain.role import Role

        base_roles = (
            "admin",
            "student",
            "student_lecture",
            "practitioner",
            "listener",
            "professor",
        )
        created_count = 0

        with app.app_context():
            for role_name in base_roles:
                exists = db.session.execute(
                    db.select(Role).where(Role.role == role_name)
                ).scalar_one_or_none()
                if exists is None:
                    db.session.add(Role(role=role_name))
                    created_count += 1

            db.session.commit()

        click.echo(f"Roles seeded. Created: {created_count}, total expected: {len(base_roles)}.")

    @app.cli.command("db-smoke")
    def db_smoke() -> None:
        """Create temporary entities and verify key ORM relationships."""
        from app.src.domain.role import Role
        from app.src.domain.user import User
        from app.src.domain.group import Group
        from app.src.domain.student import Student
        from app.src.domain.professor import Professor

        suffix = int(datetime.now(timezone.utc).timestamp())

        with app.app_context():
            student_role = db.session.execute(
                db.select(Role).where(Role.role == "student")
            ).scalar_one_or_none()
            professor_role = db.session.execute(
                db.select(Role).where(Role.role == "professor")
            ).scalar_one_or_none()

            if student_role is None or professor_role is None:
                click.echo("Missing required roles. Run `flask --app pulse_project seed-roles` first.")
                return

            student_user = User(
                username=f"smoke_student_{suffix}",
                email=f"smoke_student_{suffix}@local.test",
                role_id=student_role.id,
            )
            student_user.set_password("smoke-pass")

            professor_user = User(
                username=f"smoke_professor_{suffix}",
                email=f"smoke_professor_{suffix}@local.test",
                role_id=professor_role.id,
            )
            professor_user.set_password("smoke-pass")

            group = Group(
                number=f"SMK-{suffix}",
                name=f"S{suffix % 100000000:08d}",
            )

            db.session.add_all([student_user, professor_user, group])
            db.session.flush()

            student = Student(id=student_user.id, group_id=group.id)
            professor = Professor(id=professor_user.id, group_id=group.id)
            db.session.add_all([student, professor])
            db.session.commit()

            # Read back and verify both directions of relations.
            loaded_student = db.session.get(Student, student_user.id)
            loaded_professor = db.session.get(Professor, professor_user.id)
            loaded_group = db.session.get(Group, group.id)

            if (
                loaded_student is None
                or loaded_student.user is None
                or loaded_student.group is None
                or loaded_professor is None
                or loaded_professor.user is None
                or loaded_professor.group is None
                or loaded_group is None
            ):
                raise RuntimeError("Smoke relation check failed: missing relation objects.")

            if len(loaded_group.students) < 1 or len(loaded_group.professors) < 1:
                raise RuntimeError("Smoke relation check failed: group reverse relations are empty.")

            # Cleanup temporary entities.
            db.session.delete(loaded_student)
            db.session.delete(loaded_professor)
            db.session.delete(student_user)
            db.session.delete(professor_user)
            db.session.delete(loaded_group)
            db.session.commit()

        click.echo("DB smoke test passed and temporary records were removed.")

    @app.cli.command("seed-demo-data")
    def seed_demo_data() -> None:
        """Create one demo group, student, and professor for manual testing (idempotent)."""
        from app.src.domain.role import Role
        from app.src.domain.user import User
        from app.src.domain.group import Group
        from app.src.domain.student import Student
        from app.src.domain.professor import Professor

        demo_group_number = "DEMO-1"
        demo_group_name = "DEMO01"
        demo_password = "demo-pass"
        student_email = "demo_student@edu.spbstu.ru"
        professor_email = "demo_professor@edu.spbstu.ru"
        yarchenko_email = "yarchenko.da@edu.spbstu.ru"

        with app.app_context():
            student_role = db.session.execute(
                db.select(Role).where(Role.role == "student")
            ).scalar_one_or_none()
            professor_role = db.session.execute(
                db.select(Role).where(Role.role == "professor")
            ).scalar_one_or_none()

            if student_role is None or professor_role is None:
                click.echo("Missing roles. Run: flask --app pulse_project seed-roles")
                return

            group = db.session.execute(
                db.select(Group).where(Group.number == demo_group_number)
            ).scalar_one_or_none()
            student_user = db.session.execute(
                db.select(User).where(User.email == student_email)
            ).scalar_one_or_none()
            professor_user = db.session.execute(
                db.select(User).where(User.email == professor_email)
            ).scalar_one_or_none()
            yarchenko_user = db.session.execute(
                db.select(User).where(User.email == yarchenko_email)
            ).scalar_one_or_none()

            if (
                group is not None
                and student_user is not None
                and professor_user is not None
                and yarchenko_user is not None
            ):
                sp = db.session.get(Student, student_user.id)
                pp = db.session.get(Professor, professor_user.id)
                if (
                    sp is not None
                    and pp is not None
                    and sp.group_id == group.id
                    and pp.group_id == group.id
                ):
                    click.echo("Demo data already present (nothing to do).")
                    click.echo(f"  group id={group.id} number={group.number}")
                    click.echo(f"  student user id={student_user.id} email={student_email}")
                    click.echo(f"  professor user id={professor_user.id} email={professor_email}")
                    click.echo(f"  yarchenko user id={yarchenko_user.id} email={yarchenko_email}")
                    click.echo(f"  password (unchanged): {demo_password}")
                    return

            if group is None:
                group = Group(number=demo_group_number, name=demo_group_name)
                db.session.add(group)
                db.session.flush()

            if student_user is None:
                student_user = User(
                    username="demo_student",
                    email=student_email,
                    role_id=student_role.id,
                )
                student_user.set_password(demo_password)
                db.session.add(student_user)
                db.session.flush()

            if professor_user is None:
                professor_user = User(
                    username="demo_professor",
                    email=professor_email,
                    role_id=professor_role.id,
                )
                professor_user.set_password(demo_password)
                db.session.add(professor_user)
                db.session.flush()

            if yarchenko_user is None:
                yarchenko_user = User(
                    username="yarchenko.da",
                    email=yarchenko_email,
                    fullname="Yarchenko DA",
                    role_id=student_role.id,
                )
                yarchenko_user.set_password(demo_password)
                db.session.add(yarchenko_user)
                db.session.flush()

            if db.session.get(Student, student_user.id) is None:
                db.session.add(Student(id=student_user.id, group_id=group.id))
            if db.session.get(Professor, professor_user.id) is None:
                db.session.add(Professor(id=professor_user.id, group_id=group.id))

            db.session.commit()

            gid = group.id
            gnum = group.number
            gname = group.name
            sid = student_user.id
            pid = professor_user.id
            yid = yarchenko_user.id

        click.echo("Demo data seeded.")
        click.echo(f"  group: id={gid} number={gnum} name={gname}")
        click.echo(f"  student: id={sid} username=demo_student email={student_email}")
        click.echo(f"  professor: id={pid} username=demo_professor email={professor_email}")
        click.echo(f"  yarchenko: id={yid} username=yarchenko.da email={yarchenko_email}")
        click.echo(f"  password for all demo users: {demo_password}")

def create_app(config_name="default"):
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    init_redis(app)
    register_blueprints(app)
    register_cli(app)

    # Загрузить публичный ключ для Arduino
    from app.api.v1.arduino import load_public_key
    load_public_key(app)

    swagger = Swagger(app=app, title='PulseCore')
    swagger.configure()

    return app

