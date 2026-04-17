import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    password TEXT
)""")

c.execute("""CREATE TABLE IF NOT EXISTS ratings (
    user_id INTEGER,
    movie TEXT,
    rating INTEGER
)""")

c.execute("""CREATE TABLE IF NOT EXISTS likes (
    user_id INTEGER,
    movie TEXT
)""")

conn.commit()
conn.close()