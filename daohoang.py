# daohoang.py — SQLite + các hàm dữ liệu
import sqlite3
import datetime

DB_PATH = "database.db"

# ========= DB =========
def _conn():
    return sqlite3.connect(DB_PATH)

def setup_database():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER PRIMARY KEY,
        username   TEXT,
        gold       INTEGER DEFAULT 0,
        last_daily TEXT
    )
    """)
    conn.commit()
    conn.close()

def ensure_user(user_id: int, username: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, gold) VALUES (?, ?, ?)", (user_id, username, 0))
    # luôn cập nhật username mới nhất
    cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()
    conn.close()

def get_gold(user_id: int) -> int:
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT gold FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else 0

def add_gold(user_id: int, delta: int):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (delta, user_id))
    conn.commit()
    conn.close()

def set_daily_today(user_id: int):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (datetime.date.today().isoformat(), user_id))
    conn.commit()
    conn.close()

def can_daily(user_id: int) -> bool:
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return True
    return row[0] != datetime.date.today().isoformat()

def top_rich(limit: int = 10):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT username, gold FROM users ORDER BY gold DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

# ========= Tiện ích định dạng / parse =========
def parse_amount(text: str) -> int | None:
    """
    Nhận chuỗi như: '1.234.567' hoặc '1,234,567' hoặc '1234567' -> int dương.
    Trả về None nếu không hợp lệ.
    """
    if not isinstance(text, str):
        return None
    clean = text.replace(".", "").replace(",", "").strip()
    if not clean.isdigit():
        return None
    val = int(clean)
    return val if val > 0 else None

def fmt_vn(n: int) -> str:
    """
    Định dạng số theo kiểu VN: 1.234.567
    """
    s = f"{n:,}"
    return s.replace(",", ".")
