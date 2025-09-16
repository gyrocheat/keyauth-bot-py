import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import requests
import string
import random
from datetime import datetime, UTC
import logging

# Load .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
ROLE_ID = int(os.getenv("ROLE_ID"))
SELLER_KEY = os.getenv("SELLER_KEY")
SELLER_LINK = os.getenv("SELLER_LINK")

# Logging
logging.basicConfig(filename="bot.log", level=logging.INFO, format='%(asctime)s - %(message)s')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Embed footer config
FOOTER_TEXT = "discord.gg/gazan"
FOOTER_ICON = "https://cdn.discordapp.com/emojis/1405595923601555467.webp?size=128"
EMBED_COLOR = 0xff0000
def _parse_response(resp: requests.Response):
    text = resp.text
    try:
        return resp.json()
    except Exception:
        # fallback: return raw text in dict
        return {"success": False, "message": text}

def call_seller_api_try_types(base_params: dict, try_types: list[str] | None = None) -> dict:
    """
    Call seller API. If try_types provided, will attempt each type in order until a non-'Type doesn't exist' result.
    Returns parsed dict (or {'success': False, 'message': '...'}).
    """
    params = base_params.copy()
    params["sellerkey"] = SELLER_KEY
    params.setdefault("format", "json")

    if try_types:
        last_resp = {"success": False, "message": "No response"}
        for t in try_types:
            params["type"] = t
            try:
                r = requests.get(SELLER_LINK, params=params, timeout=15)
                parsed = _parse_response(r)
            except Exception as e:
                parsed = {"success": False, "message": str(e)}
            # If backend explicitly said type doesn't exist, try next
            msg = str(parsed.get("message", "")).lower()
            if "type doesn't exist" in msg or "type does not exist" in msg or "type not exist" in msg:
                last_resp = parsed
                continue
            # Otherwise return immediately
            return parsed
        return last_resp
    else:
        try:
            r = requests.get(SELLER_LINK, params=params, timeout=15)
            return _parse_response(r)
        except Exception as e:
            return {"success": False, "message": str(e)}


def mask():
    # Ví dụ: GZV-ABC-123
    part1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    part2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    return f"GZV-{part1}-{part2}"

# Helper function to send embed
def embed_message(title, description):
    embed = discord.Embed(title=title, description=description, color=EMBED_COLOR, timestamp=datetime.now(UTC))
    embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
    return embed

# Check role
def has_role(interaction):
    return any(role.id == ROLE_ID for role in interaction.user.roles)

# Add Key
@bot.tree.command(name="add", description="Thêm key mới")
@app_commands.describe(day="Số ngày key tồn tại", level="Level của key", amount="Số lượng key")
async def add(interaction: discord.Interaction, day: int, level: int, amount: int):
    if not has_role(interaction):
        return await interaction.response.send_message("Bạn không có quyền dùng lệnh này!", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)

    try:
        resp = requests.get(
            f"{SELLER_LINK}?sellerkey={SELLER_KEY}&type=add&expiry={day}"
            f"&mask=GZV-XXX-XXX&level={level}&amount={amount}&format=json",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return await interaction.followup.send(f"⚠️ Lỗi gọi API: {e}", ephemeral=True)
    
    if not data.get("success"):
        return await interaction.followup.send(f"❌ Không thể tạo key: {data.get('message','Unknown error')}", ephemeral=True)
    
    created_keys = []
    if data.get("success"):
        print("DEBUG API response:", data)
        if "keys" in data:
            created_keys = data["keys"]
        elif "key" in data:
            created_keys = [data["key"]]

    if created_keys:
        keys_text = "\n".join(created_keys)
        code_block = f"```\n{keys_text}\n```"
        embed = discord.Embed(
            title="✅ Key đã được tạo thành công!",
            color=0xff0000,
            timestamp=datetime.now(UTC)
        )
        embed.add_field(name="🔑 License Key", value=str(len(created_keys)), inline=False)
        embed.add_field(name="🖥 Số thiết bị", value="1 thiết bị", inline=True)
        embed.add_field(name="⏳ Thời hạn", value=f"{day} ngày", inline=True)
        embed.add_field(name="🏷 Level", value=f"Level {level}", inline=True)
        embed.add_field(name="📅 Ngày tạo", value=datetime.now(UTC).strftime("%d-%m-%Y %H:%M:%S"), inline=True)
        embed.add_field(name="👤 Người tạo", value=str(interaction.user), inline=True)
        embed.add_field(name="⏰ Thời gian còn lại", value=f"{day} ngày", inline=True)
        embed.add_field(name="🚫 Trạng thái", value="Chưa Dùng", inline=True)
        embed.add_field(name="\u200b", value="─" * 20, inline=False)  # separator
        if len(code_block) <= 4000:
            embed.description = f"**Danh sách keys:**\n{code_block}"
            file_to_send = None
        else:
        # Nếu quá dài thì gửi kèm file
            import io
            buffer = io.StringIO(keys_text)
            file_to_send = discord.File(fp=buffer, filename="keys.txt")
            embed.add_field(
            name="📎 Tệp đính kèm",
            value="Danh sách key quá dài, xem file `keys.txt`.",
            inline=False
        )

        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
        await interaction.followup.send(embed=embed, ephemeral=True)
        logging.info(f"{interaction.user} executed /add: {created_keys}")
        return 
    else:
            embed = discord.Embed(
                title="❌ Lỗi khi tạo key!",
            description=data.get("message", "Không thể tạo key."),
            color=0xff0000,
            timestamp=datetime.now(UTC)
        )
    embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
    await interaction.followup.send(embed=embed, ephemeral=True)
    logging.error(f"{interaction.user} executed /add but failed: {data}")

# Delete Key
@bot.tree.command(name="del", description="Xóa key")
@app_commands.describe(key="Key cần xóa", reason="Lý do xóa key")
async def delete(interaction: discord.Interaction, key: str, reason: str):
    if not has_role(interaction):
        await interaction.response.send_message("Bạn không có quyền dùng lệnh này!", ephemeral=True)
        return
    resp = requests.get(
       f"{SELLER_LINK}?sellerkey={SELLER_KEY}&type=del&key={key}&reason={reason}&format=json",
       timeout=15
    )
    data = resp.json()
    if data.get('success'):
        embed = discord.Embed(
            title="🗑️ Key đã bị xóa!",
            color=0xff0000, 
            timestamp=datetime.now(UTC)
        )
        embed.add_field(name="🔑 License Key", value=key, inline=False)
        embed.add_field(name="📝 Lý do", value=reason, inline=True)
        embed.add_field(name="👤 Người xóa", value=str(interaction.user), inline=True)
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
    else:
        embed = discord.Embed(
            title="❌ Lỗi khi xóa key!",
            description=data.get("message", "Không thể xóa key."),
            color=0xff0000,
            timestamp=datetime.now(UTC)
        )
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    logging.info(f"{interaction.user} executed /del on {key}: {data}")
# Info Key
from datetime import datetime, timezone, timedelta

@bot.tree.command(name="inf", description="Lấy thông tin key")
@app_commands.describe(key="Key cần lấy thông tin")
async def info(interaction: discord.Interaction, key: str):
    if not has_role(interaction):
        await interaction.response.send_message("Bạn không có quyền dùng lệnh này!", ephemeral=True)
        return

    try:
        resp = requests.get(
            f"{SELLER_LINK}?sellerkey={SELLER_KEY}&type=info&key={key}&format=json",
            timeout=15
        )
        data = resp.json()
    except Exception as e:
        data = {"success": False, "message": str(e)}

    print("DEBUG /inf response:", data)

    if data.get("success"):
        # Lấy các field
        creation_raw = data.get("creationdate", "N/A")
        expiry_raw = data.get("expiry", "N/A")

        # Parse creation date (UTC) -> VN time
        try:
            creation_dt = datetime.strptime(creation_raw, "%dth %B %Y %I:%M:%S %p (UTC)")
            creation_vn = creation_dt + timedelta(hours=7)
            creation_fmt = creation_vn.strftime("%d-%m-%Y %H:%M:%S")
        except Exception:
            creation_fmt = creation_raw

        # Parse expiry date -> timeleft
        try:
            expiry_dt = datetime.strptime(expiry_raw, "%d %B %Y %I:%M:%S %p (UTC)")
            expiry_vn = expiry_dt + timedelta(hours=7)
            expiry_fmt = expiry_vn.strftime("%d-%m-%Y %H:%M:%S")
            now_vn = datetime.now(timezone.utc) + timedelta(hours=7)
            timeleft = str(expiry_vn - now_vn)
        except Exception:
            expiry_fmt = expiry_raw
            timeleft = "Không xác định"

        embed = discord.Embed(
            title="ℹ️ Thông tin Key",
            color=0xff0000,
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(name="🔑 License Key", value=key, inline=True)
        embed.add_field(name="📅 Ngày tạo", value=creation_fmt, inline=True)
        embed.add_field(name="🏷 Level", value=data.get("level", "N/A"), inline=True)
        embed.add_field(name="👤 Người tạo", value=str(interaction.user), inline=True)
        embed.add_field(name="🙍 Người dùng", value=data.get("usedby", "N/A"), inline=True)
        embed.add_field(name="🚫 Trạng thái", value=data.get("status", "N/A"), inline=True)
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
    else:
        embed = discord.Embed(
            title="❌ Lỗi khi lấy thông tin key!",
            description=str(data.get("message", "Không thể lấy thông tin key.")),
            color=0xff0000,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)

    await interaction.response.send_message(embed=embed, ephemeral=True)



# Ban Key
@bot.tree.command(name="ban", description="Ban key")
@app_commands.describe(key="Key cần ban")
async def ban(interaction: discord.Interaction, key: str):
    if not has_role(interaction):
        return await interaction.response.send_message("Bạn không có quyền dùng lệnh này!", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    try:
        resp = requests.get(
            f"{SELLER_LINK}?sellerkey={SELLER_KEY}&type=ban&key={key}&format=json",
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        embed = discord.Embed(
            title="❌ Lỗi khi gọi API!",
            description=str(e),
            color=EMBED_COLOR,
            timestamp=datetime.now(UTC)
        )
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
        return await interaction.followup.send(embed=embed, ephemeral=True)

    if data.get("success"):
        embed = discord.Embed(
            title="✅ Key đã bị BAN thành công!",
            color=EMBED_COLOR,
            timestamp=datetime.now(UTC)
        )
        embed.add_field(name="🔑 License Key", value=key, inline=False)
        embed.add_field(name="🚫 Trạng thái", value="Đã bị ban", inline=True)
        embed.add_field(name="👤 Người thực hiện", value=str(interaction.user), inline=True)
        embed.add_field(name="📅 Thời gian", value=datetime.now(UTC).strftime("%d-%m-%Y %H:%M:%S"), inline=True)
    else:
        embed = discord.Embed(
            title="❌ Lỗi khi ban key!",
            description=data.get("message", "Không thể ban key."),
            color=EMBED_COLOR,
            timestamp=datetime.now(UTC)
        )

    embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
    await interaction.followup.send(embed=embed, ephemeral=True)

    logging.info(f"{interaction.user} executed /ban on {key}: {data}")

# Reset HWID
@bot.tree.command(name="reset", description="Reset key ")
@app_commands.describe(key="Key cần reset")
async def reset(interaction: discord.Interaction, key: str):
    if not has_role(interaction):
        return await interaction.response.send_message("Bạn không có quyền dùng lệnh này!", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    try:
        resp = requests.get(
            f"{SELLER_LINK}?sellerkey={SELLER_KEY}&type=resetuser&user={key}&format=json",
            timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        embed = discord.Embed(
            title="❌ Lỗi khi gọi API!",
            description=str(e),
            color=EMBED_COLOR,
            timestamp=datetime.now(UTC)
        )
        embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
        return await interaction.followup.send(embed=embed, ephemeral=True)

    if data.get("success"):
        embed = discord.Embed(
            title="✅ Key đã được reset thành công!",
            color=EMBED_COLOR,
            timestamp=datetime.now(UTC)
        )
        embed.add_field(name="🔑 License Key", value=key, inline=False)
        embed.add_field(name="⚙️ Thao tác", value="Reset Key", inline=True)
        embed.add_field(name="👤 Người thực hiện", value=str(interaction.user), inline=True)
        embed.add_field(name="🚫 Trạng thái", value="Resetkey thành công", inline=True)
        embed.add_field(name="📅 Thời gian", value=datetime.now(UTC).strftime("%d-%m-%Y %H:%M:%S"), inline=True)
    else:
        embed = discord.Embed(
            title="❌ Lỗi khi reset HWID!",
            description=data.get("message", "Không thể reset HWID."),
            color=EMBED_COLOR,
            timestamp=datetime.now(UTC)
        )

    embed.set_footer(text=FOOTER_TEXT, icon_url=FOOTER_ICON)
    await interaction.followup.send(embed=embed, ephemeral=True)

    logging.info(f"{interaction.user} executed /reset on {key}: {data}")



# Run Bot
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} đã online!")

bot.run(TOKEN)