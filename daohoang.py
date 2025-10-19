# daohoang.py — SQLite + data + shop + buffs + server config
import sqlite3, time, datetime
from typing import Optional, List, Tuple, Dict

DB_PATH = "database.db"

# ---- SHOP ----
SHOP_ITEMS: Dict[str, Tuple[int, str]] = {
    "cuocgo":       (10,  "Cuốc gỗ (+1 coin/farm, cộng dồn)"),
    "cuocsat":      (20,  "Cuốc sắt (+2 coin/farm, cộng dồn)"),
    "cuocvang":     (50,  "Cuốc vàng (+5 coin/farm, cộng dồn)"),
    "cuockimcuong": (100, "Cuốc kim cương (+10 coin/farm, cộng dồn)"),
    "khien":        (200, "Khiên chặn chết 100% 1 lần (tiêu hao)"),
    "khien_vip":    (500, "Khiên VIP chặn chết 100% 5 lần (tiêu hao)"),
    # Thuốc mới (2 phút)
    "thuoc_x2":       (500,  "X2 vàng nhận trong 2 phút"),
    "thuoc_giamchet": (1000, "Giảm 50% tỉ lệ chết trong 2 phút"),
}

BUFF_DUR_SEC = 120  # 2 phút

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def setup_database():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id       INTEGER PRIMARY KEY,
        username      TEXT,
        gold          INTEGER DEFAULT 0,
        level         INTEGER DEFAULT 1,
        exp           INTEGER DEFAULT 0,
        last_daily    TEXT,
        banned        INTEGER DEFAULT 0,
        is_admin      INTEGER DEFAULT 0,
        can_spam      INTEGER DEFAULT 0,
        last_farm_ts  INTEGER DEFAULT 0
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        user_id INTEGER,
        item    TEXT,
        qty     INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, item),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS buffs (
        user_id    INTEGER,
        buff_name  TEXT,
        expires_at INTEGER,
        PRIMARY KEY (user_id, buff_name),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS config (
        id                   INTEGER PRIMARY KEY CHECK (id = 1),
        allowed_channel_id   INTEGER,
        death_rate_percent   INTEGER DEFAULT 35
    )
    """)
    cur.execute("INSERT OR IGNORE INTO config (id, allowed_channel_id, death_rate_percent) VALUES (1, NULL, 35)")
    conn.commit(); conn.close()

# ---- USERS ----
def ensure_user(uid: int, username: str):
    conn = _conn(); cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (uid, username))
    cur.execute("UPDATE users SET username=? WHERE user_id=?", (username, uid))
    conn.commit(); conn.close()

def is_banned(uid: int) -> bool:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT banned FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); conn.close()
    return bool(row and row[0])

def is_admin(uid: int) -> bool:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); conn.close()
    return bool(row and row[0])

def set_admin(uid: int, on: bool):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin=? WHERE user_id=?", (1 if on else 0, uid))
    conn.commit(); conn.close()

def set_ban(uid: int, on: bool):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if on else 0, uid))
    conn.commit(); conn.close()

def reset_user(uid: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET gold=0, level=1, exp=0, last_daily=NULL, banned=0, can_spam=0, last_farm_ts=0 WHERE user_id=?", (uid,))
    cur.execute("DELETE FROM inventory WHERE user_id=?", (uid,))
    cur.execute("DELETE FROM buffs WHERE user_id=?", (uid,))
    conn.commit(); conn.close()

def get_gold(uid: int) -> int:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT gold FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); conn.close()
    return int(row[0]) if row else 0

def add_gold(uid: int, delta: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET gold = gold + ? WHERE user_id=?", (delta, uid))
    conn.commit(); conn.close()

def set_level(uid: int, level: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET level=? WHERE user_id=?", (level, uid))
    conn.commit(); conn.close()

def add_exp(uid: int, add: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT level, exp FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    if not row: conn.close(); return
    level, exp = int(row[0]), int(row[1]) + max(0, add)
    need = 100 * level
    while exp >= need:
        exp -= need
        level += 1
        need = 100 * level
    cur.execute("UPDATE users SET level=?, exp=? WHERE user_id=?", (level, exp, uid))
    conn.commit(); conn.close()

def set_daily_today(uid: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET last_daily=? WHERE user_id=?", (datetime.date.today().isoformat(), uid))
    conn.commit(); conn.close()

def can_daily(uid: int) -> bool:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT last_daily FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); conn.close()
    if not row or not row[0]: return True
    return row[0] != datetime.date.today().isoformat()

def set_can_spam(uid: int, on: bool):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET can_spam=? WHERE user_id=?", (1 if on else 0, uid))
    conn.commit(); conn.close()

def get_can_spam(uid: int) -> bool:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT can_spam FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); conn.close()
    return bool(row and row[0])

def get_last_farm_ts(uid: int) -> int:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT last_farm_ts FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone(); conn.close()
    return int(row[0]) if row else 0

def set_last_farm_now(uid: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE users SET last_farm_ts=? WHERE user_id=?", (int(time.time()), uid))
    conn.commit(); conn.close()

# ---- INVENTORY ----
def get_inv(uid: int) -> List[Tuple[str, int]]:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT item, qty FROM inventory WHERE user_id=? ORDER BY item", (uid,))
    rows = cur.fetchall(); conn.close()
    return rows

def add_item(uid: int, item: str, qty: int):
    conn = _conn(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO inventory(user_id, item, qty)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, item)
        DO UPDATE SET qty = qty + excluded.qty
    """, (uid, item, qty))
    conn.commit(); conn.close()

def use_item(uid: int, item: str, qty: int = 1) -> bool:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT qty FROM inventory WHERE user_id=? AND item=?", (uid, item))
    row = cur.fetchone()
    if not row or row[0] < qty:
        conn.close(); return False
    cur.execute("UPDATE inventory SET qty = qty - ? WHERE user_id=? AND item=?", (qty, uid, item))
    cur.execute("DELETE FROM inventory WHERE user_id=? AND item=? AND qty<=0", (uid, item))
    conn.commit(); conn.close(); return True

# ---- SHOP OPS ----
def list_shop() -> List[Tuple[str, int, str]]:
    return [(name, SHOP_ITEMS[name][0], SHOP_ITEMS[name][1]) for name in SHOP_ITEMS.keys()]

def buy(uid: int, item: str, qty: int) -> Optional[str]:
    if item not in SHOP_ITEMS:
        return "❌ Vật phẩm không tồn tại."
    price = SHOP_ITEMS[item][0] * qty
    have = get_gold(uid)
    if have < price:
        return f"❌ Không đủ vàng. Cần {price}, bạn có {have}."
    add_gold(uid, -price)
    add_item(uid, item, qty)
    return f"🛒 Đã mua {qty} **{item}** với giá {price} vàng."

# ---- BUFFS ----
def activate_buff(uid: int, buff_name: str, now_ts: Optional[int] = None) -> int:
    if now_ts is None: now_ts = int(time.time())
    expires = now_ts + BUFF_DUR_SEC
    conn = _conn(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO buffs (user_id, buff_name, expires_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, buff_name)
        DO UPDATE SET expires_at = excluded.expires_at
    """, (uid, buff_name, expires))
    conn.commit(); conn.close()
    return expires

def get_active_buffs(uid: int) -> Dict[str, int]:
    now_ts = int(time.time())
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT buff_name, expires_at FROM buffs WHERE user_id=?", (uid,))
    rows = cur.fetchall(); conn.close()
    out = {}
    for name, exp_at in rows:
        left = int(exp_at) - now_ts
        if left > 0:
            out[name] = left
    return out

def clear_expired_buffs(uid: int):
    now_ts = int(time.time())
    conn = _conn(); cur = conn.cursor()
    cur.execute("DELETE FROM buffs WHERE user_id=? AND expires_at<=?", (uid, now_ts))
    conn.commit(); conn.close()

# ---- CONFIG ----
def get_allowed_channel_id() -> Optional[int]:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT allowed_channel_id FROM config WHERE id=1")
    row = cur.fetchone(); conn.close()
    return int(row[0]) if row and row[0] is not None else None

def set_allowed_channel_id(ch_id: Optional[int]):
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE config SET allowed_channel_id=? WHERE id=1", (ch_id,))
    conn.commit(); conn.close()

def get_death_rate() -> int:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT death_rate_percent FROM config WHERE id=1")
    row = cur.fetchone(); conn.close()
    return int(row[0]) if row else 35

def set_death_rate(p: int):
    p = max(0, min(100, p))
    conn = _conn(); cur = conn.cursor()
    cur.execute("UPDATE config SET death_rate_percent=? WHERE id=1", (p,))
    conn.commit(); conn.close()

# ---- LEADERBOARD ----
def top_rich(limit: int = 10) -> List[Tuple[str, int]]:
    conn = _conn(); cur = conn.cursor()
    cur.execute("SELECT username, gold FROM users ORDER BY gold DESC LIMIT ?", (limit,))
    rows = cur.fetchall(); conn.close()
    return rows

# ---- PARSE ----
def parse_amount(text: str) -> Optional[int]:
    # chỉ nhận chuỗi số KHÔNG dấu . hoặc ,  (vd: "125236314631461")
    if not isinstance(text, str): return None
    s = text.strip()
    if not s.isdigit(): return None
    v = int(s)
    return v if v > 0 else None
