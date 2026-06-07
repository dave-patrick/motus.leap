import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "db.sqlite")
print(f"Connecting to {db_path}...")
c = sqlite3.connect(db_path)

tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

for t in tables:
    count = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"Table '{t}' count: {count}")
