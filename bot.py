import discord
from discord.ext import commands, tasks
from discord import ui, app_commands
import asyncio
import itertools
import time
import io
import aiohttp
import json
from datetime import datetime, timedelta
import urllib.parse
TOKEN = ''
GUILD_ID = 1487911608926867590 
TICKET_CATEGORY_ID = 1487915424573296671
STAFF_ROLE_ID = 1487912931340456039
MEMBER_COUNT_CH = 1488226177196757042 
LOG_CH_ID = 1489372379682701483 
ANNOUNCE_CH_ID = 1487918740178997359 

GITHUB_REPO = "EnbesilAdam/WinterHyacinth" 
JSON_URL = "https://gist.githubusercontent.com/EnbesilAdam/efa76e1d7df2ba5be195bd4717d339b5/raw/posts.json"
WEB_URL = "https://winterhyacinth.gt.tc/devlog-detail.html"

LAST_DATA = {"post_id": None, "commit_sha": None}
STATUS_LIST = itertools.cycle(["🎮 Developing Games", "⚙️ Optimizing Plugins", "💻 Windows Tools", "❄️ Winter Hyacinth"])
START_TIME = datetime.now()

class CareerLinkView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        subject = "Winter Hyacinth - Job Application"
        body = ("Name/Nickname:\n" "Age:\n" "Role (Developer/Designer/etc):\n" "Portfolio/Experience:\n" "Why do you want to join Winter Hyacinth?:")
        mail_to = "winterhyacinth.contact@gmail.com"
        encoded_subject = urllib.parse.quote(subject)
        encoded_body = urllib.parse.quote(body)
        gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={mail_to}&su={encoded_subject}&body={encoded_body}"
        self.add_item(ui.Button(label="Send Application via Gmail", url=gmail_url, emoji="📧"))

class FAQDropdown(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Careers", description="Apply to join our creative team.", emoji="💼"),
            discord.SelectOption(label="Open Support Ticket", description="Get direct help from our staff.", emoji="🎫"),
        ]
        super().__init__(placeholder="✨ Select a Service...", min_values=1, max_values=1, options=options, custom_id="faq_select_v11")

    async def callback(self, interaction: discord.Interaction):
        selection = self.values[0]
        if selection == "Open Support Ticket":
            await interaction.response.defer(ephemeral=True)
            await create_ticket(interaction)
        elif selection == "Careers":
            embed = discord.Embed(
                title="💼 Join the Winter Hyacinth Team", 
                description=(
                    "We are constantly evolving and looking for new talents to join our vision.\n\n"
                    "**How to apply?**\n"
                    "1. Click the button below to open a pre-formatted Gmail tab.\n"
                    "2. Fill in your personal details and portfolio.\n"
                    "3. Send your application to our official mail.\n\n"
                    "📧 **Contact:** `winterhyacinth.contact@gmail.com`"
                ), 
                color=0x5865F2
            )
            embed.add_field(name="Available Fields", value="▫️ Game Development\n▫️ Web Technologies\n▫️ Graphic Design\n▫️ Community Management", inline=False)
            embed.set_footer(text="Winter Hyacinth • Career Department", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            await interaction.response.send_message(embed=embed, view=CareerLinkView(), ephemeral=True)

class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="🛡️", custom_id="claim_v11")
    async def claim(self, interaction: discord.Interaction, button: ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("❌ Only authorized staff can claim this ticket.", ephemeral=True)
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        embed = discord.Embed(description=f"✅ **{interaction.user.mention}** has taken responsibility for this ticket.", color=0x2ecc71)
        await interaction.channel.send(embed=embed)

    @ui.button(label="Close & Archive", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_v11")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message("❌ Access denied.", ephemeral=True)
        await interaction.response.send_message("🔄 **Archiving channel and generating transcript...**")
        log_ch = interaction.guild.get_channel(LOG_CH_ID)
        content = f"--- WINTER HYACINTH TICKET LOG ---\nChannel: {interaction.channel.name}\nClosed By: {interaction.user}\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n----------------------------------\n\n"
        async for m in interaction.channel.history(limit=None, oldest_first=True):
            content += f"[{m.created_at.strftime('%H:%M:%S')}] {m.author.display_name}: {m.content}\n"
        if log_ch:
            file = discord.File(io.BytesIO(content.encode()), filename=f"archive-{interaction.channel.name}.txt")
            log_embed = discord.Embed(title="📑 Ticket Archived", description=f"**User:** {interaction.channel.name}\n**Closed By:** {interaction.user.mention}", color=0x2b2d31, timestamp=datetime.now())
            await log_ch.send(embed=log_embed, file=file)
        await asyncio.sleep(3)
        await interaction.channel.delete()

async def create_ticket(interaction: discord.Interaction):
    guild = interaction.guild
    category = guild.get_channel(TICKET_CATEGORY_ID)
    staff = guild.get_role(STAFF_ROLE_ID)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        staff: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }
    user_id_str = str(interaction.user.id)
    channel = await guild.create_text_channel(
        name=f"ticket-{interaction.user.display_name[:10]}-{user_id_str[-4:]}",
        category=category,
        overwrites=overwrites
    )
    welcome_embed = discord.Embed(title="❄️ Welcome to Support", description=f"Hello {interaction.user.mention},\n\nOur staff has been notified. While you wait, please describe your issue.\n\n**Staff Tools:** Use buttons below.", color=0x3498db)
    welcome_embed.set_thumbnail(url=interaction.user.display_avatar.url)
    welcome_embed.add_field(name="Account Created", value=f"<t:{int(interaction.user.created_at.timestamp())}:R>", inline=True)
    await channel.send(content=f"{staff.mention if staff else ''} {interaction.user.mention}", embed=welcome_embed, view=TicketControlView())
    await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

class WinterBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all(), help_command=None)

    async def setup_hook(self):
        faq_view = ui.View(timeout=None)
        faq_view.add_item(FAQDropdown())
        self.add_view(faq_view)
        self.add_view(TicketControlView())
        self.add_view(CareerLinkView())
        self.main_loop.start()
        print("💎 Aesthetic Engine Loaded | Systems Operational")

    @tasks.loop(minutes=2)
    async def main_loop(self):
        if not self.is_ready(): return
        await self.check_github()
        await self.check_devlogs()
        await self.update_stats()

    async def check_github(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.github.com/repos/{GITHUB_REPO}/commits") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        sha = data[0]['sha']
                        if LAST_DATA["commit_sha"] and LAST_DATA["commit_sha"] != sha:
                            ch = self.get_channel(ANNOUNCE_CH_ID)
                            msg, author, url = data[0]['commit']['message'], data[0]['commit']['author']['name'], data[0]['html_url']
                            embed = discord.Embed(title="🚀 GitHub Repository Update", color=0x2ecc71, timestamp=datetime.now())
                            embed.set_author(name=f"Update by {author}", icon_url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
                            embed.description = f"```text\n{msg}\n```"
                            embed.add_field(name="Changes", value=f"[View Commit]({url})")
                            if ch: await ch.send(embed=embed)
                        LAST_DATA["commit_sha"] = sha
        except: pass

    async def check_devlogs(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{JSON_URL}?t={int(time.time())}") as resp:
                    if resp.status == 200:
                        data = json.loads(await resp.text())
                        sorted_data = sorted(data, key=lambda x: int(x['id']), reverse=True)
                        latest = sorted_data[0]
                        pid = str(latest.get("id"))
                        if LAST_DATA["post_id"] and LAST_DATA["post_id"] != pid:
                            ch = self.get_channel(ANNOUNCE_CH_ID)
                            embed = discord.Embed(title=f"❄️ NEW DEVLOG: {latest.get('baslik')}", description=latest.get("ozet"), color=0x7d5fff)
                            embed.add_field(name="Link", value=f"🔗 [Open Devlog]({WEB_URL}?id={pid})")
                            banner = latest.get("banner")
                            if banner:
                                if banner.startswith("img/"): banner = f"https://winterhyacinth.gt.tc/{banner}"
                                embed.set_image(url=banner)
                            if ch: await ch.send(content="🔔 **New Article Published!** @everyone", embed=embed)
                        LAST_DATA["post_id"] = pid
        except: pass

    async def update_stats(self):
        guild = self.get_guild(GUILD_ID)
        if guild:
            ch = guild.get_channel(MEMBER_COUNT_CH)
            if ch: 
                try: await ch.edit(name=f"👥 Members: {guild.member_count}")
                except: pass
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=next(STATUS_LIST)))

bot = WinterBot()

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup(ctx):
    embed = discord.Embed(title="❄️ WINTER HYACINTH HUB", description="Official Career & Support Center. Select an option below to proceed.", color=0x2b2d31)
    embed.set_image(url="https://i.imgur.com/jlevP0F.jpeg")
    embed.set_footer(text="Reliability • Innovation • Quality")
    view = ui.View(timeout=None)
    view.add_item(FAQDropdown())
    await ctx.send(embed=embed, view=view)

@bot.command(name="info")
async def info(ctx):
    """Gelişmiş Bilgilendirme Komutu"""
    uptime = datetime.now() - START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    embed = discord.Embed(title="❄️ Winter Hyacinth - System Intelligence", color=0x3498db, timestamp=datetime.now())
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    embed.add_field(name="👥 Members", value=f"`{ctx.guild.member_count}`", inline=True)
    embed.add_field(name="🎭 Roles", value=f"`{len(ctx.guild.roles)}`", inline=True)
    embed.add_field(name="💬 Channels", value=f"`{len(ctx.guild.channels)}`", inline=True)
    
    embed.add_field(name="📡 Latency", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"`{hours}h {minutes}m {seconds}s`", inline=True)
    embed.add_field(name="🛰️ Status", value="🟢 Operational", inline=True)
    
    embed.add_field(name="🚀 Last Commit", value=f"`{LAST_DATA['commit_sha'][:7] if LAST_DATA['commit_sha'] else 'Checking...'}`", inline=True)
    embed.add_field(name="📝 Devlog ID", value=f"`{LAST_DATA['post_id'] if LAST_DATA['post_id'] else 'Syncing...'}`", inline=True)
    embed.add_field(name="💻 Developer", value="`enbest`", inline=True)
    
    embed.set_footer(text="Winter Hyacinth • Automated Management System", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.send(embed=embed)

if __name__ == "__main__":
    bot.run(TOKEN)
