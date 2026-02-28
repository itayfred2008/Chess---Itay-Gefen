# database.py
import sqlite3
import hashlib
import os
from typing import Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "chess_users.db")


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create users table if it doesn't exist."""
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def signup(username: str, password: str) -> Tuple[bool, str]:
    """
    Register a new user. Returns (success, message).
    Message is error description on failure.
    """
    username = username.strip()
    if not username:
        return False, "Username cannot be empty."
    if not password:
        return False, "Password cannot be empty."

    password_hash = _hash_password(password)
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash)
        )
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()


def login(username: str, password: str) -> Tuple[bool, str]:
    """
    Verify credentials. Returns (success, message).
    On success, message is the username. On failure, error description.
    """
    username = username.strip()
    if not username or not password:
        return False, "Please enter username and password."

    password_hash = _hash_password(password)
    conn = _get_connection()
    cur = conn.execute(
        "SELECT username FROM users WHERE username = ? AND password_hash = ?",
        (username, password_hash)
    )
    row = cur.fetchone()
    conn.close()

    if row:
        return True, row["username"]
    return False, "Username or password incorrect."
