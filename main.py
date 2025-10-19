# main.py — Bot đầy đủ + hiệu ứng “owo style” + keep-alive
import os
import random
import asyncio
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

import daohoang as db

# ======= Keep-alive cho Render (web service) =======
app = Flask(__name__)
@app.route("/")
def home():
    return "✅ Đảo Hoang Bot đang chạy!"

def _run_web():
    app.run(host="0.0.0.0", port=8080)

Thread(target=_run_web, daemon=True).start()

# ======= Discord setup =======
TOKEN = os.getenv("DISCORD_TOKEN")
intents = discord.Intents.default()
intents.message_content = True

# Tắt help mặc định để dùng help custom
bot = commands.Bot(command_prefix="k", intents=intents, help_command=None)

# Emoji & hiệu ứng
OWO_EMOJIS = ["😼", "🐾", "💥", "✨", "💎", "🔥", "🪙", "⚒️"]
async def owo_typing(ctx, min_s=0.8, max_s=1.8):
    async with ctx.typing():
        await asyncio.sleep(random.uniform(min_s, max_s))

# ======= Khởi tạo DB =======
db.setup_database()

@bot.event
async def on_ready():
    print(f"✅ Bot đã đăng nhập thành công: {bot.user} (Guilds: {len(bot.guilds)})")

# ======= Lệnh cơ bản =======
@bot.command(name="start")
async def start(ctx: commands.Context):
    db.ensure_user(ctx.author.id, ctx.author.name)
    await ctx.reply(f"🏝️ Xin chào **{ctx.author.name}**! Tài khoản của bạn đã sẵn sàng. Gõ `khelp` để xem lệnh.")

@bot.command(name="profile")
async def profile(ctx: commands.Context, member: discord.Member | None = None):
    user = member or ctx.author
    db.ensure_user(user.id, user.name)
    gold = db.get_gold(user.id)
    await ctx.reply(f"📜 **{user.display_name}** đang có **💰 {db.fmt_vn(gold)}** vàng.")

@bot.command(name="daily")
async def daily(ctx: commands.Context):
    db.ensure_user(ctx.author.id, ctx.author.name)
    if not db.can_daily(ctx.author.id):
        return await ctx.reply("🕒 Bạn đã nhận **daily** hôm nay rồi. Hẹn bạn ngày mai nhé!")
    reward = random.randint(1_000, 3_000)
    db.add_gold(ctx.author.id, reward)
    db.set_daily_today(ctx.author.id)
    await owo_typing(ctx)
    await ctx.reply(f"🎉 Daily hôm nay: **+{db.fmt_vn(reward)}** vàng! {random.choice(OWO_EMOJIS)}")

# ======= Lệnh cày kiểu OWO =======
@bot.command(name="cf")
async def kcf(ctx: commands.Context, amount: str):
    """
    kcf <số>  — nhận thêm amount và bonus ngẫu nhiên
    Cho nhập 1.111.111 hoặc 1,111,111 đều được.
    """
    db.ensure_user(ctx.author.id, ctx.author.name)
    val = db.parse_amount(amount)
    if val is None:
        return await ctx.reply("❌ Số không hợp lệ. Ví dụ: `kcf 100000` hoặc `kcf 100.000`")
    gain = val + random.randint(100, 500)
    await owo_typing(ctx)
    db.add_gold(ctx.author.id, gain)
    await ctx.reply(f"⛏️ Đào xong! Nhận **+{db.fmt_vn(gain)}** vàng {random.choice(OWO_EMOJIS)}")

@bot.command(name="ks")
async def ks(ctx: commands.Context):
    db.ensure_user(ctx.author.id, ctx.author.name)
    await owo_typing(ctx)
    gain = random.randint(500, 1_500)
    db.add_gold(ctx.author.id, gain)
    await ctx.reply(f"🌾 Săn được **+{db.fmt_vn(gain)}** vàng {random.choice(OWO_EMOJIS)}")

@bot.command(name="kbj")
async def kbj(ctx: commands.Context):
    db.ensure_user(ctx.author.id, ctx.author.name)
    await owo_typing(ctx)
    gain = random.randint(300, 1_000)
    db.add_gold(ctx.author.id, gain)
    await ctx.reply(f"⛏️ Khai thác được **+{db.fmt_vn(gain)}** vàng {random.choice(OWO_EMOJIS)}")

# ======= Giao dịch / tương tác =======
@bot.command(name="give")
async def give(ctx: commands.Context, member: discord.Member, amount: str):
    """
    kgive @user <số>
    Cho phép nhập dạng 1.111.111 / 1,111,111 / 1111111
    """
    if member.bot:
        return await ctx.reply("🤖 Không thể tặng vàng cho bot.")
    db.ensure_user(ctx.author.id, ctx.author.name)
    db.ensure_user(member.id, member.name)

    val = db.parse_amount(amount)
    if val is None or val <= 0:
        return await ctx.reply("❌ Số không hợp lệ. Ví dụ: `kgive @user 25.000`")

    sender_gold = db.get_gold(ctx.author.id)
    if sender_gold < val:
        return await ctx.reply(f"❌ Bạn không đủ vàng. Bạn đang có **{db.fmt_vn(sender_gold)}**.")

    await owo_typing(ctx, 0.6, 1.2)
    db.add_gold(ctx.author.id, -val)
    db.add_gold(member.id, val)
    await ctx.reply(f"🎁 Đã tặng **{member.mention} {db.fmt_vn(val)}** vàng. Còn lại của bạn: **{db.fmt_vn(db.get_gold(ctx.author.id))}**")

@bot.command(name="steal")
async def steal(ctx: commands.Context, member: discord.Member):
    if member.bot or member.id == ctx.author.id:
        return await ctx.reply("🙅 Không thể trộm mục tiêu này.")
    db.ensure_user(ctx.author.id, ctx.author.name)
    db.ensure_user(member.id, member.name)
    target_gold = db.get_gold(member.id)
    if target_gold <= 0:
        return await ctx.reply("😿 Người này chẳng có vàng để trộm!")

    await owo_typing(ctx)
    success = random.random() < 0.6
    if not success:
        fine = min(150, db.get_gold(ctx.author.id))
        db.add_gold(ctx.author.id, -fine)
        return await ctx.reply(f"🚨 Bị bắt quả tang! Bạn mất **-{db.fmt_vn(fine)}** vàng.")

    stolen = random.randint(50, min(300, target_gold))
    db.add_gold(member.id, -stolen)
    db.add_gold(ctx.author.id, stolen)
    await ctx.reply(f"🕵️ Trộm thành công từ {member.mention}: **+{db.fmt_vn(stolen)}** vàng! {random.choice(OWO_EMOJIS)}")

# ======= Khám phá =======
@bot.command(name="hunt")
async def hunt(ctx: commands.Context):
    db.ensure_user(ctx.author.id, ctx.author.name)
    await owo_typing(ctx)
    gain = random.randint(200, 800)
    db.add_gold(ctx.author.id, gain)
    await ctx.reply(f"🧭 Khám phá đảo và kiếm được **+{db.fmt_vn(gain)}** vàng! {random.choice(OWO_EMOJIS)}")

# ======= Top =======
@bot.command(name="leaderboard")
async def leaderboard(ctx: commands.Context):
    top = db.top_rich(10)
    if not top:
        return await ctx.reply("📭 Chưa có ai trong bảng xếp hạng.")
    lines = []
    medals = ["🥇","🥈","🥉"]
    for i, (name, gold) in enumerate(top, start=1):
        prefix = medals[i-1] if i <= 3 else f"{i}."
        lines.append(f"{prefix} **{name}** — 💰 {db.fmt_vn(gold)}")
    await ctx.reply("**🏆 Bảng Xếp Hạng Giàu Nhất**\n" + "\n".join(lines))

# ======= Help custom =======
@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    embed = discord.Embed(title="📖 Hướng dẫn lệnh — Đảo Hoang Bot", color=0xFFD700,
                          description="Tiền tệ: **vàng**. Dùng dấu chấm phẩy tự do khi nhập số, ví dụ `25.000`.")
    embed.add_field(name="🎮 Cơ bản",
                    value="`kstart` bắt đầu chơi\n"
                          "`kprofile [@user]` xem vàng\n"
                          "`kdaily` nhận thưởng ngày",
                    inline=False)
    embed.add_field(name="⚒️ Cày kiểu owo",
                    value="`kcf <số>` cày thêm (nhập số bất kỳ: `kcf 100.000`)\n"
                          "`kks` săn vàng\n"
                          "`kkbj` khai thác",
                    inline=False)
    embed.add_field(name="🎁 Tương tác",
                    value="`kgive @user <số>` tặng vàng\n"
                          "`ksteal @user` trộm vàng (60% thành công)\n"
                          "`khunt` khám phá\n"
                          "`kleaderboard` top giàu",
                    inline=False)
    await ctx.reply(embed=embed)

# ======= Chạy bot =======
if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ Thiếu DISCORD_TOKEN trong Environment Variables.")
    bot.run(TOKEN)
