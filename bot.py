import discord
from discord.ext import commands, tasks
from discord import ui
import asyncio
import itertools
import time
import io
import aiohttp
import json
from datetime import datetime
import urllib.parse
import os
from dotenv import load_dotenv

# --- SYSTEM CONFIG ---
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

GUILD_ID = 1487911608926867590
TICKET_CATEGORY_ID = 1487915424573296671
STAFF_ROLE_ID = 1487912931340456039
MEMBER_COUNT_CH = 1488226177196757042
LOG_CH_ID = 1489372379682701483
ANNOUNCE_CH_ID = 1487918740178997359

GITHUB_REPOS = [
    "EnbesilAdam/WinterHyacinth",
    "EnbesilAdam/Cardinal-AI",
    "EnbesilAdam/MySchoolMemories"
]

JSON_URL = (
    "https://gist.githubusercontent.com/"
    "EnbesilAdam/efa76e1d7df2ba5be195bd4"
    "17d339b5/raw/posts.json"
)
WEB_URL = "https://winterhyacinth.gt.tc/devlog-detail.html"

LAST_DATA = {
    "post_id": None,
    "commits": {}
}

STATUS_OPTIONS = [
    "🎮 Developing Games",
    "⚙️ Optimizing Plugins",
    "💻 Windows Tools",
    "❄️ Winter Hyacinth"
]
STATUS_LIST = itertools.cycle(STATUS_OPTIONS)
START_TIME = datetime.now()

# --- STYLIZED UI COMPONENTS (ALL ENGLISH) ---

class CareerLinkView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        subject = "Winter Hyacinth - Job Application"
        body = (
            "Name/Nickname:\n"
            "Age:\n"
            "Role (Developer/Designer/etc):\n"
            "Portfolio/Experience:\n"
            "Why do you want to join Winter Hyacinth?:"
        )
        mail_to = "winterhyacinth.contact@gmail.com"
        enc_sub = urllib.parse.quote(subject)
        enc_body = urllib.parse.quote(body)
        gmail_url = (
            f"https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={mail_to}&su={enc_sub}&body={enc_body}"
        )
        self.add_item(
            ui.Button(
                label="Send Application via Gmail",
                url=gmail_url,
                emoji="📧"
            )
        )

class FAQDropdown(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Careers",
                description="Apply to join our creative team.",
                emoji="💼"
            ),
            discord.SelectOption(
                label="Open Support Ticket",
                description="Get direct help from our staff.",
                emoji="🎫"
            ),
        ]
        super().__init__(
            placeholder="✨ Select a Service...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="faq_select_v11"
        )

    async def callback(self, interaction: discord.Interaction):
        selection = self.values[0]
        if selection == "Open Support Ticket":
            await interaction.response.defer(ephemeral=True)
            await create_ticket(interaction)
        elif selection == "Careers":
            desc = (
                "We are constantly evolving and looking for new "
                "talents to join our vision.\n\n"
                "**How to apply?**\n"
                "1. Click the button below to open Gmail.\n"
                "2. Fill in your personal details.\n"
                "3. Send your application to our official mail.\n\n"
                "📧 **Contact:** `winterhyacinth.contact@gmail.com`"
            )
            embed = discord.Embed(
                title="💼 Join the Winter Hyacinth Team",
                description=desc,
                color=0x5865F2
            )
            fields = (
                "▫️ Game Development\n"
                "▫️ Web Technologies\n"
                "▫️ Graphic Design\n"
                "▫️ Community Management"
            )
            embed.add_field(
                name="Available Fields",
                value=fields,
                inline=False
            )
            icon = interaction.guild.icon.url if interaction.guild.icon else None
            embed.set_footer(
                text="Winter Hyacinth • Career Dept",
                icon_url=icon
            )
            await interaction.response.send_message(
                embed=embed,
                view=CareerLinkView(),
                ephemeral=True
            )

class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Claim Ticket",
        style=discord.ButtonStyle.success,
        emoji="🛡️",
        custom_id="claim_v11"
    )
    async def claim(self, interaction: discord.Interaction, button: ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ Only authorized staff can claim this ticket.",
                ephemeral=True
            )
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        msg = f"✅ **{interaction.user.mention}** has taken responsibility."
        embed = discord.Embed(description=msg, color=0x2ecc71)
        await interaction.channel.send(embed=embed)

    @ui.button(
        label="Close & Archive",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_v11"
    )
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role not in interaction.user.roles:
            return await interaction.response.send_message(
                "❌ Access denied.",
                ephemeral=True
            )
        await interaction.response.send_message(
            "🔄 **Archiving channel and generating transcript...**"
        )
        log_ch = interaction.guild.get_channel(LOG_CH_ID)
        dt_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        content = (
            f"--- WINTER HYACINTH TICKET LOG ---\n"
            f"Channel: {interaction.channel.name}\n"
            f"Closed By: {interaction.user}\n"
            f"Date: {dt_str}\n"
            f"----------------------------------\n\n"
        )
        async for m in interaction.channel.history(limit=None, oldest_first=True):
            t_str = m.created_at.strftime('%H:%M:%S')
            content += f"[{t_str}] {m.author.display_name}: {m.content}\n"
        if log_ch:
            f_bytes = io.BytesIO(content.encode())
            file = discord.File(
                f_bytes,
                filename=f"archive-{interaction.channel.name}.txt"
            )
            desc = (
                f"**User:** {interaction.channel.name}\n"
                f"**Closed By:** {interaction.user.mention}"
            )
            log_embed = discord.Embed(
                title="📑 Ticket Archived",
                description=desc,
                color=0x2b2d31,
                timestamp=datetime.now()
            )
            await log_ch.send(embed=log_embed, file=file)
        await asyncio.sleep(3)
        await interaction.channel.delete()

async def create_ticket(interaction: discord.Interaction):
    guild = interaction.guild
    category = guild.get_channel(TICKET_CATEGORY_ID)
    staff = guild.get_role(STAFF_ROLE_ID)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            read_messages=False
        ),
        interaction.user: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True
        ),
        staff: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            manage_channels=True
        )
    }
    u_str = str(interaction.user.id)
    ch_name = f"ticket-{interaction.user.name[:10]}-{u_str[-4:]}"
    channel = await guild.create_text_channel(
        name=ch_name,
        category=category,
        overwrites=overwrites
    )
    desc = (
        f"Hello {interaction.user.mention},\n\n"
        f"Our staff has been notified. Please describe your issue.\n\n"
        f"**Staff Tools:** Use buttons below."
    )
    welcome_embed = discord.Embed(
        title="❄️ Welcome to Support",
        description=desc,
        color=0x3498db
    )
    welcome_embed.set_thumbnail(url=interaction.user.display_avatar.url)
    ts = int(interaction.user.created_at.timestamp())
    welcome_embed.add_field(
        name="Account Created",
        value=f"<t:{ts}:R>",
        inline=True
    )
    mention_text = f"{staff.mention if staff else ''} {interaction.user.mention}"
    await channel.send(
        content=mention_text,
        embed=welcome_embed,
        view=TicketControlView()
    )
    await interaction.followup.send(
        f"✅ Ticket created: {channel.mention}",
        ephemeral=True
    )

# --- BOT ENGINE ---

class WinterBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.all(),
            help_command=None
        )

    async def setup_hook(self):
        faq_view = ui.View(timeout=None)
        faq_view.add_item(FAQDropdown())
        self.add_view(faq_view)
        self.add_view(TicketControlView())
        self.add_view(CareerLinkView())
        self.main_loop.start()
        print("💎 Winter Hyacinth Bot Loaded | Systems Operational")

    @tasks.loop(minutes=2)
    async def main_loop(self):
        if not self.is_ready(): return
        await self.check_github()
        await self.check_devlogs()
        await self.update_stats()

    async def check_github(self):
        try:
            async with aiohttp.ClientSession() as session:
                for repo in GITHUB_REPOS:
                    api_url = f"https://api.github.com/repos/{repo}/commits"
                    async with session.get(api_url) as resp:
                        if resp.status != 200: continue
                        commits_data = await resp.json()
                        if not commits_data: continue
                        
                        sha = commits_data[0]['sha']
                        repo_name = repo.split('/')[-1]
                        
                        if repo not in LAST_DATA["commits"]:
                            LAST_DATA["commits"][repo] = sha
                            continue
                        
                        if LAST_DATA["commits"][repo] != sha:
                            detail_url = f"{api_url}/{sha}"
                            async with session.get(detail_url) as d_resp:
                                if d_resp.status == 200:
                                    d_data = await d_resp.json()
                                    msg = d_data['commit']['message']
                                    author = d_data['commit']['author']['name']
                                    url = d_data['html_url']
                                    
                                    stats = d_data.get('stats', {})
                                    total_changes = stats.get('total', 0)
                                    additions = stats.get('additions', 0)
                                    deletions = stats.get('deletions', 0)
                                    
                                    files_summary = []
                                    for file in d_data.get('files', [])[:10]:
                                        filename = file.get('filename')
                                        status = file.get('status')
                                        if status == "added":
                                            files_summary.append(f"🟢 **Added:** `{filename}`")
                                        elif status == "modified":
                                            files_summary.append(f"🟡 **Modified:** `{filename}`")
                                        elif status == "removed":
                                            files_summary.append(f"🔴 **Removed:** `{filename}`")
                                    
                                    total_files = len(d_data.get('files', []))
                                    if total_files > 10:
                                        files_summary.append(f"*and {total_files - 10} more files...*")
                                        
                                    file_changes_text = "\n".join(files_summary) if files_summary else "No structural file changes."
                                    
                                    ch = self.get_channel(ANNOUNCE_CH_ID)
                                    embed = discord.Embed(
                                        title=f"🚀 GitHub Update: {repo_name}",
                                        color=0x2ecc71,
                                        timestamp=datetime.now()
                                    )
                                    gh_icon = "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
                                    embed.set_author(name=f"Push by {author}", icon_url=gh_icon)
                                    
                                    embed.description = f"**Commit Message:**\n```text\n{msg}\n```"
                                    
                                    stats_text = f"🔹 **Total Lines Changed:** `{total_changes}`\n➕ **Additions:** `{additions}`\n➖ **Deletions:** `{deletions}`"
                                    embed.add_field(name="📊 Commit Statistics", value=stats_text, inline=False)
                                    embed.add_field(name="📋 Modified Files", value=file_changes_text, inline=False)
                                    embed.add_field(name="🔗 Code Review", value=f"[Review on GitHub]({url})")
                                    
                                    if ch:
                                        await ch.send(content="🔔 **New Repository Activity Detected!**", embed=embed)
                            
                            LAST_DATA["commits"][repo] = sha
                        await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[-] GitHub Error: {e}")

    async def check_devlogs(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{JSON_URL}?t={int(time.time())}") as resp:
                    if resp.status == 200:
                        data = json.loads(await resp.text())
                        if not data: return

                        sorted_data = sorted(data, key=lambda x: int(x['id']), reverse=True)
                        latest = sorted_data[0]
                        pid_str = str(latest.get("id"))
                        pid_int = int(pid_str)

                        if LAST_DATA["post_id"] is None:
                            LAST_DATA["post_id"] = pid_str
                            return

                        old_id = int(LAST_DATA["post_id"])

                        if pid_int > old_id:
                            ch = self.get_channel(ANNOUNCE_CH_ID)
                            embed = discord.Embed(
                                title=f"❄️ NEW DEVLOG: {latest.get('baslik')}",
                                description=latest.get("ozet"),
                                color=0x7d5fff
                            )
                            embed.add_field(name="Link", value=f"🔗 [Open Devlog]({WEB_URL}?id={pid_str})")
                            banner = latest.get("banner")
                            if banner:
                                if banner.startswith("img/"):
                                    banner = f"https://winterhyacinth.gt.tc/{banner}"
                                embed.set_image(url=banner)

                            if ch: await ch.send(content="🔔 **New Article!** @everyone", embed=embed)

                        LAST_DATA["post_id"] = pid_str
        except Exception as e:
            print(f"[-] Devlog Error: {e}")

    async def update_stats(self):
        guild = self.get_guild(GUILD_ID)
        if guild:
            ch = guild.get_channel(MEMBER_COUNT_CH)
            if ch:
                try: await ch.edit(name=f"👥 Members: {guild.member_count}")
                except: pass
            status_activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=next(STATUS_LIST)
            )
            await self.change_presence(activity=status_activity)

bot = WinterBot()

# --- COMMANDS ---

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup(ctx):
    desc = "Official Career & Support Center. Select an option below to proceed."
    embed = discord.Embed(
        title="❄️ WINTER HYACINTH HUB",
        description=desc,
        color=0x2b2d31
    )
    embed.set_image(url="https://i.imgur.com/jlevP0F.jpeg")
    embed.set_footer(text="Reliability • Innovation • Quality")
    view = ui.View(timeout=None)
    view.add_item(FAQDropdown())
    await ctx.send(embed=embed, view=view)

@bot.command(name="info")
async def info(ctx):
    uptime = datetime.now() - START_TIME
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    embed = discord.Embed(
        title="❄️ Winter Hyacinth - System Intelligence",
        color=0x3498db,
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(name="👥 Members", value=f"`{ctx.guild.member_count}`", inline=True)
    embed.add_field(name="🎭 Roles", value=f"`{len(ctx.guild.roles)}`", inline=True)
    embed.add_field(name="💬 Channels", value=f"`{len(ctx.guild.channels)}`", inline=True)

    embed.add_field(name="📡 Latency", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.add_field(name="⏱️ Uptime", value=f"`{hours}h {minutes}m {seconds}s`", inline=True)
    embed.add_field(name="🛰️ Status", value="🟢 Operational", inline=True)

    embed.add_field(name="🚀 Monitored Repos", value=f"`{len(GITHUB_REPOS)} Repos`", inline=True)
    p_id = LAST_DATA['post_id'] if LAST_DATA['post_id'] else 'Syncing...'
    embed.add_field(name="📝 Devlog ID", value=f"`{p_id}`", inline=True)
    embed.add_field(name="💻 Developer", value="`enbest`", inline=True)

    icon = ctx.guild.icon.url if ctx.guild.icon else None
    embed.set_footer(
        text="Winter Hyacinth • Automated System",
        icon_url=icon
    )
    await ctx.send(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: DISCORD_BOT_TOKEN not found in environment!")
    else:
        bot.run(TOKEN)
