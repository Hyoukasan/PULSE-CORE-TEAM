from app.main import create_app
import sqlite3

app = create_app()
ctx = app.app_context()
ctx.push()

conn = sqlite3.connect('instance/pulse_project.db')
c = conn.cursor()
c.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = c.fetchall()

print("Database tables:")
for t in tables:
    print(f"  - {t[0]}")

# Check if approach_queues exists
c.execute("PRAGMA table_info(approach_queues)")
columns = c.fetchall()
if columns:
    print("\napproach_queues table columns:")
    for col in columns:
        print(f"  - {col[1]}: {col[2]}")
else:
    print("\nERROR: approach_queues table not found!")

conn.close()
