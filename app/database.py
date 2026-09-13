import sqlite3
from pathlib import Path


DATABASE_PATH = Path("/app/data/pissa_finance.db")


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def init_db():
    connection = get_connection()

    connection.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        type TEXT NOT NULL,
        category TEXT,
        transaction_date TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
""")

    connection.commit()
    connection.close()