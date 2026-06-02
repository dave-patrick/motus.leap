import sqlite3
import os

COOKIES_DB_PATH = os.path.abspath("user_data/Default/Network/Cookies")
conn = sqlite3.connect(COOKIES_DB_PATH)
cursor = conn.cursor()
try:
    cursor.execute("SELECT host_key, name, encrypted_value FROM cookies LIMIT 5")
except:
    cursor.execute("SELECT host, name, encrypted_value FROM cookies LIMIT 5")

for r in cursor.fetchall():
    print(r[0], r[1], type(r[2]), r[2][:20])
conn.close()
