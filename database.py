import sqlite3
import json
from datetime import datetime

def init_db():
    conn = sqlite3.connect("savemate.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL,
            type TEXT,
            description TEXT,
            date TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            target_amount REAL,
            reached INTEGER DEFAULT 0,
            created_date TEXT
        )
    """)
    conn.commit()
    return conn

conn = None

def set_global_conn(c):
    global conn
    conn = c

def get_total_savings():
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM history")
    res = cursor.fetchone()[0]
    return res if res is not None else 0.0

def get_history():
    cursor = conn.cursor()
    cursor.execute("SELECT amount, type, description, date FROM history ORDER BY id DESC")
    return cursor.fetchall()

def get_setting(key, default=""):
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    return res[0] if res else default

def save_setting(key, value):
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()

def get_goals():
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, target_amount, reached, created_date FROM goals ORDER BY id DESC")
    return cursor.fetchall()

def add_goal_to_db(name, target_amount):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO goals (name, target_amount, reached, created_date) VALUES (?, ?, 0, ?)",
        (name, target_amount, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()

def delete_goal_from_db(goal_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM goals WHERE id=?", (goal_id,))
    conn.commit()

def mark_goal_reached(goal_id):
    cursor = conn.cursor()
    cursor.execute("UPDATE goals SET reached=1 WHERE id=?", (goal_id,))
    conn.commit()

def log_goal_completion_to_history(name, target_amount):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO history (amount, type, description, date) VALUES (?, 'Goal Achieved', ?, ?)",
        (0, f"🏁 Achieved goal: {name} (₱{target_amount:,.2f})", datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()