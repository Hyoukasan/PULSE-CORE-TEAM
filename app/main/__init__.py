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
from sqlalchemy import event


def register_blueprints(app: Flask) -> None:
    from app.api import v1

    app.register_blueprint(v1.health.bp)
    app.register_blueprint(v1.auth.bp)
    app.register_blueprint(v1.attendance.bp)
    app.register_blueprint(v1.groups.bp)
    app.register_blueprint(v1.messages.bp)
    app.register_blueprint(v1.users.bp)
    app.register_blueprint(v1.bans.bp)
    app.register_blueprint(v1.arduino.bp)
    app.register_blueprint(v1.queue.bp)
    app.register_blueprint(v1.tasks.bp)
    app.register_blueprint(v1.google.bp)
    from app.api.v1.sync import bp as sync_bp
    app.register_blueprint(sync_bp)


def seed_roles() -> int:
    """Insert base roles if they do not exist."""
    from app.src.domain.role import Role

    base_roles = (
        "admin",
        "practitioner",
        "listener",
    )
    created_count = 0

    for role_name in base_roles:
        exists = db.session.execute(
            db.select(Role).where(Role.role == role_name)
        ).scalar_one_or_none()
        if exists is None:
            db.session.add(Role(role=role_name))
            created_count += 1

    db.session.commit()
    return created_count


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
    def cli_seed_roles() -> None:
        """Insert base roles if they do not exist."""
        created_count = seed_roles()
        click.echo(f"Roles seeded. Created: {created_count}, total expected: 3.")

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
            practitioner_role = db.session.execute(
                db.select(Role).where(Role.role == "practitioner")
            ).scalar_one_or_none()
            admin_role = db.session.execute(
                db.select(Role).where(Role.role == "admin")
            ).scalar_one_or_none()

            if practitioner_role is None or admin_role is None:
                click.echo("Missing required roles. Run `flask --app pulse_project seed-roles` first.")
                return

            student_user = User(
                username=f"smoke_practitioner_{suffix}",
                email=f"smoke_practitioner_{suffix}@local.test",
                role_id=practitioner_role.id,
            )
            student_user.set_password("smoke-pass")

            professor_user = User(
                username=f"smoke_admin_{suffix}",
                email=f"smoke_admin_{suffix}@local.test",
                role_id=admin_role.id,
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
            practitioner_role = db.session.execute(
                db.select(Role).where(Role.role == "practitioner")
            ).scalar_one_or_none()
            admin_role = db.session.execute(
                db.select(Role).where(Role.role == "admin")
            ).scalar_one_or_none()

            if practitioner_role is None or admin_role is None:
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
                    click.echo(f"  admin user id={professor_user.id} email={professor_email}")
                    click.echo(f"  yarchenko user id={yarchenko_user.id} email={yarchenko_email}")
                    click.echo(f"  password (unchanged): {demo_password}")
                    return

            if group is None:
                group = Group(number=demo_group_number, name=demo_group_name)
                db.session.add(group)
                db.session.flush()

            if student_user is None:
                student_user = User(
                    username="demo_practitioner",
                    email=student_email,
                    role_id=practitioner_role.id,
                )
                student_user.set_password(demo_password)
                db.session.add(student_user)
                db.session.flush()

            if professor_user is None:
                professor_user = User(
                    username="demo_admin",
                    email=professor_email,
                    role_id=admin_role.id,
                )
                professor_user.set_password(demo_password)
                db.session.add(professor_user)
                db.session.flush()

            if yarchenko_user is None:
                yarchenko_user = User(
                    username="yarchenko.da",
                    email=yarchenko_email,
                    fullname="Yarchenko DA",
                    role_id=practitioner_role.id,
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
        click.echo(f"  admin: id={pid} username=demo_admin email={professor_email}")
        click.echo(f"  yarchenko: id={yid} username=yarchenko.da email={yarchenko_email}")
        click.echo(f"  password for all demo users: {demo_password}")

def create_app(config_name="default"):
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    # If using SQLite, tune PRAGMA to reduce locking and allow concurrent readers/writers.
    try:
        if app.config.get("SQLALCHEMY_DATABASE_URI", "").startswith("sqlite"):
            engine = db.get_engine(app)

            @event.listens_for(engine, "connect")
            def _set_sqlite_pragmas(dbapi_connection, connection_record):
                try:
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA journal_mode=WAL;")
                    cursor.execute("PRAGMA synchronous=NORMAL;")
                    cursor.close()
                except Exception:
                    app.logger.exception("Failed to set SQLite PRAGMA settings")
    except Exception:
        app.logger.exception("Failed to initialize SQLite PRAGMAs")
    from app.src.integrations.db_hooks import register_db_listeners
    register_db_listeners(app)
    init_redis(app)
    register_blueprints(app)
    register_cli(app)

    with app.app_context():
        db.create_all()
        from app.src.integrations.schema_migrations import apply_sqlite_schema_patches
        apply_sqlite_schema_patches()
        seed_roles()

    # Загрузить публичный ключ для Arduino
    from app.api.v1.arduino import load_public_key
    load_public_key(app)

    swagger = Swagger(app=app, title='PulseCore')
    swagger.configure()

    # Start background DB export worker (posts snapshot to configured URL)
    try:
        from app.src.integrations.exporter import start_db_export_worker

        start_db_export_worker(app)
    except Exception:
        app.logger.exception("Failed to start DB export worker")
#''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
    import json
    from flask import request

    @app.after_request
    def inject_endpoint_params(response):
        # Работаем только со спецификацией Swagger
        if request.path.endswith('swagger.json') and response.content_type == 'application/json':
            try:
                spec = json.loads(response.get_data(as_text=True))

                # 1. Arduino: /api/v1/arduino/verify
                target_path = "/api/v1/arduino/verify"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "pass_key": {"type": "string", "description": "Ключ доступа устройства"},
                                        "sign": {"type": "string", "description": "Криптографическая подпись данных"}
                                    },
                                    "required": ["pass_key", "sign"]
                                }
                            }
                        }
                    }

                # 2. Attendance: /api/v1/attendance/excuse
                target_path = "/api/v1/attendance/excuse"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string", "description": "Email студента"},
                                        "reason": {"type": "string", "description": "Причина пропуска"},
                                        "file_url": {"type": "string", "description": "Ссылка на документ (опционально)"},
                                        "timestamp": {"type": "string", "description": "Временная метка (опционально)"}
                                    },
                                    "required": ["email", "reason"]
                                }
                            }
                        }
                    }

                # 3. Attendance: /api/v1/attendance/pass
                target_path = "/api/v1/attendance/pass"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "pass_id": {"type": "string", "description": "ID пропуска"}
                                    },
                                    "required": ["pass_id"]
                                }
                            }
                        }
                    }

                # 4. Auth: /api/v1/auth/login
                target_path = "/api/v1/auth/login"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string", "description": "Email пользователя"},
                                        "password": {"type": "string", "description": "Пароль"},
                                        "platform": {"type": "string", "description": "Платформа (опционально)"},
                                        "vk_id": {"type": "integer", "description": "VK ID (опционально)"}
                                    },
                                    "required": ["email", "password"]
                                }
                            }
                        }
                    }

                # 5. Auth: /api/v1/auth/verify
                target_path = "/api/v1/auth/verify"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string", "description": "Email для проверки роли"}
                                    },
                                    "required": ["email"]
                                }
                            }
                        }
                    }

                # 6. Auth: /api/v1/auth/bot
                target_path = "/api/v1/auth/bot"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string", "description": "Действие бота"},
                                        "mail": {"type": "string", "description": "Email"},
                                        "password": {"type": "string", "description": "Пароль"},
                                        "telegram_id": {"type": "integer", "description": "Telegram ID"},
                                        "vk_id": {"type": "integer", "description": "VK ID"},
                                        "fullname": {"type": "string", "description": "Полное имя"}
                                    },
                                    "required": ["action", "mail", "password"]
                                }
                            }
                        }
                    }

                # 7. Bans: /api/v1/bans/ban (POST)
                target_path = "/api/v1/bans/ban"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "from": {
                                            "type": "object",
                                            "description": "Идентификатор администратора",
                                            "properties": {
                                                "telegram_id": {"type": "integer"},
                                                "admin_id": {"type": "integer"}
                                            }
                                        },
                                        "target": {
                                            "type": "object",
                                            "description": "Идентификатор пользователя для бана",
                                            "properties": {
                                                "telegram_id": {"type": "integer"},
                                                "email": {"type": "string"}
                                            }
                                        },
                                        "permanent": {"type": "boolean", "description": "Постоянная блокировка"},
                                        "ban_expires_at": {"type": "string", "description": "Дата окончания бана (ISO 8601)"}
                                    },
                                    "required": ["from", "target"]
                                }
                            }
                        }
                    }

                # 8. Bans: /api/v1/bans/unban (POST)
                target_path = "/api/v1/bans/unban"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "from": {
                                            "type": "object",
                                            "description": "Идентификатор администратора",
                                            "properties": {
                                                "telegram_id": {"type": "integer"},
                                                "admin_id": {"type": "integer"}
                                            }
                                        },
                                        "target": {
                                            "type": "object",
                                            "description": "Идентификатор пользователя для разбана",
                                            "properties": {
                                                "telegram_id": {"type": "integer"},
                                                "email": {"type": "string"}
                                            }
                                        }
                                    },
                                    "required": ["from", "target"]
                                }
                            }
                        }
                    }

                # 9. Bans: /api/v1/bans (GET)
                target_path = "/api/v1/bans"
                if target_path in spec.get('paths', {}):
                    # Для GET-запросов параметры указываются в query, а не в requestBody
                    spec['paths'][target_path]['get']['parameters'] = [
                        {
                            "name": "admin_telegram_id",
                            "in": "query",
                            "description": "ID администратора в Telegram (для проверки прав)",
                            "schema": {"type": "integer"}
                        }
                    ]

                # 10. Google Sheets: /api/v1/google/in (POST)
                target_path = "/api/v1/google/in"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "rows": {
                                            "type": "array",
                                            "description": "Список строк для импорта",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "email": {"type": "string", "description": "Email студента"},
                                                    "fullname": {"type": "string", "description": "ФИО"},
                                                    "group_number": {"type": "string", "description": "Номер группы"},
                                                    "pass_id": {"type": "string", "description": "ID пропуска"},
                                                    "missed_passes": {"type": "integer", "description": "Количество пропусков"}
                                                }
                                            }
                                        }
                                    },
                                    "required": ["rows"]
                                }
                            }
                        }
                    }

                # 11. Google Sheets: /api/v1/google/in-attendance (POST)
                target_path = "/api/v1/google/in-attendance"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "rows": {
                                            "type": "array",
                                            "description": "Список записей посещаемости",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "email": {"type": "string", "description": "Email студента"},
                                                    "timestamp": {"type": "string", "description": "Временная метка (ISO 8601)"},
                                                    "attended": {"type": "boolean", "description": "Факт присутствия"}
                                                }
                                            }
                                        }
                                    },
                                    "required": ["rows"]
                                }
                            }
                        }
                    }

                # 12. Google Sheets: /api/v1/google/in-lecture-dates (POST)
                target_path = "/api/v1/google/in-lecture-dates"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "semester": {"type": "integer", "description": "Номер семестра (1 или 2)"},
                                        "dates": {"type": "array", "items": {"type": "string"}, "description": "Список дат лекций"}
                                    },
                                    "required": ["semester", "dates"]
                                }
                            }
                        }
                    }

                # 13. Google Sheets: /api/v1/google/out-lecture-dates (GET)
                target_path = "/api/v1/google/out-lecture-dates"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "semester", "in": "query", "required": True, "description": "Номер семестра (1 или 2)", "schema": {"type": "integer"}}
                    ]

                # 14. Google Sheets: /api/v1/google/in-lecture-attendance (POST)
                target_path = "/api/v1/google/in-lecture-attendance"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "semester": {"type": "integer", "description": "Номер семестра"},
                                        "rows": {
                                            "type": "array",
                                            "description": "Список посещений лекций",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "email": {"type": "string", "description": "Email студента"},
                                                    "date": {"type": "string", "description": "Дата лекции (YYYY-MM-DD)"},
                                                    "attended": {"type": "boolean", "description": "Присутствовал ли"}
                                                }
                                            }
                                        }
                                    },
                                    "required": ["semester", "rows"]
                                }
                            }
                        }
                    }

                # 15. Google Sheets: /api/v1/google/out-lecture-attendance (GET)
                target_path = "/api/v1/google/out-lecture-attendance"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "semester", "in": "query", "required": True, "description": "Номер семестра (1 или 2)", "schema": {"type": "integer"}}
                    ]

                # 16. Google Sheets: /api/v1/google/in-grades (POST)
                target_path = "/api/v1/google/in-grades"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "semester": {"type": "integer", "description": "Номер семестра"},
                                        "rows": {
                                            "type": "array",
                                            "description": "Список оценок",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "email": {"type": "string", "description": "Email студента"},
                                                    "subject": {"type": "string", "description": "Название предмета"},
                                                    "component": {"type": "string", "description": "Компонент оценки (напр. LR1)"},
                                                    "score": {"type": "integer", "description": "Балл за компонент"}
                                                }
                                            }
                                        }
                                    },
                                    "required": ["semester", "rows"]
                                }
                            }
                        }
                    }

                # 17. Google Sheets: /api/v1/google/out-grades (GET)
                target_path = "/api/v1/google/out-grades"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "semester", "in": "query", "required": True, "description": "Номер семестра (1 или 2)", "schema": {"type": "integer"}}
                    ]

                # 18. Google Sheets: /api/v1/google/out-grades-layout (GET)
                target_path = "/api/v1/google/out-grades-layout"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "semester", "in": "query", "required": True, "description": "Номер семестра (1 или 2)", "schema": {"type": "integer"}}
                    ]

                # 19. Groups: /api/v1/groups/assign (POST)
                target_path = "/api/v1/groups/assign"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "user_id": {"type": "integer", "description": "ID пользователя"},
                                        "group_number": {"type": "string", "description": "Номер группы"}
                                    },
                                    "required": ["user_id", "group_number"]
                                }
                            }
                        }
                    }

                # 20. Groups: /api/v1/groups/sync (POST)
                target_path = "/api/v1/groups/sync"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "rows": {
                                            "type": "array",
                                            "description": "Список групп для синхронизации",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "number": {"type": "string", "description": "Номер группы"},
                                                    "name": {"type": "string", "description": "Название группы"}
                                                },
                                                "required": ["number", "name"]
                                            }
                                        }
                                    },
                                    "required": ["rows"]
                                }
                            }
                        }
                    }

                # 21. Messages: /api/v1/messages/send (POST)
                target_path = "/api/v1/messages/send"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "from": {
                                            "type": "object",
                                            "description": "Данные отправителя",
                                            "properties": {
                                                "user_id": {"type": "integer"},
                                                "admin_id": {"type": "integer"},
                                                "role": {"type": "string"},
                                                "email": {"type": "string"},
                                                "fullname": {"type": "string"},
                                                "group": {"type": "string"},
                                                "platform": {"type": "string"},
                                                "telegram_id": {"type": "integer"},
                                                "vk_id": {"type": "integer"}
                                            }
                                        },
                                        "message": {
                                            "type": "object",
                                            "description": "Текст сообщения",
                                            "properties": {
                                                "type": {"type": "string"},
                                                "text": {"type": "string", "description": "Текст сообщения (обязательно)"},
                                                "timestamp": {"type": "string"}
                                            },
                                            "required": ["text"]
                                        },
                                        "to_user_id": {"type": "integer", "description": "ID получателя"},
                                        "to_telegram_id": {"type": "integer", "description": "Telegram ID получателя"},
                                        "to_vk_id": {"type": "integer", "description": "VK ID получателя"},
                                        "to_group_number": {"type": "string", "description": "Номер группы для рассылки"},
                                        # Flat bot payload (альтернативный формат)
                                        "telegram_id": {"type": "integer", "description": "Telegram ID бота (если нет from)"},
                                        "vk_id": {"type": "integer", "description": "VK ID бота (если нет from)"},
                                        "type": {"type": "string", "description": "Тип сообщения (если message не объект)"},
                                        "text": {"type": "string", "description": "Текст сообщения (если message не объект)"}
                                    },
                                    "required": ["message"]
                                }
                            }
                        }
                    }

                # 22. Messages: /api/v1/messages (GET)
                target_path = "/api/v1/messages"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "telegram_id", "in": "query", "description": "Telegram ID для получения сообщений", "schema": {"type": "integer"}},
                        {"name": "vk_id", "in": "query", "description": "VK ID для получения сообщений", "schema": {"type": "integer"}}
                    ]

                # 23. Messages: /api/v1/messages/broadcast/poll (GET)
                target_path = "/api/v1/messages/broadcast/poll"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "platform", "in": "query", "required": True, "description": "Платформа: telegram или vk", "schema": {"type": "string", "enum": ["telegram", "vk"]}}
                    ]

                # 24. Messages: /api/v1/messages/{user_id} (GET)
                target_path = "/api/v1/messages/{user_id}"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "user_id", "in": "path", "required": True, "description": "ID пользователя или бота", "schema": {"type": "integer"}}
                    ]

                # 25. Messages: /api/v1/messages/groups/{group_id}/students (GET)
                target_path = "/api/v1/messages/groups/{group_id}/students"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "group_id", "in": "path", "required": True, "description": "ID группы", "schema": {"type": "integer"}}
                    ]

                # 26. Queue: /api/v1/queue/add (POST)
                target_path = "/api/v1/queue/add"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        # Direct payload
                                        "student_id": {"type": "integer", "description": "ID студента"},
                                        "professor_id": {"type": "integer", "description": "ID преподавателя"},
                                        # Bot payload
                                        "telegram_id": {"type": "integer", "description": "Telegram ID бота"},
                                        "vk_id": {"type": "integer", "description": "VK ID бота"},
                                        # Общие поля
                                        "lesson_date": {"type": "string", "description": "Дата занятия (ISO 8601)"},
                                        "labs_count": {"type": "integer", "description": "Количество лабораторных"}
                                    },
                                    "oneOf": [
                                        {"required": ["student_id", "professor_id", "lesson_date"]},
                                        {"required": ["telegram_id", "lesson_date"]},
                                        {"required": ["vk_id", "lesson_date"]}
                                    ]
                                }
                            }
                        }
                    }

                # 27. Queue: /api/v1/queue/remove (POST)
                target_path = "/api/v1/queue/remove"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        # Direct payload
                                        "student_id": {"type": "integer", "description": "ID студента"},
                                        "professor_id": {"type": "integer", "description": "ID преподавателя"},
                                        # Bot payload
                                        "telegram_id": {"type": "integer", "description": "Telegram ID бота"},
                                        "vk_id": {"type": "integer", "description": "VK ID бота"},
                                        # Общее поле
                                        "lesson_date": {"type": "string", "description": "Дата занятия (ISO 8601)"}
                                    },
                                    "oneOf": [
                                        {"required": ["student_id", "professor_id", "lesson_date"]},
                                        {"required": ["telegram_id", "lesson_date"]},
                                        {"required": ["vk_id", "lesson_date"]}
                                    ]
                                }
                            }
                        }
                    }

                # 28. Queue: /api/v1/queue/position (POST)
                target_path = "/api/v1/queue/position"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        # Direct payload
                                        "student_id": {"type": "integer", "description": "ID студента"},
                                        "professor_id": {"type": "integer", "description": "ID преподавателя"},
                                        # Bot payload
                                        "telegram_id": {"type": "integer", "description": "Telegram ID бота"},
                                        "vk_id": {"type": "integer", "description": "VK ID бота"},
                                        # Общее поле
                                        "lesson_date": {"type": "string", "description": "Дата занятия (ISO 8601)"}
                                    },
                                    "oneOf": [
                                        {"required": ["student_id", "professor_id", "lesson_date"]},
                                        {"required": ["telegram_id", "lesson_date"]},
                                        {"required": ["vk_id", "lesson_date"]}
                                    ]
                                }
                            }
                        }
                    }

                # 29. Queue: /api/v1/queue/lesson/{lesson_date} (GET)
                target_path = "/api/v1/queue/lesson/{lesson_date}"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "lesson_date", "in": "path", "required": True, "description": "Дата занятия (строка)", "schema": {"type": "string"}}
                    ]

                # 30. Queue: /api/v1/queue/lesson/{professor_id}/{lesson_date} (GET)
                target_path = "/api/v1/queue/lesson/{professor_id}/{lesson_date}"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "professor_id", "in": "path", "required": True, "description": "ID преподавателя", "schema": {"type": "integer"}},
                        {"name": "lesson_date", "in": "path", "required": True, "description": "Дата занятия (строка)", "schema": {"type": "string"}}
                    ]

                # 31. Sync: /sync/ban (POST)
                target_path = "/sync/ban"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "students": {
                                            "type": "array",
                                            "description": "Список студентов для обновления статуса бана",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "email": {"type": "string", "description": "Email студента"},
                                                    "ban": {"type": "boolean", "description": "true = забанить, false = разбанить"},
                                                    "ban_expires_at": {"type": "string", "description": "Дата окончания бана (ISO 8601, опционально)"}
                                                },
                                                "required": ["email", "ban"]
                                            }
                                        }
                                    },
                                    "required": ["students"]
                                }
                            }
                        }
                    }

                # 32. Sync: /sync/attendance (POST)
                target_path = "/sync/attendance"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "students": {
                                            "type": "array",
                                            "description": "Список записей посещаемости",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "email": {"type": "string", "description": "Email студента"},
                                                    "date": {"type": "string", "description": "Дата (формат: ГГГГ-ММ-ДД)"},
                                                    "status": {"type": "string", "enum": ["present", "absent"], "description": "Статус присутствия"}
                                                },
                                                "required": ["email", "date", "status"]
                                            }
                                        }
                                    },
                                    "required": ["students"]
                                }
                            }
                        }
                    }

                # 33. Sync: /sync/lecture-dates (POST)
                target_path = "/sync/lecture-dates"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "semester": {"type": "integer", "description": "Номер семестра (1 или 2)"},
                                        "dates": {"type": "array", "items": {"type": "string"}, "description": "Список дат лекций"}
                                    },
                                    "required": ["semester", "dates"]
                                }
                            }
                        }
                    }

                # 34. Sync: /sync/lecture-attendance (POST)
                target_path = "/sync/lecture-attendance"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "semester": {"type": "integer", "description": "Номер семестра"},
                                        "students": {
                                            "type": "array",
                                            "description": "Список посещений лекций",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "email": {"type": "string", "description": "Email студента"},
                                                    "date": {"type": "string", "description": "Дата лекции"},
                                                    "status": {"type": "string", "description": "Статус (present/absent)"}
                                                }
                                            }
                                        }
                                    },
                                    "required": ["semester", "students"]
                                }
                            }
                        }
                    }

                # 35. Sync: /sync/grades (POST)
                target_path = "/sync/grades"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "semester": {"type": "integer", "description": "Номер семестра"},
                                        "rows": {
                                            "type": "array",
                                            "description": "Список оценок",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "email": {"type": "string", "description": "Email студента"},
                                                    "subject": {"type": "string", "description": "Название предмета"},
                                                    "component": {"type": "string", "description": "Компонент (напр. LR1)"},
                                                    "score": {"type": "integer", "description": "Балл"}
                                                }
                                            }
                                        }
                                    },
                                    "required": ["semester", "rows"]
                                }
                            }
                        }
                    }

                # 36. Tasks: /api/v1/tasks/create (POST)
                target_path = "/api/v1/tasks/create"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "group_id": {"type": "integer", "description": "ID группы"},
                                        "title": {"type": "string", "description": "Название задания"},
                                        "description": {"type": "string", "description": "Описание задания"},
                                        "file_url": {"type": "string", "description": "Ссылка на файл задания"},
                                        "due_date": {"type": "string", "description": "Дедлайн (ISO 8601)"}
                                    },
                                    "required": ["group_id", "title"]
                                }
                            }
                        }
                    }

                # 37. Tasks: /api/v1/tasks/list (GET)
                target_path = "/api/v1/tasks/list"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "telegram_id", "in": "query", "description": "Telegram ID студента", "schema": {"type": "integer"}},
                        {"name": "vk_id", "in": "query", "description": "VK ID студента", "schema": {"type": "integer"}}
                    ]

                # 38. Tasks: /api/v1/tasks/{task_id}/submit (POST)
                target_path = "/api/v1/tasks/{task_id}/submit"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['parameters'] = [
                        {"name": "task_id", "in": "path", "required": True, "description": "ID задания", "schema": {"type": "integer"}}
                    ]
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "telegram_id": {"type": "integer", "description": "Telegram ID студента"},
                                        "vk_id": {"type": "integer", "description": "VK ID студента"},
                                        "response_text": {"type": "string", "description": "Текст ответа"},
                                        "file_url": {"type": "string", "description": "Ссылка на файл с решением"}
                                    }
                                }
                            }
                        }
                    }

                # 39. Tasks: /api/v1/tasks/{task_id}/responses (GET)
                target_path = "/api/v1/tasks/{task_id}/responses"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "task_id", "in": "path", "required": True, "description": "ID задания", "schema": {"type": "integer"}}
                    ]

                # 40. Users: /api/v1/users/register (POST)
                target_path = "/api/v1/users/register"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string", "description": "Имя пользователя"},
                                        "email": {"type": "string", "description": "Email (университетский)"},
                                        "password": {"type": "string", "description": "Пароль (мин. 8 символов)"},
                                        "role": {"type": "string", "description": "Роль: practitioner или listener", "default": "practitioner"},
                                        "fullname": {"type": "string", "description": "Полное имя (опционально)"}
                                    },
                                    "required": ["username", "email", "password"]
                                }
                            }
                        }
                    }

                # 41. Users: /api/v1/users/{user_id} (GET)
                target_path = "/api/v1/users/{user_id}"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['get']['parameters'] = [
                        {"name": "user_id", "in": "path", "required": True, "description": "ID пользователя", "schema": {"type": "integer"}}
                    ]

                # 42. Users: /api/v1/users/ban (POST)
                target_path = "/api/v1/users/ban"
                if target_path in spec.get('paths', {}):
                    spec['paths'][target_path]['post']['requestBody'] = {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        # Идентификатор администратора (один из трёх)
                                        "admin_id": {"type": "integer", "description": "ID администратора"},
                                        "admin_telegram_id": {"type": "integer", "description": "Telegram ID администратора"},
                                        "admin_vk_id": {"type": "integer", "description": "VK ID администратора"},
                                        # Идентификатор целевого пользователя (один из четырёх)
                                        "user_id": {"type": "integer", "description": "ID пользователя для бана"},
                                        "target_user_id": {"type": "integer", "description": "Альтернативный ID пользователя"},
                                        "target_telegram_id": {"type": "integer", "description": "Telegram ID пользователя"},
                                        "target_vk_id": {"type": "integer", "description": "VK ID пользователя"},
                                        # Параметры бана
                                        "ban_expires_at": {"type": "string", "description": "Дата окончания бана (ISO 8601) или null для разбана"},
                                        "permanent": {"type": "boolean", "description": "Постоянный бан (игнорирует ban_expires_at)"}
                                    },
                                    "oneOf": [
                                        {"required": ["admin_id", "user_id"]},
                                        {"required": ["admin_telegram_id", "target_telegram_id"]},
                                        {"required": ["admin_vk_id", "target_vk_id"]}
                                    ]
                                }
                            }
                        }
                    }

                response.set_data(json.dumps(spec, ensure_ascii=False))
            except Exception:
                pass  # Не ломаем ответ, если что-то пошло не так

        return response
    # ============================================
    return app