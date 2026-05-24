#!/usr/bin/env python
"""Initialize the database with all tables and seed roles."""

import os
import sys

# Remove old DB file first
db_path = "instance/pulse_project.db"
if os.path.exists(db_path):
    try:
        os.remove(db_path)
        print(f"✓ Old database file removed")
    except Exception as e:
        print(f"⚠ Could not remove old DB: {e}")
        sys.exit(1)

from app.main import create_app
from app.src.integrations.db import db
from app.src.domain.role import Role

app = create_app()

try:
    with app.app_context():
        print("Creating all tables...")
        db.create_all()
        print("✓ Tables created")
        
        print("Seeding roles...")
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
        print(f"✓ Roles seeded. Created: {created_count}, total expected: {len(base_roles)}")
        print("\n✓ Database initialization complete!")
finally:
    db.session.remove()
