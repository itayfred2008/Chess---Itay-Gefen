import sqlite3
import hashlib
import os
import re
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
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _generate_salt() -> str:
    return os.urandom(16).hex()


def _hash_password_with_salt(password: str, salt_hex: str) -> str:
    salt_bytes = bytes.fromhex(salt_hex)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        100_000
    )
    return pwd_hash.hex()


def _validate_password_strength(password: str) -> Tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r"\d", password):
        return False, "Password must include at least one digit."
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must include at least one special character."
    return True, "ok"


def signup(username: str, password: str) -> Tuple[bool, str]:
    username = username.strip().lower()

    if not username:
        return False, "Username cannot be empty."
    if not password:
        return False, "Password cannot be empty."

    ok, msg = _validate_password_strength(password)
    if not ok:
        return False, msg

    salt = _generate_salt()
    password_hash = _hash_password_with_salt(password, salt)

    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_salt, password_hash) VALUES (?, ?, ?)",
            (username, salt, password_hash)
        )
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()


def login(username: str, password: str) -> Tuple[bool, str]:
    username = username.strip().lower()
    if not username or not password:
        return False, "Please enter username and password."

    conn = _get_connection()
    cur = conn.execute(
        "SELECT username, password_salt, password_hash FROM users WHERE username = ?",
        (username,)
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return False, "Username or password incorrect."

    expected_hash = row["password_hash"]
    salt = row["password_salt"]
    actual_hash = _hash_password_with_salt(password, salt)

    if actual_hash == expected_hash:
        return True, row["username"]

    return False, "Username or password incorrect."