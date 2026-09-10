import sqlite3
import os

db_path = "/home/ubuntu/motus.leap/db.sqlite"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT u.id, u.email, c.access_token, c.refresh_token, c.token_expiry FROM users u LEFT JOIN credentials c ON u.id = c.user_id")
for row in c.fetchall():
    d = dict(row)
    # Truncate tokens for security when printing
    if d.get("access_token"):
        d["access_token"] = d["access_token"][:15] + "..."
    if d.get("refresh_token"):
        d["refresh_token"] = d["refresh_token"][:15] + "..."
    print(d)
