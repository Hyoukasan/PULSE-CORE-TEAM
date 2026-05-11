#!/usr/bin/env python
"""Initialize the database with all tables and seed roles - clean approach."""

import os
import shutil
import tempfile

# Path
db_path = "instance/pulse_project.db"
db_backup = "instance/pulse_project.db.backup"

# Backup old DB
if os.path.exists(db_path):
    try:
        if os.path.exists(db_backup):
            os.remove(db_backup)
        shutil.copy(db_path, db_backup)
        print(f"✓ Backed up old database to {db_backup}")
    except Exception as e:
        print(f"⚠ Warning: Could not backup old DB: {e}")

# Create app and init DB
from app.main import create_app
from app.src.integrations.db import db
from app.src.domain.role import Role

print("Creating Flask app...")
app = create_app()

print("Initializing database...")
with app.app_context():
    try:
        # Drop old tables first
        print("Dropping existing tables...")
        db.drop_all()
        
        # Create new tables
        print("Creating all tables...")
        db.create_all()
        print("✓ Tables created")
        
        # Seed roles
        print("Seeding roles...")
        base_roles = (
            "admin",
            "student",
            "student_lecture",
            "practitioner",
            "listener",
            "professor",
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
        print(f"✓ Roles seeded. Created: {created_count}, total expected: {len(base_roles)}")
        print("\n✓ Database initialization complete!")
    except Exception as e:
        print(f"✗ Error: {e}")
        raise
    finally:
        db.session.remove()
