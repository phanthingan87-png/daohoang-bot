# main.py — Bot full casino + admin + OWO + keep-alive + channel lock
import os, random, asyncio
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

import daohoang as db

# ========== Keep-alive (Render) ==========
app = Flask(__name__)
@app.route("/")
def home():
    return "✅ Đảo Hoang Casino v4 đang chạy!"

def _run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=_run_web, daemon=True).start()

# ========== Discord ==========
TOKEN = os.getenv("DISCORD_TOKEN")
SUPER_ADMINS = set()  # có thể điền ID admin cứng nếu muốn: {1234567890, ...}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="k", intents=intents, help_command=None)

# OWO effects
EMOJIS = ["😼","🐾","💥","✨","💎","🔥","🪙","⚒️","🎲","🎰","🛡️","🏝️"]
async def owo_typing(ctx, a=0.6, b=1.6):
    async with ctx.typing():
        await asyncio.sleep(random.uniform(a, b))

db.setup_database()

# ====== helpers ======
def _is_admin(uid: int) -> bool:
    return uid in SUPER_ADMINS or db.is_admin(uid)

def _channel_locked_ok(channel_id: int) -> bool:
    allowed = db.get_allowed_channel_id()
    return (allowed is None) or (allowed == channel_id)

async def _check_gate(ctx) -> bool:
    if not _channel_locked_ok(ctx.channel.id):
        await ctx.reply("🚫 Bot chỉ hoạt động trong kênh đã được set bằng `ksetchannel`.")
        return False
    if db.is_banned(ctx.author.id):
        await ctx.reply("⛔ Bạn đã bị ban.")
        return False
    return True

# ========== Events ==========
@bot.event
async def on_ready():
    print(f"✅ Online: {bot.user} | Guilds: {len(bot.guilds)}")

# ========== Player Commands ==========
@bot.command(name="start")
async def start(ctx):
    if not await _check_gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    await ctx.reply(f"🏝️ Chào **{ctx.author.display_name}**! Tài khoản đã sẵn sàng. Dùng `khelp` để xem lệnh.")

@bot.command(name="profile")
async def profile(ctx, member: discord.Member | None = None):
    if not await _check_gate(ctx): return
    user = member or ctx.author
    db.ensure_user(user.id, user.name)
    gold = db.get_gold(user.id)
    # lấy level/exp cho vui
    await owo_typing(ctx, 0.3, 0.8)
    await ctx.reply(f"📜 **{user.display_name}** — 💰 {gold} vàng.")

@bot.command(name="daily")
async def daily(ctx):
    if not await _check_gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    if not db.can_daily(ctx.author.id):
        return await ctx.reply("🕒 Hôm nay bạn nhận daily rồi, quay lại ngày mai nhé!")
    reward = random.randint(1000, 3000)
    db.add_gold(ctx.author.id, reward)
    db.set_daily_today(ctx.author.id)
    await owo_typing(ctx)
    await ctx.reply(f"🎉 Daily: +{reward} vàng {random.choice(EMOJIS)}")

# ----- Casino: Coin Flip (kcf) -----
@bot.command(name="cf")
async def kcf(ctx, bet: str):
    if not await _check_gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    amt = db.parse_amount(bet)
    if amt is None: return await ctx.reply("❌ Cú pháp: `kcf <cược>` (chỉ số, không dấu).")
    if db.get_gold(ctx.author.id) < amt: return await ctx.reply("❌ Bạn không đủ vàng để cược.")
    await owo_typing(ctx)
    side = random.choice(["thắng","thua"])
    if side == "thắng":
        db.add_gold(ctx.author.id, amt)
        await ctx.reply(f"🪙 Tung đồng xu: **THẮNG**! +{amt} vàng {random.choice(EMOJIS)}")
    else:
        db.add_gold(ctx.author.id, -amt)
        await ctx.reply(f"🪙 Tung đồng xu: **THUA**... -{amt} vàng {random.choice(EMOJIS)}")

# ----- Casino: Slot (ks) -----
SLOT_ICONS = ["💎","🍒","7️⃣","🍋","🔔","⭐"]
@bot.command(name="ks")
async def ks(ctx):
    if not await _check_gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    # Áp dụng death chance
    if random.randint(1,100) <= db.get_death_rate():
        # thử dùng khiên
        if db.use_item(ctx.author.id, "khien", 1):
            await ctx.reply("🛡️ Gặp nạn nhưng **khiên** đã cứu bạn. Không mất gì!")
        else:
            lose = max(0, db.get_gold(ctx.author.id) // 10)
            db.add_gold(ctx.author.id, -lose)
            return await ctx.reply(f"💀 Xui quá! Bạn gặp nạn và mất {lose} vàng.")
    # slot
    await owo_typing(ctx, 1.0, 2.0)
    r = [random.choice(SLOT_ICONS) for _ in range(3)]
    display = " | ".join(r)
    if r[0] == r[1] == r[2]:
        win = random.randint(500, 1500)
        db.add_gold(ctx.author.id, win)
        await ctx.reply(f"🎰 [{display}] — **JACKPOT!** +{win} vàng {random.choice(EMOJIS)}")
    elif (r[0] == r[1]) or (r[1] == r[2]) or (r[0] == r[2]):
        win = random.randint(200, 600)
        db.add_gold(ctx.author.id, win)
        await ctx.reply(f"🎰 [{display}] — Trúng nhỏ +{win} vàng {random.choice(EMOJIS)}")
    else:
        lose = random.randint(100, 400)
        lose = min(lose, db.get_gold(ctx.author.id))
        db.add_gold(ctx.author.id, -lose)
        await ctx.reply(f"🎰 [{display}] — Trượt rồi... -{lose} vàng")

# ----- Casino: “Tiến lên” giả lập (kbj) -----
@bot.command(name="kbj")
async def kbj(ctx):
    if not await _check_gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    # Death check
    if random.randint(1,100) <= db.get_death_rate():
        if db.use_item(ctx.author.id, "khien", 1):
            await ctx.reply("🛡️ Khiên đã bảo vệ bạn khỏi tai nạn.")
        else:
            lose = max(0, db.get_gold(ctx.author.id) // 10)
            db.add_gold(ctx.author.id, -lose)
            return await ctx.reply(f"💀 Gặp nạn khi đánh bài! Mất {lose} vàng.")
    await owo_typing(ctx, 0.8, 1.4)
    outcome = random.random()
    if outcome < 0.45:
        win = random.randint(300, 900)
        db.add_gold(ctx.author.id, win)
        await ctx.reply(f"🃏 Bạn **thắng** ván bài! +{win} vàng {random.choice(EMOJIS)}")
    elif outcome < 0.9:
        lose = random.randint(200, 600)
        lose = min(lose, db.get_gold(ctx.author.id))
        db.add_gold(ctx.author.id, -lose)
        await ctx.reply(f"🃏 Thua ván bài... -{lose} vàng")
    else:
        await ctx.reply("🃏 Ván bài hòa, không mất gì.")

# ----- Tài xỉu (ktx <cược> t|x) -----
@bot.command(name="ktx")
async def ktx(ctx, bet: str, choice: str):
    if not await _check_gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    amt = db.parse_amount(bet)
    if amt is None: return await ctx.reply("❌ Cú pháp: `ktx <cược> t|x` (t=tài, x=xỉu, chỉ số).")
    if db.get_gold(ctx.author.id) < amt: return await ctx.reply("❌ Bạn không đủ vàng.")
    choice = choice.lower()
    if choice not in ("t","x"):
        return await ctx.reply("❌ Chọn `t` (tài) hoặc `x` (xỉu).")
    await owo_typing(ctx, 0.8, 1.6)
    dice = [random.randint(1,6) for _ in range(3)]
    s = sum(dice)
    # 3/18 = nhà ăn (thua)
    house = (s == 3 or s == 18)
    result = "t" if 11 <= s <= 17 else "x"  # 4-10 xỉu, 11-17 tài
    if house:
        db.add_gold(ctx.author.id, -amt)
        return await ctx.reply(f"🎲 Kết quả {dice} = **{s}** — Nhà ăn! -{amt} vàng")
    if choice == result:
        db.add_gold(ctx.author.id, amt)
        await ctx.reply(f"🎲 {dice} = **{s}** — Bạn **THẮNG**! +{amt} vàng {random.choice(EMOJIS)}")
    else:
        db.add_gold(ctx.author.id, -amt)
        await ctx.reply(f"🎲 {dice} = **{s}** — Bạn thua... -{amt} vàng")

# ----- Khám phá đơn giản -----
@bot.command(name="hunt")
async def hunt(ctx):
    if not await _check_gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    if random.randint(1,100) <= db.get_death_rate():
        if db.use_item(ctx.author.id, "khien", 1):
            await ctx.reply("🛡️ Khiên đã cứu bạn trong chuyến khám phá.")
        else:
            lose = max(0, db.get_gold(ctx.author.id) // 10)
            db.add_gold(ctx.author.id, -lose)
            return await ctx.reply(f"💀 Gặp tai nạn! Mất {lose} vàng.")
    await owo_typing(ctx)
    gain = random.randint(200, 800)
    db.add_gold(ctx.author.id, gain)
    await ctx.reply(f"🧭 Bạn tìm được **+{gain}** vàng khi khám phá! {random.choice(EMOJIS)}")

# ----- Giao dịch -----
@bot.command(name="give")
async def give(ctx, member: discord.Member, amount: str):
    if not await _check_gate(ctx): return
    if member.bot: return await ctx.reply("🤖 Không tặng cho bot.")
    db.ensure_user(ctx.author.id, ctx.author.name)
    db.ensure_user(member.id, member.name)
    val = db.parse_amount(amount)
    if val is None: return await ctx.reply("❌ Nhập số hợp lệ (không dấu).")
    if db.get_gold(ctx.author.id) < val: return await ctx.reply("❌ Bạn không đủ vàng.")
    await owo_typing(ctx, 0.4, 1.0)
    db.add_gold(ctx.author.id, -val)
    db.add_gold(member.id, val)
    await ctx.reply(f"🎁 Đã tặng {member.mention} **{val}** vàng.")

# ----- Shop / Inventory -----
@bot.command(name="shop")
async def shop(ctx):
    if not await _check_gate(ctx): return
    lines = []
    for name, (price, desc) in db.SHOP_ITEMS.items():
        lines.append(f"- **{name}**: {price} vàng — {desc}")
    await ctx.reply("🏪 **Cửa hàng**:\n" + "\n".join(lines) + "\nDùng: `kbuy <item> <số>`")

@bot.command(name="buy")
async def buy(ctx, item: str, qty: str):
    if not await _check_gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    n = db.parse_amount(qty)
    if n is None: return await ctx.reply("❌ Nhập số lượng hợp lệ (không dấu).")
    res = db.buy(ctx.author.id, item, n)
    await ctx.reply(res)

@bot.command(name="inv")
async def kinv(ctx):
    if not await _check_gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    inv = db.get_inv(ctx.author.id)
    gold = db.get_gold(ctx.author.id)
    if not inv:
        return await ctx.reply(f"🎒 Kho trống. Bạn có **{gold}** vàng.")
    lines = [f"💰 Vàng: **{gold}**"]
    for it, q in inv:
        lines.append(f"- {it}: {q}")
    await ctx.reply("🎒 **Kho của bạn:**\n" + "\n".join(lines))

# ----- Top -----
@bot.command(name="top")
async def ktop(ctx):
    if not await _check_gate(ctx): return
    board = db.top_rich(10)
    if not board: return await ctx.reply("📭 Chưa có dữ liệu.")
    out = ["**🏆 Bảng Xếp Hạng**"]
    medals = ["🥇","🥈","🥉"]
    for i, (name, gold) in enumerate(board, start=1):
        prefix = medals[i-1] if i <= 3 else f"{i}."
        out.append(f"{prefix} **{name}** — {gold}")
    await ctx.reply("\n".join(out))

# ----- Help -----
@bot.command(name="help")
async def help_cmd(ctx):
    if not await _check_gate(ctx): return
    msg = (
        "**📖 Lệnh người chơi**\n"
        "`kstart`, `kprofile`, `kdaily`\n"
        "`kcf <cược>` — tung đồng xu\n"
        "`ks` — slot máy quay\n"
        "`kbj` — bài vui\n"
        "`ktx <cược> t|x` — tài/xỉu\n"
        "`khunt` — khám phá\n"
        "`kgive @user <số>` — tặng vàng\n"
        "`kshop`, `kbuy <item> <số>`, `kinv`\n"
        "`ktop` — bảng xếp hạng\n\n"
        "**🛠 Admin**\n"
        "`kban @user` / `kunban @user`\n"
        "`krs @user` — reset\n"
        "`kaddcoin @user <coin>` / `kremovecoin @user <coin>`\n"
        "`ksetlv @user <level>` / `ksetadmin @user <on|off>`\n"
        "`ksetdeath <percent>`\n"
        "`ksetchannel #kenh` / `kunsetchannel`\n"
        "_Lưu ý: chỉ nhập **số thuần** (không dấu chấm/phẩy)._"
    )
    await ctx.reply(msg)

# ========== Admin Commands ==========
@bot.command(name="ban")
async def kban(ctx, member: discord.Member):
    if not _is_admin(ctx.author.id): return await ctx.reply("🚫 Bạn không phải admin.")
    db.ensure_user(member.id, member.name); db.ban_user(member.id, True)
    await ctx.reply(f"⛔ Đã ban {member.mention}")

@bot.command(name="unban")
async def kunban(ctx, member: discord.Member):
    if not _is_admin(ctx.author.id): return await ctx.reply("🚫 Bạn không phải admin.")
    db.ensure_user(member.id, member.name); db.ban_user(member.id, False)
    await ctx.reply(f"✅ Gỡ ban {member.mention}")

@bot.command(name="rs")
async def krs(ctx, member: discord.Member):
    if not _is_admin(ctx.author.id): return await ctx.reply("🚫 Bạn không phải admin.")
    db.ensure_user(member.id, member.name); db.reset_user(member.id)
    await ctx.reply(f"♻️ Đã reset dữ liệu của {member.mention}")

@bot.command(name="addcoin")
async def kaddcoin(ctx, member: discord.Member, amount: str):
    if not _is_admin(ctx.author.id): return await ctx.reply("🚫 Bạn không phải admin.")
    val = db.parse_amount(amount)
    if val is None: return await ctx.reply("❌ Nhập số hợp lệ (không dấu).")
    db.ensure_user(member.id, member.name); db.add_gold(member.id, val)
    await ctx.reply(f"💰 Đã cộng **{val}** vàng cho {member.mention}")

@bot.command(name="removecoin")
async def kremovecoin(ctx, member: discord.Member, amount: str):
    if not _is_admin(ctx.author.id): return await ctx.reply("🚫 Bạn không phải admin.")
    val = db.parse_amount(amount)
    if val is None: return await ctx.reply("❌ Nhập số hợp lệ (không dấu).")
    db.ensure_user(member.id, member.name)
    val = min(val, db.get_gold(member.id))
    db.add_gold(member.id, -val)
    await ctx.reply(f"💸 Đã trừ **{val}** vàng của {member.mention}")

@bot.command(name="setlv")
async def ksetlv(ctx, member: discord.Member, level: str):
    if not _is_admin(ctx.author.id): return await ctx.reply("🚫 Bạn không phải admin.")
    lv = db.parse_amount(level)
    if lv is None: return await ctx.reply("❌ Level không hợp lệ.")
    db.ensure_user(member.id, member.name); db.set_level(member.id, lv)
    await ctx.reply(f"🔧 Đã set level {lv} cho {member.mention}")

@bot.command(name="setadmin")
async def ksetadmin(ctx, member: discord.Member, flag: str):
    if not _is_admin(ctx.author.id): return await ctx.reply("🚫 Bạn không phải admin.")
    on = flag.lower() == "on"
    db.ensure_user(member.id, member.name); db.set_admin(member.id, on)
    await ctx.reply(f"🛠 {member.mention} admin = **{on}**")

@bot.command(name="setdeath")
async def ksetdeath(ctx, percent: str):
    if not _is_admin(ctx.author.id): return await ctx.reply("🚫 Bạn không phải admin.")
    p = db.parse_amount(percent)
    if p is None: return await ctx.reply("❌ Nhập % hợp lệ (0-100, số thuần).")
    if p > 100: p = 100
    db.set_death_rate(p)
    await ctx.reply(f"💀 Death rate đã set = **{p}%**")

@bot.command(name="setchannel")
async def ksetchannel(ctx, ch: discord.TextChannel | None = None):
    if not _is_admin(ctx.author.id): return await ctx.reply("🚫 Bạn không phải admin.")
    target = ch.id if ch else ctx.channel.id
    db.set_allowed_channel_id(target)
    await ctx.reply(f"🔒 Bot chỉ hoạt động trong kênh: <#{target}>")

@bot.command(name="unsetchannel")
async def kunsetchannel(ctx):
    if not _is_admin(ctx.author.id): return await ctx.reply("🚫 Bạn không phải admin.")
    db.set_allowed_channel_id(None)
    await ctx.reply("🔓 Đã bỏ giới hạn kênh. Bot hoạt động ở mọi kênh.")

# ========== Run ==========
if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ Thiếu DISCORD_TOKEN env.")
    bot.run(TOKEN)
