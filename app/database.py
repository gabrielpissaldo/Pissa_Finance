import sqlite3
from pathlib import Path


DATABASE_PATH = Path("/app/data/pissa_finance.db")


def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

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
            investment_id INTEGER,
            transaction_date TEXT NOT NULL,
            created_at TEXT NOT NULL
    )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL NOT NULL DEFAULT 0,
            deadline TEXT,
            created_at TEXT NOT NULL
    )                   
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS investments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            investment_type TEXT NOT NULL,
            amount_invested REAL NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    connection.execute("""
    CREATE TABLE IF NOT EXISTS fixed_income_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        investment_id INTEGER NOT NULL UNIQUE,
        rate_type TEXT NOT NULL,
        rate_modifier REAL,
        fixed_rate REAL,
        maturity_date TEXT,
        FOREIGN KEY (investment_id)
            REFERENCES investments(id)
            ON DELETE CASCADE
        )
    """)
    connection.execute("""
    CREATE TABLE IF NOT EXISTS market_investment_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        investment_id INTEGER NOT NULL UNIQUE,
        asset_type TEXT,
        symbol TEXT,
        quantity REAL,
        average_price REAL,
        FOREIGN KEY (investment_id)
            REFERENCES investments(id)
            ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()