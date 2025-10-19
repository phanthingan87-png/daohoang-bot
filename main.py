# main.py — V7: giữ lệnh cũ + farm 1 lần + bonus hiển thị + daily giảm + cướp vàng + kienbao + buffs + admin tier
import os, random, asyncio, time
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

import daohoang as db

# ========= Keep-alive =========
app = Flask(__name__)
@app.route("/")
def home():
    return "✅ DaoHoang V7 running"

def _run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=_run_web, daemon=True).start()

# ========= Discord =========
TOKEN = os.getenv("DISCORD_TOKEN")
SUPER_ADMIN_NAME = "sr.nguoihanhtinh_vnvodich"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="k", intents=intents, help_command=None)

EMOJIS = ["😼","🐾","💥","✨","💎","🔥","🪙","⚒️","🎲","🎰","🛡️","🏝️"]

async def owo(ctx, a=0.5, b=1.5):
    async with ctx.typing():
        await asyncio.sleep(random.uniform(a, b))

db.setup_database()

# ========= Helpers =========
def _is_super_admin(m: discord.Member) -> bool:
    return (m.name == SUPER_ADMIN_NAME)

def _is_admin(m: discord.Member) -> bool:
    return _is_super_admin(m) or db.is_admin(m.id)

def _channel_ok(channel_id: int) -> bool:
    allowed = db.get_allowed_channel_id()
    return (allowed is None) or (allowed == channel_id)

async def _gate(ctx) -> bool:
    if not _channel_ok(ctx.channel.id):
        await ctx.reply("🚫 Bot chỉ hoạt động trong kênh đã set bằng `ksetchannel`.")
        return False
    if db.is_banned(ctx.author.id) and not _is_super_admin(ctx.author):
        await ctx.reply("⛔ Bạn đã bị ban.")
        return False
    return True

def _eff_death(uid: int) -> int:
    base = db.get_death_rate()
    buffs = db.get_active_buffs(uid)
    return max(0, base // 2) if "thuoc_giamchet" in buffs else base

def _gain(uid: int, amount: int) -> int:
    buffs = db.get_active_buffs(uid)
    val = amount * 2 if ("thuoc_x2" in buffs and amount > 0) else amount
    db.add_gold(uid, val)
    return val

async def _buff_end_notice(ctx, buff_name: str, seconds: int):
    try:
        await asyncio.sleep(seconds)
        db.clear_expired_buffs(ctx.author.id)
        if buff_name not in db.get_active_buffs(ctx.author.id):
            await ctx.reply(f"⏰ Thuốc **{buff_name}** đã hết hiệu lực.")
    except Exception:
        pass

# ========= Events =========
@bot.event
async def on_ready():
    print(f"✅ Online: {bot.user} | Guilds: {len(bot.guilds)}")

# ========= Player =========
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
    await owo(ctx, 0.3, 0.8)
    await ctx.reply(f"📜 **{user.display_name}** — 💰 {gold} vàng.")

@bot.command(name="daily")
async def kdaily(ctx):
    if not await _gate(ctx): return
    db.ensure_user(ctx.author.id, ctx.author.name)
    if not db.can_daily(ctx.author.id):
        return await ctx.reply("🕒 Hôm nay bạn nhận **daily** rồi!")
    reward = random.randint(200, 800)  # giảm thưởng daily
    got = _gain(ctx.author.id, reward)
    db.set_daily_today(ctx.author.id)
    db.add_exp(ctx.author.id, 10)
    await owo(ctx)
    await ctx.reply(f"🎁 Daily: **+{got}** vàng")

@bot.command(name="farm")
async def kfarm(ctx):
    if not await _gate(ctx): return
    uid = ctx.author.id
    db.ensure_user(uid, ctx.author.name)

    # Cooldown 10s (bị bỏ qua nếu spam ON hoặc SuperAdmin)
    if not db.get_can_spam(uid) and not _is_super_admin(ctx.author):
        last = db.get_last_farm_ts(uid)
        now = int(time.time())
        if now - last < 10:
            return await ctx.reply(f"⏳ Đợi {10 - (now - last)}s nữa nhé.")
        db.set_last_farm_now(uid)

    # Death check
    if random.randint(1, 100) <= _eff_death(uid):
        if db.use_item(uid, "khien", 1):
            return await ctx.reply("🛡️ **Khiên** đã cứu bạn. Không mất gì!")
        elif db.use_item(uid, "khien_vip", 1):
            return await ctx.reply("🛡️ **Khiên VIP** đã cứu bạn!")
        else:
            lose = min(db.get_gold(uid), max(0, db.get_gold(uid)//10))
            db.add_gold(uid, -lose); db.add_exp(uid, 2)
            return await ctx.reply(f"💀 Xui quá! Bạn gặp nạn và mất {lose} vàng.")

    # 5-10 + bonus cuốc (hiển thị bonus rõ)
    base = random.randint(5, 10)
    inv = dict(db.get_inv(uid))
    bonus = inv.get("cuocgo", 0)*1 + inv.get("cuocsat", 0)*2 + inv.get("cuocvang", 0)*5 + inv.get("cuockimcuong", 0)*10
    total = base + bonus
    got = _gain(uid, total)
    db.add_exp(uid, 5)
    await owo(ctx)
    await ctx.reply(f"⛏️ Bạn đào được **+{got}** vàng (bonus +{bonus}).")

# ---- Casino (vẫn hoạt động, không đưa vào help) ----
@bot.command(name="cf")
async def kcf(ctx, bet: str):
    if not await _gate(ctx): return
    amt = db.parse_amount(bet)
    if amt is None: return await ctx.reply("❌ Cú pháp: `kcf <cược>` (chỉ số, không dấu).")
    if db.get_gold(ctx.author.id) < amt: return await ctx.reply("❌ Bạn không đủ vàng.")
    await owo(ctx)
    win = random.choice([True, False])
    if win:
        got = _gain(ctx.author.id, amt); db.add_exp(ctx.author.id, 5)
        await ctx.reply(f"🪙 THẮNG! +{got} vàng")
    else:
        db.add_gold(ctx.author.id, -amt); db.add_exp(ctx.author.id, 2)
        await ctx.reply(f"🪙 THUA... -{amt} vàng")

SLOT_ICONS = ["💎","🍒","7️⃣","🍋","🔔","⭐"]
@bot.command(name="s")
async def ks(ctx):
    if not await _gate(ctx): return
    uid = ctx.author.id
    db.ensure_user(uid, ctx.author.name)
    if random.randint(1,100) <= _eff_death(uid):
        if db.use_item(uid, "khien", 1) or db.use_item(uid, "khien_vip", 1):
            return await ctx.reply("🛡️ Khiên đã cứu bạn!")
        lose = min(db.get_gold(uid), max(0, db.get_gold(uid)//10))
        db.add_gold(uid, -lose); db.add_exp(uid, 2)
        return await ctx.reply(f"💀 Gặp nạn ở máy quay! Mất {lose} vàng.")
    await owo(ctx, 1.0, 2.0)
    r = [random.choice(SLOT_ICONS) for _ in range(3)]
    disp = " | ".join(r)
    if r[0]==r[1]==r[2]:
        got = _gain(uid, random.randint(500, 1500)); db.add_exp(uid, 10)
        await ctx.reply(f"🎰 [{disp}] — **JACKPOT!** +{got} vàng")
    elif r[0]==r[1] or r[1]==r[2] or r[0]==r[2]:
        got = _gain(uid, random.randint(200, 600)); db.add_exp(uid, 6)
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
    if random.randint(1,100) <= _eff_death(uid):
        if db.use_item(uid, "khien", 1) or db.use_item(uid, "khien_vip", 1):
            return await ctx.reply("🛡️ Khiên đã bảo vệ bạn!")
        lose = min(db.get_gold(uid), max(0, db.get_gold(uid)//10))
        db.add_gold(uid, -lose); db.add_exp(uid, 2)
        return await ctx.reply(f"💀 Xui! Thua bài và mất {lose} vàng.")
    await owo(ctx, 0.8, 1.4)
    outcome = random.random()
    if outcome < 0.45:
        got = _gain(uid, random.randint(300, 900)); db.add_exp(uid, 8)
        await ctx.reply(f"🃏 Bạn **thắng**! +{got} vàng")
    elif outcome < 0.9:
        lose = min(db.get_gold(uid), random.randint(200, 600))
        db.add_gold(uid, -lose); db.add_exp(uid, 3)
        await ctx.reply(f"🃏 Thua... -{lose} vàng")
    else:
        db.add_exp(uid, 4)
        await ctx.reply("🃏 Hòa, không mất gì.")

@bot.command(name="tx")
async def ktx(ctx, bet: str, choice: str):
    if not await _gate(ctx): return
    uid = ctx.author.id
    amt = db.parse_amount(bet)
    if amt is None: return await ctx.reply("❌ Cú pháp: `ktx <cược> t|x`.")
    if db.get_gold(uid) < amt: return await ctx.reply("❌ Bạn không đủ vàng.")
    choice = choice.lower()
    if choice not in ("t","x"): return await ctx.reply("❌ Chọn `t` (tài) hoặc `x` (xỉu).")
    await owo(ctx, 0.8, 1.6)
    dice = [random.randint(1,6) for _ in range(3)]
    s = sum(dice)
    if s in (3, 18):
        db.add_gold(uid, -amt); db.add_exp(uid, 3)
        return await ctx.reply(f"🎲 {dice} = **{s}** — Nhà ăn! -{amt} vàng")
    result = "t" if 11 <= s <= 17 else "x"
    if result == choice:
        got = _gain(uid, amt); db.add_exp(uid, 6)
        await ctx.reply(f"🎲 {dice} = **{s}** — **THẮNG**! +{got} vàng")
    else:
        db.add_gold(uid, -amt); db.add_exp(uid, 3)
        await ctx.reply(f"🎲 {dice} = **{s}** — Thua... -{amt} vàng")

# ---- Hunt ----
@bot.command(name="hunt")
async def khunt(ctx):
    if not await _gate(ctx): return
    uid = ctx.author.id
    db.ensure_user(uid, ctx.author.name)
    if random.randint(1,100) <= _eff_death(uid):
        if db.use_item(uid, "khien", 1) or db.use_item(uid, "khien_vip", 1):
            return await ctx.reply("🛡️ Khiên đã cứu bạn.")
        lose = min(db.get_gold(uid), max(0, db.get_gold(uid)//10))
        db.add_gold(uid, -lose); db.add_exp(uid, 2)
        return await ctx.reply(f"💀 Gặp tai nạn! Mất {lose} vàng.")
    await owo(ctx)
    got = _gain(uid, random.randint(200, 800)); db.add_exp(uid, 5)
    await ctx.reply(f"🧭 Bạn tìm được **+{got}** vàng khi khám phá!")

# ---- Rob (NEW) ----
ROB_COST = 10000
ROB_CD = 600  # 10 phút
ROB_SUCCESS = 70  # %

@bot.command(name="cuop")
async def kcuop(ctx, target: discord.Member):
    if not await _gate(ctx): return
    robber = ctx.author
    victim = target
    if victim.bot: return await ctx.reply("🤖 Không thể cướp bot.")
    if robber.id == victim.id: return await ctx.reply("❌ Không thể tự cướp chính mình.")
    db.ensure_user(robber.id, robber.name)
    db.ensure_user(victim.id, victim.name)

    # Kiểm tra tiền cướp
    if db.get_gold(robber.id) < ROB_COST:
        return await ctx.reply(f"❌ Bạn cần ít nhất {ROB_COST} vàng để cướp.")
    # Cooldown
    now = int(time.time())
    last = db.get_last_rob_ts(robber.id)
    if now - last < ROB_CD:
        return await ctx.reply(f"⏳ Bạn phải đợi {ROB_CD - (now - last)}s nữa mới được cướp lần tiếp theo.")
    db.set_last_rob_now(robber.id)

    # Tính tỉ lệ thành công (kienbao nạn nhân giảm 50% 1 lần)
    success_rate = ROB_SUCCESS
    kienbao_used = False
    inv_victim = dict(db.get_inv(victim.id))
    if inv_victim.get("kienbao", 0) > 0:
        # tiêu hao ngay khi bị nhắm tới
        if db.use_item(victim.id, "kienbao", 1):
            success_rate = max(0, success_rate // 2)  # 70% -> 35%
            kienbao_used = True

    # Trừ phí cướp trước
    db.add_gold(robber.id, -ROB_COST)

    await owo(ctx, 0.8, 1.6)
    roll = random.randint(1, 100)
    if roll <= success_rate:
        # Thành công: cướp 20-40% vàng hiện có của nạn nhân
        vic_gold = db.get_gold(victim.id)
        if vic_gold <= 0:
            return await ctx.reply(f"🕳️ {victim.mention} không có vàng để cướp. Bạn mất phí {ROB_COST} vàng.")
        percent = random.randint(20, 40)
        steal = max(1, (vic_gold * percent) // 100)
        db.add_gold(victim.id, -steal)
        db.add_gold(robber.id, steal)
        db.add_exp(robber.id, 10)
        note = " (nạn nhân đã dùng *kienbao*, tỉ lệ cướp bị giảm 50%)" if kienbao_used else ""
        await ctx.reply(f"⚔️ CƯỚP THÀNH CÔNG! Bạn lấy **{steal}** vàng từ {victim.mention}.{note}")
    else:
        # Thất bại: mất 10,000 (đã trừ trước)
        db.add_exp(robber.id, 2)
        note = " (nạn nhân đã dùng *kienbao*, tỉ lệ cướp bị giảm 50%)" if kienbao_used else ""
        await ctx.reply(f"💢 CƯỚP THẤT BẠI! Bạn mất phí **{ROB_COST}** vàng.{note}")

# ---- Trade / Info ----
@bot.command(name="give")
async def kgive(ctx, member: discord.Member, amount: str):
    if not await _gate(ctx): return
    if member.bot: return await ctx.reply("🤖 Không tặng cho bot.")
    val = db.parse_amount(amount)
    if val is None: return await ctx.reply("❌ Nhập số hợp lệ (không dấu).")
    if db.get_gold(ctx.author.id) < val: return await ctx.reply("❌ Bạn không đủ vàng.")
    await owo(ctx, 0.4, 1.0)
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
    # kdung thuoc_x2 | kdung thuoc_giamchet
    if not await _gate(ctx): return
    if item not in ("thuoc_x2", "thuoc_giamchet"):
        return await ctx.reply("❌ Chỉ dùng: `thuoc_x2` hoặc `thuoc_giamchet`.")
    if not db.use_item(ctx.author.id, item, 1):
        return await ctx.reply("❌ Bạn không có vật phẩm này.")
    exp_at = db.activate_buff(ctx.author.id, item)
    left = exp_at - int(time.time())
    await ctx.reply(f"🧪 Đã dùng **{item}**! Hiệu lực {left}s.")
    bot.loop.create_task(_buff_end_notice(ctx, item, left))

@bot.command(name="inv")
async def kinv(ctx):
    if not await _gate(ctx): return
    inv = db.get_inv(ctx.author.id)
    gold = db.get_gold(ctx.author.id)
    buffs = db.get_active_buffs(ctx.author.id)
    lines = [f"💰 Vàng: **{gold}**"]
    if inv:
        lines.append("🎒 **Kho:**")
        for it,q in inv:
            lines.append(f"- {it}: {q}")
    else:
        lines.append("🎒 Kho trống.")
    if buffs:
        lines.append("🧪 **Buff đang hoạt động:**")
        for name,left in buffs.items():
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

# ---- Help (Ẩn cờ bạc) ----
@bot.command(name="help")
async def khelp(ctx):
    if not await _gate(ctx): return
    msg = (
        "**📖 Lệnh người chơi**\n"
        "`kstart`, `kprofile`, `kdaily`\n"
        "`kfarm` — đào (CD 10s)\n"
        "`kshop`, `kbuy <item> <số>`, `kdung <thuoc_x2|thuoc_giamchet>`, `kinv`\n"
        "`kgive @user <số>`, `ktop`\n"
        "`kcuop @user` — tốn 10000 vàng, 70% thành công, CD 10 phút\n"
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

# ========= Admin =========
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

# ========= RUN =========
if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ Thiếu DISCORD_TOKEN env.")
    bot.run(TOKEN)
