# daohoang.py — SQLite + dữ liệu + logic shop/inv + cấu hình server
import sqlite3
import datetime
from typing import Optional, List, Tuple

DB_PATH = "database.db"

SHOP_ITEMS = {
    # item: (price, description)
    "cuocgo":       (10,  "Cuốc gỗ sờn sờn."),
    "cuocsat":      (20,  "Cuốc sắt chắc chắn."),
    "cuocvang":     (50,  "Cuốc vàng sáng chói."),
    "cuockimcuong": (100, "Cuốc kim cương xịn."),
    "khien":        (200, "Khiên bảo hộ 100% 1 lần.")
}

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def setup_database():
    conn = _conn()
    cur = conn.cursor()
    # users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id     INTEGER PRIMARY KEY,
        username    TEXT,
        gold        INTEGER DEFAULT 0,
        level       INTEGER DEFAULT 1,
        exp         INTEGER DEFAULT 0,
        last_daily  TEXT,
        banned      INTEGER DEFAULT 0,
        is_admin    INTEGER DEFAULT 0
    )
    """)
    # inventory
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        user_id INTEGER,
        item    TEXT,
        qty     INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, item),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)
    # server config (single row)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS config (
        id                 INTEGER PRIMARY KEY CHECK (id = 1),
        allowed_channel_id INTEGER,
        death_rate_percent INTEGER DEFAULT 35
    )
    """)
    cur.execute("INSERT OR IGNORE INTO config (id, allowed_channel_id, death_rate_percent) VALUES (1, NULL, 35)")
    conn.commit()
    conn.close()

def ensure_user(user_id: int, username: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, gold) VALUES (?, ?, 0)", (user_id, username))
    cur.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()
    conn.close()

def is_banned(user_id: int) -> bool:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone(); conn.close()
    return bool(row and row[0])

def is_admin(user_id: int) -> bool:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone(); conn.close()
    return bool(row and row[0])

def set_admin(user_id: int, on: bool):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (1 if on else 0, user_id))
    conn.commit(); conn.close()

def ban_user(user_id: int, on: bool):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET banned = ? WHERE user_id = ?", (1 if on else 0, user_id))
    conn.commit(); conn.close()

def reset_user(user_id: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET gold=0, level=1, exp=0, last_daily=NULL, banned=0 WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM inventory WHERE user_id = ?", (user_id,))
    conn.commit(); conn.close()

def get_gold(user_id: int) -> int:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT gold FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone(); conn.close()
    return int(row[0]) if row else 0

def add_gold(user_id: int, delta: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (delta, user_id))
    conn.commit(); conn.close()

def set_level(user_id: int, level: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET level = ? WHERE user_id = ?", (level, user_id))
    conn.commit(); conn.close()

def add_exp(user_id: int, add: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT level, exp FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close(); return
    level, exp = int(row[0]), int(row[1]) + add
    # exp cần để lên level: 100 * level (đơn giản, tránh lạm phát)
    need = 100 * level
    while exp >= need:
        exp -= need
        level += 1
        need = 100 * level
    cur.execute("UPDATE users SET level=?, exp=? WHERE user_id=?", (level, exp, user_id))
    conn.commit(); conn.close()

def set_daily_today(user_id: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (datetime.date.today().isoformat(), user_id))
    conn.commit(); conn.close()

def can_daily(user_id: int) -> bool:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT last_daily FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone(); conn.close()
    if not row or not row[0]:
        return True
    return row[0] != datetime.date.today().isoformat()

def top_rich(limit: int = 10) -> List[Tuple[str, int]]:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT username, gold FROM users ORDER BY gold DESC LIMIT ?", (limit,))
    rows = cur.fetchall(); conn.close()
    return rows

# inventory
def get_inv(user_id: int) -> List[Tuple[str, int]]:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT item, qty FROM inventory WHERE user_id = ? ORDER BY item", (user_id,))
    rows = cur.fetchall(); conn.close()
    return rows

def add_item(user_id: int, item: str, qty: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("INSERT INTO inventory(user_id, item, qty) VALUES (?, ?, ?) ON CONFLICT(user_id, item) DO UPDATE SET qty = qty + excluded.qty",
                (user_id, item, qty))
    conn.commit(); conn.close()

def use_item(user_id: int, item: str, qty: int = 1) -> bool:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT qty FROM inventory WHERE user_id=? AND item=?", (user_id, item))
    row = cur.fetchone()
    if not row or row[0] < qty:
        conn.close(); return False
    cur.execute("UPDATE inventory SET qty = qty - ? WHERE user_id=? AND item=?", (qty, user_id, item))
    cur.execute("DELETE FROM inventory WHERE user_id=? AND item=? AND qty<=0", (user_id, item))
    conn.commit(); conn.close(); return True

# shop
def list_shop() -> List[Tuple[str, int, str]]:
    return [(name, SHOP_ITEMS[name][0], SHOP_ITEMS[name][1]) for name in SHOP_ITEMS.keys()]

def buy(user_id: int, item: str, qty: int) -> Optional[str]:
    if item not in SHOP_ITEMS:
        return "❌ Vật phẩm không tồn tại."
    price = SHOP_ITEMS[item][0] * qty
    g = get_gold(user_id)
    if g < price:
        return f"❌ Không đủ vàng. Cần {price}, bạn có {g}."
    add_gold(user_id, -price)
    add_item(user_id, item, qty)
    return f"🛒 Đã mua {qty} **{item}** với giá {price} vàng."

# server config
def get_allowed_channel_id() -> Optional[int]:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT allowed_channel_id FROM config WHERE id=1")
    row = cur.fetchone(); conn.close()
    return int(row[0]) if row and row[0] is not None else None

def set_allowed_channel_id(ch_id: Optional[int]):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE config SET allowed_channel_id = ? WHERE id=1", (ch_id,))
    conn.commit(); conn.close()

def get_death_rate() -> int:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT death_rate_percent FROM config WHERE id=1")
    row = cur.fetchone(); conn.close()
    return int(row[0]) if row else 35

def set_death_rate(p: int):
    p = max(0, min(100, p))
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE config SET death_rate_percent = ? WHERE id=1", (p,))
    conn.commit(); conn.close()

# --- parse số (chỉ số thuần, không dấu) ---
def parse_amount(text: str) -> int | None:
    if not isinstance(text, str): return None
    s = text.strip()
    if not s.isdigit(): return None
    val = int(s)
    return val if val > 0 else None
