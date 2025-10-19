# main.py — Bot Discord full V6: farm + casino + buff + admin tier + spam + channel lock + keep-alive
import os, random, asyncio, time
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

import daohoang as db

# ===== Keep-alive (Render) =====
app = Flask(__name__)
@app.route("/")
def home():
    return "✅ Dao Hoang V6 is running!"

def _run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=_run_web, daemon=True).start()

# ===== Discord =====
TOKEN = os.getenv("DISCORD_TOKEN")

SUPER_ADMIN_NAME = "sr.nguoihanhtinh_vnvodich"  # super admin theo yêu cầu

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="k", intents=intents, help_command=None)

EMOJIS = ["😼","🐾","💥","✨","💎","🔥","🪙","⚒️","🎲","🎰","🛡️","🏝️"]

async def owo_typing(ctx, a=0.5, b=1.5):
    async with ctx.typing():
        await asyncio.sleep(random.uniform(a, b))

db.setup_database()

# ===== Helpers =====
def _is_super_admin(member: discord.Member) -> bool:
    return (member.name == SUPER_ADMIN_NAME)

def _is_admin(member: discord.Member) -> bool:
    return _is_super_admin(member) or db.is_admin(member.id)

def _channel_locked_ok(channel_id: int) -> bool:
    allowed = db.get_allowed_channel_id()
    return (allowed is None) or (allowed == channel_id)

async def _gate(ctx) -> bool:
    if not _channel_locked_ok(ctx.channel.id):
        await ctx.reply("🚫 Bot chỉ hoạt động trong kênh đã set bằng `ksetchannel`.")
        return False
    uid = ctx.author.id
    if db.is_banned(uid) and not _is_super_admin(ctx.author):
        await ctx.reply("⛔ Bạn đã bị ban.")
        return False
    return True

def _effective_death_rate(uid: int) -> int:
    base = db.get_death_rate()
    buffs = db.get_active_buffs(uid)
    # thuốc giảm chết → 50% base
    if "thuoc_giamchet" in buffs:
        return max(0, base // 2)
    return base

def _apply_gain_with_buffs(uid: int, amount: int) -> int:
    buffs = db.get_active_buffs(uid)
    gain = amount
    if "thuoc_x2" in buffs and amount > 0:
        gain = amount * 2
    db.add_gold(uid, gain)
    return gain

async def _schedule_buff_end_notice(ctx, buff_name: str, seconds: int):
    try:
        await asyncio.sleep(seconds)
        # sau thời gian này, clear_expired để chắc chắn
        db.clear_expired_buffs(ctx.author.id)
        # nếu đã hết thì báo
        if buff_name not in db.get_active_buffs(ctx.author.id):
            await ctx.reply(f"⏰ Thuốc **{buff_name}** đã hết hiệu lực.")
    except Exception:
        pass

# ===== Events =====
@bot.event
async def on_ready():
    print(f"✅ Online: {bot.user} | Guilds: {len(bot.guilds)}")

# ===== Player commands =====
@bot.command(name="start")
async def kstart(ctx):
    if not await _gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    await ctx.reply(f"🏝️ Xin chào **{ctx.author.display_name}**! Tài khoản đã sẵn sàng. Dùng `khelp` để xem lệnh.")

@bot.command(name="profile")
async def kprofile(ctx, member: discord.Member | None = None):
    if not await _gate(ctx): return
    user = member or ctx.author
    db.ensure_user(user.id, user.name)
    gold = db.get_gold(user.id)
    await owo_typing(ctx, 0.3, 0.8)
    await ctx.reply(f"📜 **{user.display_name}** — 💰 {gold} vàng.")

@bot.command(name="daily")
async def kdaily(ctx):
    if not await _gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    if not db.can_daily(ctx.author.id):
        return await ctx.reply("🕒 Hôm nay bạn nhận **daily** rồi!")
    reward = random.randint(1000, 3000)
    got = _apply_gain_with_buffs(ctx.author.id, reward)
    db.set_daily_today(ctx.author.id)
    db.add_exp(ctx.author.id, 10)
    await owo_typing(ctx)
    await ctx.reply(f"🎉 Daily: +{got} vàng {random.choice(EMOJIS)}")

@bot.command(name="farm")
async def kfarm(ctx):
    if not await _gate(ctx): return
    uid = ctx.author.id
    db.ensure_user(uid, ctx.author.name)

    # cooldown 10s (trừ khi can_spam = 1)
    if not db.get_can_spam(uid) and not _is_super_admin(ctx.author):
        last = db.get_last_farm_ts(uid)
        now = int(time.time())
        if now - last < 10:
            return await ctx.reply(f"⏳ Hãy đợi {10 - (now - last)}s nữa nhé.")
        db.set_last_farm_now(uid)

    # death check
    if random.randint(1, 100) <= _effective_death_rate(uid):
        # dùng khien/khien_vip
        if db.use_item(uid, "khien", 1):
            return await ctx.reply("🛡️ Gặp nạn nhưng **khiên** đã cứu bạn. Không mất gì!")
        elif db.use_item(uid, "khien_vip", 1):  # mỗi qty = 1 lần (5 lần mua = qty 5)
            return await ctx.reply("🛡️ **Khiên VIP** đã cứu bạn! Không mất gì!")
        else:
            lose = min(db.get_gold(uid), max(0, db.get_gold(uid) // 10))
            db.add_gold(uid, -lose)
            db.add_exp(uid, 2)
            return await ctx.reply(f"💀 Xui quá! Bạn gặp nạn và mất {lose} vàng.")

    # base 5-10 + bonus theo cuốc
    base = random.randint(5, 10)
    bonus = 0
    inv = dict(db.get_inv(uid))
    bonus += inv.get("cuocgo", 0) * 1
    bonus += inv.get("cuocsat", 0) * 2
    bonus += inv.get("cuocvang", 0) * 5
    bonus += inv.get("cuockimcuong", 0) * 10
    total = base + bonus
    got = _apply_gain_with_buffs(uid, total)
    db.add_exp(uid, 5)
    await owo_typing(ctx)
    await ctx.reply(f"⛏️ Bạn đào được **+{got}** vàng! {random.choice(EMOJIS)}")

# ----- Casino -----
@bot.command(name="cf")
async def kcf(ctx, bet: str):
    if not await _gate(ctx): return
    amt = db.parse_amount(bet)
    if amt is None: return await ctx.reply("❌ Cú pháp: `kcf <cược>` (chỉ số, không dấu).")
    if db.get_gold(ctx.author.id) < amt: return await ctx.reply("❌ Bạn không đủ vàng.")
    await owo_typing(ctx)
    win = random.choice([True, False])
    if win:
        got = _apply_gain_with_buffs(ctx.author.id, amt)
        db.add_exp(ctx.author.id, 5)
        await ctx.reply(f"🪙 THẮNG! Bạn nhận **+{got}** vàng.")
    else:
        db.add_gold(ctx.author.id, -amt)
        db.add_exp(ctx.author.id, 2)
        await ctx.reply(f"🪙 THUA... Bạn mất **-{amt}** vàng.")

SLOT_ICONS = ["💎","🍒","7️⃣","🍋","🔔","⭐"]
@bot.command(name="s")
async def ks(ctx):
    if not await _gate(ctx): return
    uid = ctx.author.id
    db.ensure_user(uid, ctx.author.name)
    # death check
    if random.randint(1,100) <= _effective_death_rate(uid):
        if db.use_item(uid, "khien", 1):
            return await ctx.reply("🛡️ **Khiên** đã cứu bạn khỏi nạn.")
        elif db.use_item(uid, "khien_vip", 1):
            return await ctx.reply("🛡️ **Khiên VIP** đã cứu bạn!")
        else:
            lose = min(db.get_gold(uid), max(0, db.get_gold(uid)//10))
            db.add_gold(uid, -lose); db.add_exp(uid, 2)
            return await ctx.reply(f"💀 Gặp nạn ở máy quay! Mất {lose} vàng.")
    await owo_typing(ctx, 1.0, 2.0)
    r = [random.choice(SLOT_ICONS) for _ in range(3)]
    disp = " | ".join(r)
    if r[0]==r[1]==r[2]:
        got = _apply_gain_with_buffs(uid, random.randint(500, 1500))
        db.add_exp(uid, 10)
        await ctx.reply(f"🎰 [{disp}] — **JACKPOT!** +{got} vàng")
    elif r[0]==r[1] or r[1]==r[2] or r[0]==r[2]:
        got = _apply_gain_with_buffs(uid, random.randint(200, 600))
        db.add_exp(uid, 6)
        await ctx.reply(f"🎰 [{disp}] — Trúng nhỏ +{got} vàng")
    else:
        lose = min(db.get_gold(uid), random.randint(100, 400))
        db.add_gold(uid, -lose); db.add_exp(uid, 3)
        await ctx.reply(f"🎰 [{disp}] — Trượt rồi... -{lose} vàng")

@bot.command(name="bj")
async def kbj(ctx):
    if not await _gate(ctx): return
    uid = ctx.author.id
    db.ensure_user(uid, ctx.author.name)
    if random.randint(1,100) <= _effective_death_rate(uid):
        if db.use_item(uid, "khien", 1):
            return await ctx.reply("🛡️ Khiên đã bảo vệ bạn!")
        elif db.use_item(uid, "khien_vip", 1):
            return await ctx.reply("🛡️ Khiên VIP đã bảo vệ bạn!")
        else:
            lose = min(db.get_gold(uid), max(0, db.get_gold(uid)//10))
            db.add_gold(uid, -lose); db.add_exp(uid, 2)
            return await ctx.reply(f"💀 Xui! Thua bài và mất {lose} vàng.")
    await owo_typing(ctx, 0.8, 1.4)
    outcome = random.random()
    if outcome < 0.45:
        got = _apply_gain_with_buffs(uid, random.randint(300, 900))
        db.add_exp(uid, 8)
        await ctx.reply(f"🃏 Bạn **thắng** ván bài! +{got} vàng")
    elif outcome < 0.9:
        lose = min(db.get_gold(uid), random.randint(200, 600))
        db.add_gold(uid, -lose); db.add_exp(uid, 3)
        await ctx.reply(f"🃏 Thua ván bài... -{lose} vàng")
    else:
        db.add_exp(uid, 4)
        await ctx.reply("🃏 Ván bài **hòa**, không mất gì.")

@bot.command(name="tx")
async def ktx(ctx, bet: str, choice: str):
    if not await _gate(ctx): return
    uid = ctx.author.id
    amt = db.parse_amount(bet)
    if amt is None: return await ctx.reply("❌ Cú pháp: `ktx <cược> t|x`")
    if db.get_gold(uid) < amt: return await ctx.reply("❌ Bạn không đủ vàng.")
    choice = choice.lower()
    if choice not in ("t","x"): return await ctx.reply("❌ Chọn `t` (tài) hoặc `x` (xỉu).")
    await owo_typing(ctx, 0.8, 1.6)
    dice = [random.randint(1,6) for _ in range(3)]
    s = sum(dice)
    if s in (3, 18):
        db.add_gold(uid, -amt); db.add_exp(uid, 3)
        return await ctx.reply(f"🎲 {dice} = **{s}** — Nhà ăn! -{amt} vàng")
    result = "t" if 11 <= s <= 17 else "x"
    if result == choice:
        got = _apply_gain_with_buffs(uid, amt)
        db.add_exp(uid, 6)
        await ctx.reply(f"🎲 {dice} = **{s}** — **THẮNG**! +{got} vàng")
    else:
        db.add_gold(uid, -amt); db.add_exp(uid, 3)
        await ctx.reply(f"🎲 {dice} = **{s}** — Thua... -{amt} vàng")

# ----- Hunt -----
@bot.command(name="hunt")
async def khunt(ctx):
    if not await _gate(ctx): return
    uid = ctx.author.id
    db.ensure_user(uid, ctx.author.name)
    if random.randint(1,100) <= _effective_death_rate(uid):
        if db.use_item(uid, "khien", 1) or db.use_item(uid, "khien_vip", 1):
            return await ctx.reply("🛡️ Khiên đã cứu bạn trong chuyến khám phá.")
        else:
            lose = min(db.get_gold(uid), max(0, db.get_gold(uid)//10))
            db.add_gold(uid, -lose); db.add_exp(uid, 2)
            return await ctx.reply(f"💀 Gặp tai nạn! Mất {lose} vàng.")
    await owo_typing(ctx)
    got = _apply_gain_with_buffs(uid, random.randint(200, 800))
    db.add_exp(uid, 5)
    await ctx.reply(f"🧭 Bạn tìm được **+{got}** vàng khi khám phá!")

# ----- Trade / info -----
@bot.command(name="give")
async def kgive(ctx, member: discord.Member, amount: str):
    if not await _gate(ctx): return
    if member.bot: return await ctx.reply("🤖 Không tặng cho bot.")
    val = db.parse_amount(amount)
    if val is None: return await ctx.reply("❌ Nhập số hợp lệ (không dấu).")
    if db.get_gold(ctx.author.id) < val: return await ctx.reply("❌ Bạn không đủ vàng.")
    await owo_typing(ctx, 0.4, 1.0)
    db.ensure_user(member.id, member.name)
    db.add_gold(ctx.author.id, -val)
    db.add_gold(member.id, val)
    await ctx.reply(f"🎁 Đã tặng {member.mention} **{val}** vàng.")

@bot.command(name="shop")
async def kshop(ctx):
    if not await _gate(ctx): return
    items = db.list_shop()
    lines = [f"- **{n}**: {p} vàng — {d}" for n,p,d in items]
    await ctx.reply("🏪 **Cửa hàng**:\n" + "\n".join(lines) + "\nDùng: `kbuy <item> <số>` hoặc `kdung <item>` (với thuốc)")

@bot.command(name="buy")
async def kbuy(ctx, item: str, qty: str):
    if not await _gate(ctx): return
    n = db.parse_amount(qty)
    if n is None: return await ctx.reply("❌ Nhập số lượng hợp lệ (không dấu).")
    res = db.buy(ctx.author.id, item, n)
    await ctx.reply(res)

@bot.command(name="dung")
async def kdung(ctx, item: str):
    """
    kdung thuoc_x2 | kdung thuoc_giamchet
    """
    if not await _gate(ctx): return
    if item not in ("thuoc_x2", "thuoc_giamchet"):
        return await ctx.reply("❌ Chỉ dùng: `thuoc_x2` hoặc `thuoc_giamchet`.")
    # cần có item trong kho
    if not db.use_item(ctx.author.id, item, 1):
        return await ctx.reply("❌ Bạn không có vật phẩm này trong kho.")
    exp_at = db.activate_buff(ctx.author.id, item)
    left = exp_at - int(time.time())
    await ctx.reply(f"🧪 Đã dùng **{item}**! Hiệu lực **{left}s**.")
    # lên lịch báo hết hạn
    bot.loop.create_task(_schedule_buff_end_notice(ctx, item, left))

@bot.command(name="inv")
async def kinv(ctx):
    if not await _gate(ctx): return
    inv = db.get_inv(ctx.author.id)
    gold = db.get_gold(ctx.author.id)
    buffs = db.get_active_buffs(ctx.author.id)
    lines = [f"💰 Vàng: **{gold}**"]
    if inv:
        lines.append("🎒 **Kho:**")
        for it, q in inv:
            lines.append(f"- {it}: {q}")
    else:
        lines.append("🎒 Kho trống.")
    if buffs:
        lines.append("🧪 **Buff đang hoạt động:**")
        for name, left in buffs.items():
            lines.append(f"- {name}: còn {left}s")
    await ctx.reply("\n".join(lines))

@bot.command(name="top")
async def ktop(ctx):
    if not await _gate(ctx): return
    board = db.top_rich(10)
    if not board: return await ctx.reply("📭 Chưa có dữ liệu.")
    medals = ["🥇","🥈","🥉"]
    out = ["**🏆 Bảng Xếp Hạng**"]
    for i,(name,gold) in enumerate(board, start=1):
        pre = medals[i-1] if i<=3 else f"{i}."
        out.append(f"{pre} **{name}** — {gold}")
    await ctx.reply("\n".join(out))

# ----- Help -----
@bot.command(name="help")
async def khelp(ctx):
    if not await _gate(ctx): return
    msg = (
        "**📖 Lệnh người chơi**\n"
        "`kstart`, `kprofile`, `kdaily`\n"
        "`kfarm` — đào (10s CD, có thể được bật spam)\n"
        "`kshop`, `kbuy <item> <số>`, `kdung <thuoc_x2|thuoc_giamchet>`, `kinv`\n"
        "`kgive @user <số>`, `ktop`\n"
        "`kcf <cược>`, `ks`, `kbj`, `ktx <cược> t|x`\n\n"
        "Lưu ý: chỉ nhập **số thuần** (không dấu chấm/phẩy)."
    )
    await ctx.reply(msg)

@bot.command(name="ad")
async def kad(ctx):
    if not await _gate(ctx): return
    if not _is_admin(ctx.author):
        return await ctx.reply("🚫 Bạn không phải admin.")
    msg = (
        "**🛠 Admin Commands**\n"
        "`kban @user` / `kunban @user`\n"
        "`krs @user` — reset dữ liệu\n"
        "`kaddcoin @user <số>` / `kremovecoin @user <số>`\n"
        "`ksetlv @user <level>`\n"
        "`ksetdeath <percent>`\n"
        "`ksetchannel #kenh` / `kunsetchannel`\n"
        "`kspam @user on|off`\n"
        "`ksetadmin @user on|off` — (chỉ Super Admin)"
    )
    await ctx.reply(msg)

# ===== Admin =====
@bot.command(name="ban")
async def kban(ctx, member: discord.Member):
    if not _is_admin(ctx.author): return await ctx.reply("🚫 Bạn không phải admin.")
    if _is_super_admin(member): return await ctx.reply("❌ Không thể ban Super Admin.")
    db.ensure_user(member.id, member.name); db.set_ban(member.id, True)
    await ctx.reply(f"⛔ Đã ban {member.mention}")

@bot.command(name="unban")
async def kunban(ctx, member: discord.Member):
    if not _is_admin(ctx.author): return await ctx.reply("🚫 Bạn không phải admin.")
    db.ensure_user(member.id, member.name); db.set_ban(member.id, False)
    await ctx.reply(f"✅ Gỡ ban {member.mention}")

@bot.command(name="rs")
async def krs(ctx, member: discord.Member):
    if not _is_admin(ctx.author): return await ctx.reply("🚫 Bạn không phải admin.")
    if _is_super_admin(member): return await ctx.reply("❌ Không thể reset Super Admin.")
    db.ensure_user(member.id, member.name); db.reset_user(member.id)
    await ctx.reply(f"♻️ Đã reset dữ liệu của {member.mention}")

@bot.command(name="addcoin")
async def kaddcoin(ctx, member: discord.Member, amount: str):
    if not _is_admin(ctx.author): return await ctx.reply("🚫 Bạn không phải admin.")
    val = db.parse_amount(amount)
    if val is None: return await ctx.reply("❌ Số không hợp lệ.")
    db.ensure_user(member.id, member.name); db.add_gold(member.id, val)
    await ctx.reply(f"💰 +{val} vàng cho {member.mention}")

@bot.command(name="removecoin")
async def kremovecoin(ctx, member: discord.Member, amount: str):
    if not _is_admin(ctx.author): return await ctx.reply("🚫 Bạn không phải admin.")
    val = db.parse_amount(amount)
    if val is None: return await ctx.reply("❌ Số không hợp lệ.")
    db.ensure_user(member.id, member.name)
    val = min(val, db.get_gold(member.id))
    db.add_gold(member.id, -val)
    await ctx.reply(f"💸 -{val} vàng của {member.mention}")

@bot.command(name="setlv")
async def ksetlv(ctx, member: discord.Member, level: str):
    if not _is_admin(ctx.author): return await ctx.reply("🚫 Bạn không phải admin.")
    lv = db.parse_amount(level)
    if lv is None: return await ctx.reply("❌ Level không hợp lệ.")
    db.ensure_user(member.id, member.name); db.set_level(member.id, lv)
    await ctx.reply(f"🔧 Set level {lv} cho {member.mention}")

@bot.command(name="setadmin")
async def ksetadmin(ctx, member: discord.Member, flag: str):
    if not _is_super_admin(ctx.author):
        return await ctx.reply("🚫 Chỉ **Super Admin** mới được cấp quyền admin.")
    if _is_super_admin(member):
        return await ctx.reply("ℹ️ Super Admin luôn có quyền.")
    on = flag.lower() == "on"
    db.ensure_user(member.id, member.name); db.set_admin(member.id, on)
    await ctx.reply(f"🛠 {member.mention} admin = **{on}**")

@bot.command(name="setdeath")
async def ksetdeath(ctx, percent: str):
    if not _is_admin(ctx.author): return await ctx.reply("🚫 Bạn không phải admin.")
    p = db.parse_amount(percent)
    if p is None: return await ctx.reply("❌ Nhập phần trăm hợp lệ (0-100).")
    if p > 100: p = 100
    db.set_death_rate(p)
    await ctx.reply(f"💀 Death rate = **{p}%**")

@bot.command(name="setchannel")
async def ksetchannel(ctx, ch: discord.TextChannel | None = None):
    if not _is_admin(ctx.author): return await ctx.reply("🚫 Bạn không phải admin.")
    target = ch.id if ch else ctx.channel.id
    db.set_allowed_channel_id(target)
    await ctx.reply(f"🔒 Bot chỉ hoạt động trong kênh: <#{target}>")

@bot.command(name="unsetchannel")
async def kunsetchannel(ctx):
    if not _is_admin(ctx.author): return await ctx.reply("🚫 Bạn không phải admin.")
    db.set_allowed_channel_id(None)
    await ctx.reply("🔓 Đã bỏ giới hạn kênh.")

@bot.command(name="spam")
async def kspam(ctx, member: discord.Member, flag: str):
    if not _is_admin(ctx.author): return await ctx.reply("🚫 Bạn không phải admin.")
    on = flag.lower() == "on"
    db.ensure_user(member.id, member.name)
    db.set_can_spam(member.id, on)
    await ctx.reply(f"⚡ Spam farm cho {member.mention} = **{on}**")

# ===== Run =====
if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ Thiếu DISCORD_TOKEN env.")
    bot.run(TOKEN)
