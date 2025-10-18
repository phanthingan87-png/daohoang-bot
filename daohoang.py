# daohoang.py — SQLite (.db) + quản trị admin
import sqlite3, json, os, re, random, time

DB_FILE = "players.db"

# ===== CẤU HÌNH ADMIN (dựa theo username) =====
# Ai có username trong set này sẽ tự nhận admin ở lần đầu tạo tài khoản.
# Sau đó có thể cấp/thu hồi bằng ksetadmin.
ADMIN_USERNAMES = {"admin", "sr.nguoihanhtinh_vnvodich","sr_baby_wanna_cry","villain911"}

# ===== SHOP & BONUS =====
shop_items = {
    "cuocgo": 10,         # +1/farm
    "cuocsat": 20,        # +2/farm
    "cuocvang": 50,       # +5/farm
    "cuockimcuong": 100,  # +10/farm
    "khien": 10,          # -15% tỉ lệ chết cho 1 lần farm (tiêu hao 1/lần)
    "khienvip": 200,      # miễn tử 100% | mỗi món = 10 lượt sử dụng
    "thuoc": 100          # booster x2 farm trong 5 phút (tiêu hao khi dùng)
}
tool_bonus = {"cuocgo": 1, "cuocsat": 2, "cuocvang": 5, "cuockimcuong": 10}

# ===== CẤU HÌNH GAME =====
DEATH_CHANCE_DEFAULT = 0.35      # tỉ lệ chết mặc định 35%
SHIELD_DEATH_REDUCTION = 0.15    # khiên thường giảm 15%
DEATH_PENALTY_RATIO = 0.5        # chết mất 50% coin hiện có
FARM_COOLDOWN = 10               # 10s mỗi lần farm (Admin: không cooldown)
ADVENTURE_CD = 1800              # 30 phút
PVP_CD = 3600                    # 1 giờ
DAILY_RESET = 86400              # 24 giờ

MENTION_RE = re.compile(r"^<@!?(\d+)>$")

# ====== DB LAYER ======
def _db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    conn = _db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        coin INTEGER NOT NULL DEFAULT 0,
        exp INTEGER NOT NULL DEFAULT 0,
        level INTEGER NOT NULL DEFAULT 1,
        ban INTEGER NOT NULL DEFAULT 0,
        is_admin INTEGER NOT NULL DEFAULT 0,
        inventory TEXT NOT NULL DEFAULT '{}',
        last_farm_time REAL NOT NULL DEFAULT 0,
        last_adventure REAL NOT NULL DEFAULT 0,
        last_pvp REAL NOT NULL DEFAULT 0,
        booster_until REAL NOT NULL DEFAULT 0,
        daily_farm INTEGER NOT NULL DEFAULT 0,
        daily_completed INTEGER NOT NULL DEFAULT 0,
        daily_last_reset REAL NOT NULL DEFAULT 0
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""")
    # defaults
    _set_setting("death_chance", DEATH_CHANCE_DEFAULT)
    if _get_setting("farm_channel_id") is None:
        _set_setting("farm_channel_id", None)
    conn.commit()
    conn.close()

def _get_setting(key):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row["value"])
    except Exception:
        return row["value"]

def _set_setting(key, value):
    conn = _db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, ensure_ascii=False))
    )
    conn.commit()
    conn.close()

def _fmt(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")

def _parse_pos_int(s: str):
    clean = str(s).replace(".", "").replace(",", "")
    if not clean.isdigit():
        return None
    val = int(clean)
    return val if val > 0 else None

def _is_admin_username(username: str) -> bool:
    return username in ADMIN_USERNAMES

def _row_to_user(row):
    inv = {}
    try:
        inv = json.loads(row["inventory"]) if row["inventory"] else {}
    except Exception:
        inv = {}
    return {
        "id": row["id"],
        "username": row["username"],
        "coin": row["coin"],
        "exp": row["exp"],
        "level": row["level"],
        "ban": bool(row["ban"]),
        "is_admin": bool(row["is_admin"]),
        "inventory": inv,
        "last_farm_time": row["last_farm_time"],
        "last_adventure": row["last_adventure"],
        "last_pvp": row["last_pvp"],
        "booster_until": row["booster_until"],
        "daily_progress": {
            "farm": row["daily_farm"],
            "completed": bool(row["daily_completed"]),
            "last_reset": row["daily_last_reset"],
        }
    }

def _save_user(user):
    conn = _db()
    cur = conn.cursor()
    inv_json = json.dumps(user["inventory"], ensure_ascii=False)
    dp = user["daily_progress"]
    cur.execute("""
    UPDATE players SET
        username=?, coin=?, exp=?, level=?, ban=?, is_admin=?,
        inventory=?, last_farm_time=?, last_adventure=?, last_pvp=?,
        booster_until=?, daily_farm=?, daily_completed=?, daily_last_reset=?
    WHERE id=?""", (
        user["username"], int(user["coin"]), int(user["exp"]), int(user["level"]),
        1 if user["ban"] else 0, 1 if user["is_admin"] else 0,
        inv_json, float(user["last_farm_time"]), float(user["last_adventure"]), float(user["last_pvp"]),
        float(user["booster_until"]), int(dp["farm"]), 1 if dp["completed"] else 0, float(dp["last_reset"]),
        user["id"]
    ))
    conn.commit()
    conn.close()

def _get_user_by_id(uid: str):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM players WHERE id=?", (uid,))
    row = cur.fetchone()
    conn.close()
    return _row_to_user(row) if row else None

def _get_user_by_name(name: str):
    conn = _db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM players WHERE lower(username)=lower(?) LIMIT 1", (name,))
    row = cur.fetchone()
    conn.close()
    return _row_to_user(row) if row else None

def _create_user(uid: str, username: str):
    conn = _db()
    cur = conn.cursor()
    cur.execute("""INSERT OR IGNORE INTO players
        (id, username, coin, exp, level, ban, is_admin, inventory,
         last_farm_time, last_adventure, last_pvp,
         booster_until, daily_farm, daily_completed, daily_last_reset)
         VALUES (?, ?, 0, 0, 1, 0, ?, '{}', 0, 0, 0, 0, 0, 0, 0)
    """, (uid, username, 1 if _is_admin_username(username) else 0))
    conn.commit()
    conn.close()
    return _get_user_by_id(uid)

def _find_user_key_by_token(token: str):
    token = token.strip()
    m = MENTION_RE.match(token)
    if m:
        uid = m.group(1)
        if _get_user_by_id(uid): return uid
        return None
    u = _get_user_by_name(token)
    return u["id"] if u else None

def _calc_farm_bonus(user_dict: dict) -> int:
    inv = user_dict.get("inventory", {})
    return sum(int(inv.get(name, 0)) * per for name, per in tool_bonus.items())

def _calc_level_bonus(level: int) -> float:
    return 1 + (level * 0.02)   # +2% mỗi cấp

def _gain_exp(user, gain):
    exp_add = gain // 10
    user["exp"] += exp_add
    needed = user["level"] * 100
    leveled = False
    while user["exp"] >= needed:
        user["exp"] -= needed
        user["level"] += 1
        needed = user["level"] * 100
        leveled = True
    return leveled, exp_add

def _check_daily_reset(user):
    now = time.time()
    dp = user["daily_progress"]
    if now - dp.get("last_reset", 0) > DAILY_RESET:
        user["daily_progress"] = {"farm": 0, "completed": False, "last_reset": now}

def _reset_user_fields(user: dict):
    """RS dữ liệu người chơi về mặc định, giữ username & quyền admin."""
    keep_name = user["username"]
    keep_admin = user["is_admin"]
    user.update({
        "username": keep_name,
        "coin": 0,
        "exp": 0,
        "level": 1,
        "ban": False,
        "is_admin": keep_admin,
        "inventory": {},
        "last_farm_time": 0,
        "last_adventure": 0,
        "last_pvp": 0,
        "booster_until": 0,
        "daily_progress": {"farm": 0, "completed": False, "last_reset": 0}
    })

# ===== API PUBLIC =====
def create_discord_account(user_id, username):
    _init_db()
    uid = str(user_id)
    user = _get_user_by_id(uid)
    if not user:
        user = _create_user(uid, username)
    # update username & admin flag if changed
    if user["username"] != username or user["is_admin"] != _is_admin_username(username):
        user["username"] = username
        # lưu quyền admin hiện có; không tự override nếu đã set bằng lệnh
        # chỉ auto-grant nếu trước đó chưa có và username thuộc ADMIN_USERNAMES
        if not user["is_admin"] and _is_admin_username(username):
            user["is_admin"] = True
        _save_user(user)
    return user

def get_user(user_id):
    _init_db()
    return _get_user_by_id(str(user_id))

# ===== GAME HELPERS (kcf / slots / bj) =====
def _bet_check(user, bet):
    if bet is None or bet <= 0:
        return "❌ Cược phải là số > 0."
    if user["coin"] < bet:
        return f"❌ Không đủ coin để cược {_fmt(bet)}! Bạn có {_fmt(user['coin'])}."
    return None

def _coinflip_play(user, bet, side):  # side in {"h","t"} = head/tail
    err = _bet_check(user, bet)
    if err: return err
    side = side.lower()
    if side not in ("h","t"):
        return "❌ Dùng: `kcf <tiền_cược> <h|t>` (h=heads/ngửa, t=tails/sấp)"
    user["coin"] -= bet
    roll = random.choice(("h","t"))
    if roll == side:
        user["coin"] += bet * 2
        txt = f"🎉 Thắng! +{_fmt(bet)}"
    else:
        txt = f"💥 Thua! -{_fmt(bet)}"
    _save_user(user)
    return f"🪙 **Coinflip** → ra: {roll.upper()} 🪙\n{txt} • Số dư: {_fmt(user['coin'])}"

_SLOTS_SYMS = ["🍒","🍋","🔔","⭐","7️⃣"]
def _slots_play(user, bet):
    err = _bet_check(user, bet)
    if err: return err
    user["coin"] -= bet
    a,b,c = [random.choice(_SLOTS_SYMS) for _ in range(3)]
    reels = f"{a} | {b} | {c}"

    mult = 0
    if a==b==c=="7️⃣": mult=10
    elif a==b==c: mult=5
    elif a==b or a==c or b==c: mult=2

    if mult>0:
        gain = bet*mult
        user["coin"] += gain
        _save_user(user)
        return f"🎰 **Slots** → {reels}\n🎉 Trúng x{mult}! Lãi {_fmt(gain-bet)}. Số dư: {_fmt(user['coin'])}"
    else:
        _save_user(user)
        return f"🎰 **Slots** → {reels}\n💥 Trượt rồi! Mất {_fmt(bet)}. Số dư: {_fmt(user['coin'])}"

def _bj_draw():
    ranks = [2,3,4,5,6,7,8,9,10,10,10,10,11]  # J,Q,K=10; A=11
    return random.choice(ranks)

def _bj_value(cards):
    total = sum(cards); aces = cards.count(11)
    while total>21 and aces>0:
        total -= 10; aces -= 1
    return total

def _bj_play(user, bet):
    err = _bet_check(user, bet)
    if err: return err
    user["coin"] -= bet
    player = [_bj_draw(), _bj_draw()]
    dealer = [_bj_draw(), _bj_draw()]
    while _bj_value(player) < 17: player.append(_bj_draw())
    while _bj_value(dealer) < 17: dealer.append(_bj_draw())
    pv, dv = _bj_value(player), _bj_value(dealer)
    cards = lambda xs: " ".join([("A" if x==11 else str(x)) for x in xs])
    head = f"🃏 **Blackjack**\nBạn: {cards(player)} (= {pv})\nNhà cái: {cards(dealer)} (= {dv})"
    if pv>21:
        _save_user(user); return f"{head}\n💥 Bạn quắc (>21). Mất {_fmt(bet)}. Số dư: {_fmt(user['coin'])}"
    if dv>21 or pv>dv:
        user["coin"] += bet*2; _save_user(user)
        return f"{head}\n🎉 Bạn thắng! Lãi {_fmt(bet)}. Số dư: {_fmt(user['coin'])}"
    if pv==dv:
        user["coin"] += bet; _save_user(user)
        return f"{head}\n🤝 Hòa! Hoàn tiền. Số dư: {_fmt(user['coin'])}"
    _save_user(user); return f"{head}\n💥 Thua! Mất {_fmt(bet)}. Số dư: {_fmt(user['coin'])}"

# ===== COMMAND DISPATCH =====
def process_command(user_id, username, cmd, channel_id=None):
    _init_db()
    user = create_discord_account(user_id, username)

    _check_daily_reset(user)
    if user["ban"]:
        return "🚫 Bạn đã bị ban!"
    _save_user(user)  # lưu last_reset nếu có

    parts = cmd.split()
    if not parts:
        return "❌ Lệnh không hợp lệ!"
    action = parts[0]

    # Giới hạn kênh farm nếu có
    farm_channel_id = _get_setting("farm_channel_id")
    if action == "kfarm" and farm_channel_id is not None:
        if channel_id and str(channel_id) != str(farm_channel_id):
            return f"🚫 Bạn chỉ có thể farm trong <#{farm_channel_id}>!"

    # ===== FARM =====
    if action == "kfarm":
        now = time.time()
        # Admin KHÔNG cooldown
        if not user["is_admin"]:
            if now - user["last_farm_time"] < FARM_COOLDOWN:
                remain = FARM_COOLDOWN - (now - user["last_farm_time"])
                return f"⏳ Còn {remain:.1f}s nữa mới farm được!"
        user["last_farm_time"] = now

        inv = user["inventory"]
        death_chance = float(_get_setting("death_chance") or DEATH_CHANCE_DEFAULT)
        effective_death = death_chance

        # Ưu tiên dùng KHIENTVIP (mỗi món = 10 lượt; inventory lưu số lượt)
        vip_uses = int(inv.get("khienvip", 0))
        if vip_uses > 0:
            inv["khienvip"] = vip_uses - 1
            effective_death = 0.0
        else:
            shields = int(inv.get("khien", 0))
            if shields > 0:
                inv["khien"] = shields - 1
                effective_death = max(0.0, effective_death - SHIELD_DEATH_REDUCTION)

        if random.random() < effective_death:
            lost = int(user["coin"] * DEATH_PENALTY_RATIO)
            user["coin"] -= lost
            _save_user(user)
            return f"💀 {username} chết khi đào! Mất {_fmt(lost)} coin (còn {_fmt(user['coin'])})."

        base = random.randint(5, 10)
        bonus = _calc_farm_bonus(user)
        level_bonus = _calc_level_bonus(user["level"])
        gain = int((base + bonus) * level_bonus)

        # booster x2 nếu còn hiệu lực
        if now < user.get("booster_until", 0):
            gain *= 2

        user["coin"] += gain
        leveled, exp_gain = _gain_exp(user, gain)
        user["daily_progress"]["farm"] += 1
        _save_user(user)

        msg = f"🌾 {username} nhận {_fmt(gain)} coin (+{_fmt(exp_gain)} exp). Tổng: {_fmt(user['coin'])}"
        if leveled:
            msg += f"\n🎉 **LÊN CẤP!** → Level {user['level']} (đào mạnh hơn +2%)"
        return msg

    # ===== BOOSTER / STATUS =====
    elif action == "kdung":
        if len(parts) < 2 or parts[1].lower() != "thuoc":
            return "❌ Dùng: `kdung thuoc` để kích hoạt x2 farm trong 5 phút."
        inv = user["inventory"]
        have = int(inv.get("thuoc", 0))
        if have <= 0:
            return "❌ Bạn không có 'thuoc'. Mua ở `kshop` (100 coin)."
        inv["thuoc"] = have - 1
        user["booster_until"] = time.time() + 300
        _save_user(user)
        return "🧪 Đã dùng **thuoc**! Trong 5 phút tới **x2** coin khi farm."

    elif action == "kstatus":
        now = time.time()
        booster_left = max(0, int(user.get("booster_until", 0) - now))
        eff = []
        eff.append(f"🧪 Booster x2 còn {booster_left}s" if booster_left > 0 else "🧪 Booster: không hoạt động")
        death_pct = int(float(_get_setting("death_chance") or DEATH_CHANCE_DEFAULT) * 100)
        eff.append(f"☠️ Tỉ lệ chết hiện tại: {death_pct}% (khiên thường -15%/lượt)")
        cd_left = 0 if user.get("is_admin") else max(0, int(FARM_COOLDOWN - (time.time() - user.get('last_farm_time', 0))))
        eff.append(f"⏳ Farm cooldown còn: {cd_left}s")
        vip_left = int(user["inventory"].get("khienvip", 0))
        if vip_left > 0:
            eff.append(f"🛡️ Khiên VIP lượt còn: {vip_left}")
        return "📊 **Trạng thái**:\n" + "\n".join(eff)

    # ===== ADVENTURE =====
    elif action == "kadventure":
        now = time.time()
        if now - user["last_adventure"] < ADVENTURE_CD:
            remain = ADVENTURE_CD - (now - user["last_adventure"])
            return f"🧭 Hãy nghỉ {int(remain//60)} phút nữa rồi khám phá tiếp!"
        user["last_adventure"] = now
        roll = random.random()
        if roll < 0.6:
            reward = random.randint(50, 500)
            user["coin"] += reward
            _save_user(user)
            return f"🗺️ {username} tìm được kho báu nhỏ chứa {_fmt(reward)} coin!"
        elif roll < 0.85:
            item = random.choice(list(shop_items.keys()))
            inv = user["inventory"]; inv[item] = inv.get(item, 0) + 1
            _save_user(user)
            return f"🎁 {username} tìm thấy 1 {item} khi khám phá!"
        else:
            lost = int(user["coin"] * 0.25)
            user["coin"] -= lost
            _save_user(user)
            return f"💥 {username} bị bão biển cuốn mất {_fmt(lost)} coin!"

    # ===== PVP =====
    elif action == "krob":
        if len(parts) < 2:
            return "❌ Dùng: `krob <@user|username>`"
        now = time.time()
        if now - user["last_pvp"] < PVP_CD:
            remain = int((PVP_CD - (now - user["last_pvp"])) / 60)
            return f"⚔️ Cần chờ {remain} phút nữa để cướp tiếp!"
        target_key = _find_user_key_by_token(parts[1])
        if not target_key:
            return "❌ Không tìm thấy nạn nhân!"
        target = _get_user_by_id(target_key)
        if not target or target["coin"] <= 0:
            return "💸 Nạn nhân không có coin!"
        user["last_pvp"] = now
        if random.random() < 0.5:
            rate = random.uniform(0.1, 0.3)
            stolen = int(target["coin"] * rate)
            target["coin"] -= stolen; user["coin"] += stolen
            _save_user(target); _save_user(user)
            return f"🏴‍☠️ {username} cướp thành công {_fmt(stolen)} coin từ {target['username']}!"
        else:
            penalty = int(user["coin"] * 0.1)
            user["coin"] -= penalty; _save_user(user)
            return f"💥 {username} bị phản đòn và mất {_fmt(penalty)} coin!"

    # ===== DAILY =====
    elif action == "kdaily":
        dp = user["daily_progress"]
        if dp.get("completed", False):
            return "✅ Bạn đã hoàn thành nhiệm vụ hôm nay rồi!"
        if dp["farm"] >= 10:
            reward = random.randint(500, 1000)
            user["coin"] += reward
            item = random.choice(list(shop_items.keys()))
            inv = user["inventory"]; inv[item] = inv.get(item, 0) + 1
            dp["completed"] = True
            _save_user(user)
            return f"🎉 Hoàn thành nhiệm vụ hằng ngày! Thưởng {_fmt(reward)} coin + 1 {item}!"
        else:
            return f"📋 Nhiệm vụ hôm nay: Farm 10 lần (hiện tại: {dp['farm']}/10)."

    # ===== MINI-GAME =====
    elif action == "kcf":
        if len(parts) < 3:
            return "❌ Dùng: `kcf <tiền_cược> <h|t>`"
        bet = _parse_pos_int(parts[1]); side = parts[2]
        return _coinflip_play(user, bet, side)

    elif action == "os":
        if len(parts) < 2:
            return "❌ Dùng: `os <tiền_cược>`"
        bet = _parse_pos_int(parts[1])
        return _slots_play(user, bet)

    elif action == "obj":
        if len(parts) < 2:
            return "❌ Dùng: `obj <tiền_cược>`"
        bet = _parse_pos_int(parts[1])
        return _bj_play(user, bet)

    # ===== SHOP / BUY =====
    elif action == "kshop":
        lines = []
        for name, price in shop_items.items():
            if name in tool_bonus:
                lines.append(f"- {name}: {_fmt(price)} coin (bonus +{tool_bonus[name]}/lần farm)")
            elif name == "khien":
                lines.append(f"- {name}: {_fmt(price)} coin (giảm 15% tỉ lệ chết, tiêu 1/lần)")
            elif name == "khienvip":
                lines.append(f"- {name}: {_fmt(price)} coin (MIỄN TỬ 100%, mỗi món = 10 lượt)")
            elif name == "thuoc":
                lines.append(f"- {name}: {_fmt(price)} coin (booster x2 coin trong 5 phút khi dùng)")
        return "🏪 **Cửa hàng:**\n" + "\n".join(lines) + "\n\n🧪 Dùng booster: `kdung thuoc` • `kstatus` xem trạng thái"

    elif action == "kmua":
        if len(parts) < 3:
            return "❌ Dùng: `kmua <vật_phẩm> <số_lượng>`"
        item = parts[1]; sl = _parse_pos_int(parts[2])
        if item not in shop_items or sl is None:
            return "❌ Không hợp lệ!"
        cost = shop_items[item] * sl
        if user["coin"] < cost:
            return f"❌ Không đủ coin! Cần {_fmt(cost)}, bạn có {_fmt(user['coin'])}."
        user["coin"] -= cost
        inv = user["inventory"]
        if item == "khienvip":
            inv["khienvip"] = int(inv.get("khienvip", 0)) + 10 * sl  # 1 món = 10 lượt
        else:
            inv[item] = int(inv.get(item, 0)) + sl
        _save_user(user)
        return f"🛒 Mua {_fmt(sl)} {item} với giá {_fmt(cost)} coin. (Còn lại: {_fmt(user['coin'])})"

    # ===== INVENTORY / TOP =====
    elif action in ["kkho", "kinv"]:
        inv = user["inventory"]
        items = "\n".join([f"- {i}: {_fmt(v)}" for i, v in inv.items()]) or "Không có gì."
        return f"🎒 **Kho của {username}:**\n{items}\n💰 Coin: {_fmt(user['coin'])}\n🏅 Level {user['level']} ({_fmt(user['exp'])} exp)"

    elif action == "ktop":
        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT username, coin, level FROM players ORDER BY coin DESC LIMIT 10")
        rows = cur.fetchall(); conn.close()
        msg = "🏆 **Top 10 người giàu nhất:**\n"
        for i, r in enumerate(rows, 1):
            msg += f"{i}. {r['username']} - {_fmt(r['coin'])} coin - Lv {r['level']}\n"
        return msg if rows else "Chưa có ai trong bảng xếp hạng."

    # ===== ADMIN: BAN / UNBAN / RESET / COIN / LV / SETADMIN / SETDEATH / CHANNEL =====
    elif action == "kban":
        if not user["is_admin"]:
            return "❌ Chỉ admin được dùng!"
        if len(parts) < 2:
            return "❌ Dùng: `kban <@user|username>`"
        target_key = _find_user_key_by_token(parts[1])
        if not target_key: return "❌ Không tìm thấy người chơi!"
        target = _get_user_by_id(target_key); target["ban"] = True; _save_user(target)
        return f"🚫 Đã **ban** {target['username']}."

    elif action == "kunban":
        if not user["is_admin"]:
            return "❌ Chỉ admin được dùng!"
        if len(parts) < 2:
            return "❌ Dùng: `kunban <@user|username>`"
        target_key = _find_user_key_by_token(parts[1])
        if not target_key: return "❌ Không tìm thấy người chơi!"
        target = _get_user_by_id(target_key); target["ban"] = False; _save_user(target)
        return f"✅ Đã **gỡ ban** {target['username']}."

    elif action == "krs":
        if not user["is_admin"]:
            return "❌ Chỉ admin được dùng!"
        if len(parts) < 2:
            return "❌ Dùng: `krs <@user|username>`"
        target_key = _find_user_key_by_token(parts[1])
        if not target_key: return "❌ Không tìm thấy người chơi!"
        target = _get_user_by_id(target_key); _reset_user_fields(target); _save_user(target)
        return f"♻️ Đã **reset sạch** dữ liệu của {target['username']}."

    elif action == "kaddcoin":
        if not user["is_admin"]:
            return "❌ Chỉ admin được dùng!"
        if len(parts) < 3:
            return "❌ Dùng: `kaddcoin <@user|username> <số_coin>`"
        target_key = _find_user_key_by_token(parts[1]); amount = _parse_pos_int(parts[2])
        if not target_key or amount is None: return "❌ Cú pháp sai!"
        target = _get_user_by_id(target_key); target["coin"] += amount; _save_user(target)
        return f"💰 +{_fmt(amount)} coin cho {target['username']} (hiện có {_fmt(target['coin'])})."

    elif action == "kremovecoin":
        if not user["is_admin"]:
            return "❌ Chỉ admin được dùng!"
        if len(parts) < 3:
            return "❌ Dùng: `kremovecoin <@user|username> <số_coin>`"
        target_key = _find_user_key_by_token(parts[1]); amount = _parse_pos_int(parts[2])
        if not target_key or amount is None: return "❌ Cú pháp sai!"
        target = _get_user_by_id(target_key)
        if target["coin"] < amount: amount = target["coin"]
        target["coin"] -= amount; _save_user(target)
        return f"💸 Đã trừ {_fmt(amount)} coin của {target['username']} (còn {_fmt(target['coin'])})."

    elif action == "ksetlv":
        if not user["is_admin"]:
            return "❌ Chỉ admin được dùng!"
        if len(parts) < 3:
            return "❌ Dùng: `ksetlv <@user|username> <level>`"
        target_key = _find_user_key_by_token(parts[1]); lvl = _parse_pos_int(parts[2])
        if not target_key or lvl is None: return "❌ Cú pháp sai!"
        target = _get_user_by_id(target_key); target["level"] = lvl; target["exp"] = 0; _save_user(target)
        return f"🏅 Đã đặt level của {target['username']} = {lvl}."

    elif action == "ksetadmin":
        if not user["is_admin"]:
            return "❌ Chỉ admin được dùng!"
        if len(parts) < 3:
            return "❌ Dùng: `ksetadmin <@user|username> <on|off>`"
        target_key = _find_user_key_by_token(parts[1]); val = parts[2].lower()
        if not target_key or val not in ("on","off"): return "❌ Cú pháp sai!"
        target = _get_user_by_id(target_key); target["is_admin"] = (val == "on"); _save_user(target)
        state = "cấp **admin**" if val=="on" else "thu hồi **admin**"
        return f"🛠️ Đã {state} cho {target['username']}."

    elif action == "ksetdeath":
        if not user["is_admin"]:
            return "❌ Chỉ admin được dùng!"
        if len(parts) < 2:
            return "❌ Dùng: `ksetdeath <phần_trăm>` (vd: 25)"
        try: pct = int(parts[1])
        except ValueError: return "❌ Phải là số nguyên 0–100."
        if not (0 <= pct <= 100): return "❌ Phải trong khoảng 0–100."
        _set_setting("death_chance", pct / 100.0)
        return f"✅ Đã đặt tỉ lệ chết = {pct}%."

    elif action == "ksetchannel":
        if not user["is_admin"]:
            return "❌ Chỉ admin được dùng!"
        if len(parts) < 2:
            return "❌ Dùng: `ksetchannel <#kênh>`"
        ch = parts[1].strip("<#>")
        if not ch.isdigit(): return "❌ Sai cú pháp, tag đúng kênh nhé!"
        _set_setting("farm_channel_id", int(ch))
        return f"✅ Đã set kênh farm cố định: <#{ch}>"

    elif action == "kunsetchannel":
        if not user["is_admin"]:
            return "❌ Chỉ admin được dùng!"
        if _get_setting("farm_channel_id") is None:
            return "⚠️ Chưa có kênh nào được set."
        _set_setting("farm_channel_id", None)
        return "✅ Đã hủy set kênh farm — giờ có thể farm ở mọi nơi!"

    # ===== HELP =====
    elif action == "khelp":
        return """
📜 **HƯỚNG DẪN LỆNH ĐẢO HOANG (SQLite .db)**

🌾 `kfarm` → Đào coin (5–10 + bonus cuốc, 10s hồi) • 35% chết; khiên thường -15% • Admin: không cooldown
🧪 `kdung thuoc` → Dùng booster x2 farm trong 5 phút (tiêu hao) • `kstatus` xem trạng thái
🧭 `kadventure` (30') • ⚔️ `krob <@user|username>` (1h)
📅 `kdaily` nhiệm vụ hằng ngày • 🏆 `ktop` bảng xếp hạng

🎲 **Mini-game**
`kcf <tiền> <h|t>` • `os <tiền>` • `obj <tiền>`

🏪 `kshop` / `kmua <item> <số_lượng>`
🛡️ `khien` (giảm 15%/lần) • `khienvip` (MIỄN TỬ 100%, mỗi món = 10 lượt)
🔨 Cuốc: gỗ +1 • sắt +2 • vàng +5 • kim cương +10

**Admin:**
`kban <@user>` / `kunban <@user>` • `krs <@user>` (reset dữ liệu)
`kaddcoin <@user> <coin>` / `kremovecoin <@user> <coin>`
`ksetlv <@user> <level>` • `ksetadmin <@user> <on|off>`
`ksetdeath <percent>` • `ksetchannel #kênh` / `kunsetchannel`
"""

    else:
        return "❌ Lệnh không hợp lệ! Dùng `khelp` để xem hướng dẫn."
