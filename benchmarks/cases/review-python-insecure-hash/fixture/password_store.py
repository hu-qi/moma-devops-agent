import hashlib
import sqlite3


DB_PATH = "users.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS credentials "
        "(username TEXT PRIMARY KEY, password_hash TEXT)"
    )
    return conn


def hash_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()


def register(username: str, password: str) -> None:
    conn = _get_connection()
    pw_hash = hash_password(password)
    conn.execute(
        "INSERT INTO credentials (username, password_hash) VALUES (?, ?)",
        (username, pw_hash),
    )
    conn.commit()
    conn.close()


def verify(username: str, password: str) -> bool:
    conn = _get_connection()
    row = conn.execute(
        "SELECT password_hash FROM credentials WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    if row is None:
        return False
    return row[0] == hash_password(password)
