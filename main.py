# main.py — safe token + render keepalive + channel_id passthrough
import os
import sys
import discord
from discord.ext import commands
import daohoang

# Lấy token từ biến môi trường (KHÔNG hardcode token trong code)
TOKEN = os.getenv("DISCORD_TOKEN")

# (Tùy chọn) Keep-alive cho Render/Replit nếu có file keepalive.py
try:
    from keepalive import keep_alive  # Flask web server nhỏ
    keep_alive()
except Exception:
    # Không sao nếu bạn không dùng Render/Replit hoặc chưa có keepalive.py
    pass

# Intents
intents = discord.Intents.default()
intents.message_content = True  # nhớ bật Message Content Intent trong Dev Portal

bot = commands.Bot(command_prefix="k", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot đã đăng nhập thành công với tên: {bot.user} (in {len(bot.guilds)} guilds)")

@bot.command()
async def start(ctx):
    """Bắt đầu chơi game đảo hoang"""
    daohoang.create_discord_account(ctx.author.id, ctx.author.name)
    await ctx.reply(
        f"🏝️ Xin chào **{ctx.author.name}**! Tài khoản của bạn đã sẵn sàng.\n"
        "Dùng `khelp` để xem danh sách lệnh!"
    )

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Các lệnh game bắt đầu bằng 'k'
    if message.content.startswith("k"):
        try:
            response = daohoang.process_command(
                message.author.id,
                message.author.name,
                message.content,
                channel_id=message.channel.id  # truyền channel_id để ksetchannel hoạt động
            )
            if response:
                await message.channel.send(response)
        except Exception as e:
            await message.channel.send(f"⚠️ Lỗi: {e}")

    # Để commands extension vẫn bắt được các lệnh @bot.command()
    await bot.process_commands(message)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Thiếu DISCORD_TOKEN. Hãy đặt biến môi trường DISCORD_TOKEN trước khi chạy.")
        sys.exit(1)
    bot.run(TOKEN)
