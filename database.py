"""
database.py

Handles all SQLite database operations for SaveUp.
For Milestone 1, this class is only responsible for:
- Creating the database
- Opening the connection
- Creating required tables
"""

import sqlite3
from pathlib import Path

from config import DB_NAME


class Database:
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / DB_NAME
        self.connection = None

    def connect(self):
        """Open a connection to the SQLite database."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row

        return self.connection

    def initialize(self):
        """Create all required tables if they don't already exist."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                weekday INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL
            )
        """)

        conn.commit()

    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None

db = Database()