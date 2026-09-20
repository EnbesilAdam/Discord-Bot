"""
❄️ Winter Hyacinth Bot v2
Gereksinimler:  pip install -U discord.py aiohttp python-dotenv   (Python 3.10+)
.env:           DISCORD_BOT_TOKEN, GEMINI_API_KEY, GITHUB_TOKEN (opsiyonel)
"""
import asyncio
import io
import json
import logging
import os
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("hyacinth")

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

GUILD_ID = 1487911608926867590
TICKET_CATEGORY_ID = 1487915424573296671
STAFF_ROLE_ID = 1487912931340456039
MEMBER_COUNT_CH = 1488226177196757042
LOG_CH_ID = 1489372379682701483
ANNOUNCE_CH_ID = 1487918740178997359

GITHUB_REPOS = ["EnbesilAdam/Discord-Bot", "EnbesilAdam/WinterHyacinth"]
JSON_URL = "https://api.github.com/gists/efa76e1d7df2ba5be195bd4717d339b5"
WEB_URL = "https://winterhyacinth.gt.tc/devlog-detail.html"
SITE_URL = "https://winterhyacinth.gt.tc"

# Gemini: erişilemeyen (404) modeller otomatik atlanır, sırayla yedeğe geçilir.
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-1.5-flash"]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_SYSTEM_PROMPT = (
    "You are Hyacinth AI, the official smart assistant of Winter Hyacinth — "
    "a game development and software studio. You are helpful, technically strong, "
    "and friendly. You assist users with coding questions, debugging, game dev, "
    "web technologies, and general software problems. "
    "When writing code, always use proper markdown code blocks with language tags. "
    "Reply in the same language the user writes in. "
    "Keep responses concise but thorough. If you don't know something, say so honestly."
)

AI_IDLE_LIMIT = 600      # sn: oturum otomatik kapanma süresi
AI_IDLE_WARN = 540       # sn: kapanmadan önce uyarı
AI_MAX_HISTORY = 20      # hafızada tutulan mesaj sayısı (çift olmalı)
PING_EVERYONE_ON_DEVLOG = True

STATUS_OPTIONS = ["🎮 Developing Games", "⚙️ Optimizing Plugins", "💻 Windows Tools", "❄️ Winter Hyacinth", "💬 /help"]
TEXT_EXT = (".py", ".js", ".ts", ".json", ".txt", ".md", ".cs", ".java", ".cpp", ".c", ".h", ".html", ".css",
            ".lua", ".yml", ".yaml", ".log", ".sh", ".bat", ".ini", ".toml", ".xml", ".sql", ".php", ".go", ".rs", ".gd")


class C:
    PRIMARY = 0x7D5FFF
    SUCCESS = 0x2ECC71
    ERROR = 0xE74C3C
    INFO = 0x3498DB
    WARN = 0xF1C40F
    DARK = 0x2B2D31
    BLURPLE = 0x5865F2


NO_MENTIONS = discord.AllowedMentions.none()
LAST_DATA = {"post_id": None, "commits": {}}


def truncate(text, n: int) -> str:
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def fmt_uptime(seconds: float) -> str:
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    return " ".join(p for p in (f"{d}g" if d else "", f"{h}sa" if h else "", f"{m}dk" if m else "", f"{s}sn") if p)


def is_staff(member) -> bool:
    if not isinstance(member, discord.Member):
        return False
    return member.guild_permissions.administrator or any(r.id == STAFF_ROLE_ID for r in member.roles)


def split_message(text: str, limit: int = 1900) -> list[str]:
    """Uzun metni satır sınırlarından böler ve kod bloklarını (```) bozmadan taşır."""
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    chunks.append(text)

    out, carry = [], None
    for chunk in chunks:
        if carry is not None:
            chunk = f"```{carry}\n{chunk}"
        markers = re.findall(r"```([^\n`]*)", chunk)
        if len(markers) % 2 == 1:
            carry = markers[-1].strip()
            chunk += "\n```"
        else:
            carry = None
        out.append(chunk)
    return out


async def send_log(guild: discord.Guild, embed: discord.Embed, file: Optional[discord.File] = None):
    ch = guild.get_channel(LOG_CH_ID)
    if ch:
        try:
            await ch.send(embed=embed, file=file)
        except discord.HTTPException as e:
            log.warning("Log gönderilemedi: %s", e)


class GeminiClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.sem = asyncio.Semaphore(3)

    async def generate(self, history: list, prompt: str) -> tuple[bool, str, Optional[str]]:
        """(başarılı_mı, metin, kullanılan_model) döner."""
        if not GEMINI_API_KEY:
            return False, "❌ `GEMINI_API_KEY` bulunamadı. Lütfen `.env` dosyasını kontrol edin.", None

        payload = {
            "systemInstruction": {"parts": [{"text": GEMINI_SYSTEM_PROMPT}]},
            "contents": [*history, {"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
        timeout = aiohttp.ClientTimeout(total=45)

        async with self.sem:
            for model in GEMINI_MODELS:
                url = f"{GEMINI_BASE}/{model}:generateContent"
                for attempt in range(3):
                    try:
                        async with self.session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                            if resp.status == 200:
                                return self._parse(await resp.json(), model)
                            if resp.status in (429, 500, 502, 503, 504):
                                log.warning("Gemini %s HTTP %s (deneme %d/3)", model, resp.status, attempt + 1)
                                if attempt < 2:
                                    await asyncio.sleep(2 ** (attempt + 1))
                                continue
                            if resp.status == 404:
                                log.warning("Gemini modeli bulunamadı: %s, sonraki modele geçiliyor", model)
                                break
                            body = (await resp.text())[:200]
                            log.error("Gemini %s HTTP %s: %s", model, resp.status, body)
                            return False, f"❌ Gemini API hatası: HTTP {resp.status}", model
                    except asyncio.TimeoutError:
                        log.warning("Gemini %s zaman aşımı (deneme %d/3)", model, attempt + 1)
                    except aiohttp.ClientError as e:
                        log.error("Gemini bağlantı hatası (%s): %s", model, e)
                        return False, "❌ Gemini'ye bağlanılamadı. Biraz sonra tekrar dene.", model

        return False, ("⏳ **Gemini şu an meşgul.** Tüm modeller denendi ama yanıt alınamadı.\n"
                       "Lütfen **1-2 dakika** bekleyip tekrar dene."), None

    @staticmethod
    def _parse(data: dict, model: str) -> tuple[bool, str, Optional[str]]:
        candidates = data.get("candidates") or []
        if not candidates:
            if (data.get("promptFeedback") or {}).get("blockReason"):
                return False, "🛡️ Bu istek güvenlik filtresi tarafından engellendi.", model
            return False, "❌ Gemini yanıt döndürmedi. Lütfen tekrar dene.", model
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            return False, "❌ Gemini boş yanıt döndürdü. Soruyu farklı ifade etmeyi dene.", model
        return True, text, model


@dataclass
class AISession:
    user_id: int
    history: list = field(default_factory=list)
    last_activity: float = field(default_factory=time.time)
    warned: bool = False
    turns: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


AI_SESSIONS: dict[int, AISession] = {}


async def read_attachments(message: discord.Message) -> str:
    parts = []
    for att in message.attachments[:3]:
        if att.size > 100_000 or not att.filename.lower().endswith(TEXT_EXT):
            continue
        try:
            raw = await att.read()
        except discord.HTTPException:
            continue
        parts.append(f"\n\n[Attached file: {att.filename}]\n```\n{raw.decode('utf-8', 'ignore')[:12000]}\n```")
    return "".join(parts)


async def close_ai_channel(channel: discord.abc.GuildChannel, reason: str):
    AI_SESSIONS.pop(channel.id, None)
    try:
        await channel.delete(reason=reason)
    except discord.HTTPException as e:
        log.warning("AI kanalı silinemedi: %s", e)


class AISessionControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Reset Memory", style=discord.ButtonStyle.secondary, emoji="🧹", custom_id="reset_ai_memory_v1")
    async def reset_memory(self, interaction: discord.Interaction, button: ui.Button):
        session = AI_SESSIONS.get(interaction.channel.id)
        if not session:
            return await interaction.response.send_message("❌ Bu oturum artık aktif değil.", ephemeral=True)
        if interaction.user.id != session.user_id:
            return await interaction.response.send_message("❌ Yalnızca oturum sahibi hafızayı sıfırlayabilir.", ephemeral=True)
        session.history.clear()
        session.turns = 0
        await interaction.response.send_message(
            embed=discord.Embed(description="🧹 **Konuşma hafızası sıfırlandı.** Temiz bir sayfayla devam edebilirsin.", color=C.SUCCESS))

    @ui.button(label="Close AI Session", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ai_session_v1")
    async def close_session(self, interaction: discord.Interaction, button: ui.Button):
        session = AI_SESSIONS.get(interaction.channel.id)
        user = interaction.user
        allowed = (
            user.id == interaction.guild.owner_id
            or (isinstance(user, discord.Member) and user.guild_permissions.administrator)
            or (session and session.user_id == user.id)
        )
        if not allowed:
            return await interaction.response.send_message(
                "❌ Bu oturumu yalnızca oturumu açan kullanıcı veya yönetici kapatabilir.", ephemeral=True)
        await interaction.response.send_message(
            embed=discord.Embed(description="🔄 **AI oturumu kapatılıyor...**", color=C.WARN))
        await asyncio.sleep(2)
        await close_ai_channel(interaction.channel, f"AI session closed by {user}")
        log.info("AI oturumu kapatıldı: %s", interaction.channel.name)


async def create_ai_session(interaction: discord.Interaction):
    guild, user = interaction.guild, interaction.user

    for ch_id, sess in list(AI_SESSIONS.items()):
        if sess.user_id == user.id:
            ch = guild.get_channel(ch_id)
            if ch:
                return await interaction.followup.send(f"⚠️ Zaten açık bir AI oturumun var: {ch.mention}", ephemeral=True)
            AI_SESSIONS.pop(ch_id, None)

    category = guild.get_channel(TICKET_CATEGORY_ID)
    category = category if isinstance(category, discord.CategoryChannel) else None
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, embed_links=True),
    }
    safe = re.sub(r"[^a-z0-9]", "", user.name.lower())[:10] or "user"
    ch_name = f"ai-{safe}-{str(user.id)[-4:]}"
    channel = await guild.create_text_channel(
        name=ch_name, category=category, overwrites=overwrites,
        topic=f"🤖 Hyacinth AI Session | User: {user} | Auto-closes after 10 min of inactivity",
        reason=f"AI session for {user}",
    )
    AI_SESSIONS[channel.id] = AISession(user_id=user.id)

    desc = (
        f"Merhaba {user.mention}! 👋\n\n"
        "**Hyacinth AI** aktif ve sana yardım etmeye hazır.\n\n"
        "💡 **Neler yapabilirsin?**\n"
        "▫️ Kod yazdırabilir veya debug ettirebilirsin\n"
        "▫️ `.py` `.js` `.json` `.txt` gibi dosyaları **yükleyerek** incelettirebilirsin\n"
        "▫️ Oyun geliştirme ve web sorularını sorabilirsin\n"
        "▫️ `//` ile başlayan mesajlar AI'a gönderilmez (yan sohbet)\n\n"
        "⚠️ **10 dakika** mesaj gelmezse oda otomatik silinir."
    )
    embed = discord.Embed(title="🤖 Hyacinth AI — Debug Session", description=desc, color=C.PRIMARY,
                          timestamp=discord.utils.utcnow())
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="Winter Hyacinth • AI Assistant | Powered by Gemini")
    await channel.send(embed=embed, view=AISessionControlView())
    await interaction.followup.send(f"✅ AI oturumun hazır: {channel.mention}", ephemeral=True)
    log.info("Yeni AI oturumu: %s -> %s", user, ch_name)


def ticket_owner_id(channel) -> Optional[int]:
    m = re.search(r"ticket-owner:(\d+)", getattr(channel, "topic", None) or "")
    return int(m.group(1)) if m else None


def find_open_ticket(guild: discord.Guild, user_id: int) -> Optional[discord.TextChannel]:
    return next((ch for ch in guild.text_channels if ticket_owner_id(ch) == user_id), None)


async def build_transcript(channel: discord.TextChannel, closer: discord.abc.User) -> bytes:
    lines = [
        "--- WINTER HYACINTH TICKET LOG ---",
        f"Channel:   {channel.name}",
        f"Closed By: {closer}",
        f"Date:      {discord.utils.utcnow():%Y-%m-%d %H:%M UTC}",
        "----------------------------------", "",
    ]
    async for m in channel.history(limit=None, oldest_first=True):
        lines.append(f"[{m.created_at:%Y-%m-%d %H:%M:%S}] {m.author.display_name}: {m.clean_content}")
        for a in m.attachments:
            lines.append(f"    📎 {a.filename} -> {a.url}")
        for e in m.embeds:
            if e.title or e.description:
                lines.append(f"    [embed] {e.title or ''} {truncate(e.description or '', 200)}")
    return "\n".join(lines).encode("utf-8")


async def finalize_ticket(channel: discord.TextChannel, closer: discord.Member):
    guild = channel.guild
    data = await build_transcript(channel, closer)
    fname = f"transcript-{channel.name}.txt"
    owner_id = ticket_owner_id(channel)

    embed = discord.Embed(
        title="📑 Ticket Archived", color=C.DARK, timestamp=discord.utils.utcnow(),
        description=f"**Ticket:** `{channel.name}`\n**Owner:** <@{owner_id}>\n**Closed By:** {closer.mention}" if owner_id
        else f"**Ticket:** `{channel.name}`\n**Closed By:** {closer.mention}",
    )
    await send_log(guild, embed, discord.File(io.BytesIO(data), filename=fname))

    owner = guild.get_member(owner_id) if owner_id else None
    if owner and owner.id != closer.id:
        try:
            dm = discord.Embed(title="🎫 Ticket'ın kapatıldı",
                               description=f"**{guild.name}** sunucusundaki `{channel.name}` ticket'ı kapatıldı.\nKayıt ektedir.",
                               color=C.INFO)
            await owner.send(embed=dm, file=discord.File(io.BytesIO(data), filename=fname))
        except discord.HTTPException:
            pass
    await asyncio.sleep(2)
    await channel.delete(reason=f"Ticket closed by {closer}")


class ConfirmCloseView(ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @ui.button(label="Yes, close it", style=discord.ButtonStyle.danger, emoji="🔒")
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🔄 **Transkript hazırlanıyor, kanal kapatılıyor...**", view=None)
        await finalize_ticket(interaction.channel, interaction.user)

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="✅ İptal edildi.", view=None)


class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, emoji="🛡️", custom_id="claim_v11")
    async def claim(self, interaction: discord.Interaction, button: ui.Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Only authorized staff can claim this ticket.", ephemeral=True)
        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(embed=discord.Embed(
            description=f"✅ **{interaction.user.mention}** has taken responsibility.", color=C.SUCCESS))

    @ui.button(label="Close & Archive", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_v11")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        if not (is_staff(interaction.user) or interaction.user.id == ticket_owner_id(interaction.channel)):
            return await interaction.response.send_message("❌ Access denied.", ephemeral=True)
        await interaction.response.send_message(
            "⚠️ Bu ticket'ı kapatıp arşivlemek istediğine emin misin?", view=ConfirmCloseView(), ephemeral=True)


async def create_ticket(interaction: discord.Interaction, subject: str, details: str):
    guild, user = interaction.guild, interaction.user

    existing = find_open_ticket(guild, user.id)
    if existing:
        return await interaction.followup.send(f"⚠️ Zaten açık bir ticket'ın var: {existing.mention}", ephemeral=True)

    category = guild.get_channel(TICKET_CATEGORY_ID)
    category = category if isinstance(category, discord.CategoryChannel) else None
    staff = guild.get_role(STAFF_ROLE_ID)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
    }
    if staff:
        overwrites[staff] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)

    safe = re.sub(r"[^a-z0-9]", "", user.name.lower())[:10] or "user"
    channel = await guild.create_text_channel(
        name=f"ticket-{safe}-{str(user.id)[-4:]}", category=category, overwrites=overwrites,
        topic=f"ticket-owner:{user.id} | {truncate(subject, 100)}", reason=f"Ticket opened by {user}")

    embed = discord.Embed(
        title="❄️ Welcome to Support",
        description=f"Hello {user.mention}, our staff has been notified.\nSomeone will be with you shortly.",
        color=C.INFO, timestamp=discord.utils.utcnow())
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="📌 Subject", value=truncate(subject, 256), inline=False)
    embed.add_field(name="📝 Details", value=truncate(details, 1024), inline=False)
    embed.add_field(name="👤 Account Created", value=discord.utils.format_dt(user.created_at, "R"), inline=True)
    embed.set_footer(text="Staff: use the buttons below")

    mention_text = f"{staff.mention if staff else ''} {user.mention}".strip()
    await channel.send(content=mention_text, embed=embed, view=TicketControlView(),
                       allowed_mentions=discord.AllowedMentions(roles=True, users=True))
    await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)
    await send_log(guild, discord.Embed(title="🎫 Ticket Opened", color=C.INFO, timestamp=discord.utils.utcnow(),
                                        description=f"{user.mention} → {channel.mention}\n**Subject:** {truncate(subject, 200)}"))


class TicketModal(ui.Modal, title="🎫 Open Support Ticket"):
    subject = ui.TextInput(label="Subject", placeholder="Kısaca sorunun nedir?", min_length=3, max_length=100)
    details = ui.TextInput(label="Details", style=discord.TextStyle.paragraph, required=False, max_length=1000,
                           placeholder="Sorununu detaylı anlat (opsiyonel)")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await create_ticket(interaction, str(self.subject), str(self.details) or "—")


class CareerLinkView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        body = ("Name/Nickname:\nAge:\nRole (Developer/Designer/etc):\n"
                "Portfolio/Experience:\nWhy do you want to join Winter Hyacinth?:")
        url = ("https://mail.google.com/mail/?view=cm&fs=1&to=winterhyacinth.contact@gmail.com"
               f"&su={urllib.parse.quote('Winter Hyacinth - Job Application')}&body={urllib.parse.quote(body)}")
        self.add_item(ui.Button(label="Send Application via Gmail", url=url, emoji="📧"))


class FAQDropdown(ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="✨ Select a Service...", min_values=1, max_values=1, custom_id="faq_select_v12",
            options=[
                discord.SelectOption(label="Careers", description="Apply to join our creative team.", emoji="💼"),
                discord.SelectOption(label="Open Support Ticket", description="Get direct help from our staff.", emoji="🎫"),
                discord.SelectOption(label="Debug with AI", description="Get instant AI-powered coding & debug help.", emoji="🤖"),
            ])

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        if choice == "Open Support Ticket":
            await interaction.response.send_modal(TicketModal())
        elif choice == "Debug with AI":
            await interaction.response.defer(ephemeral=True)
            await create_ai_session(interaction)
        else:
            desc = ("We are constantly evolving and looking for new talents to join our vision.\n\n"
                    "**How to apply?**\n1. Click the button below to open Gmail.\n"
                    "2. Fill in your personal details.\n3. Send your application to our official mail.\n"
                    "📧 **Contact:** `winterhyacinth.contact@gmail.com`")
            embed = discord.Embed(title="💼 Join the Winter Hyacinth Team", description=desc, color=C.BLURPLE)
            embed.add_field(name="Available Fields",
                            value="▫️ Game Development\n▫️ Web Technologies\n▫️ Graphic Design\n▫️ Community Management",
                            inline=False)
            embed.set_footer(text="Winter Hyacinth • Career Dept",
                             icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            await interaction.response.send_message(embed=embed, view=CareerLinkView(), ephemeral=True)

        # Menüyü sıfırla: seçilen seçenek görünür kalmasın
        try:
            await interaction.message.edit(view=FAQView())
        except discord.HTTPException:
            pass


class FAQView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(FAQDropdown())



class WinterBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)
        self.start_time = time.time()
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.gemini: Optional[GeminiClient] = None
        self._status_i = 0

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
        self.gemini = GeminiClient(self.http_session)

        self.add_view(FAQView())
        self.add_view(TicketControlView())
        self.add_view(AISessionControlView())

        for loop in (self.github_loop, self.devlog_loop, self.stats_loop, self.presence_loop, self.ai_timeout_loop):
            loop.start()

        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        try:
            synced = await self.tree.sync(guild=guild)
            log.info("✅ %d slash komutu senkronize edildi.", len(synced))
        except Exception as e:
            log.error("Slash senkronizasyon hatası: %s", e)

    async def close(self):
        if self.http_session:
            await self.http_session.close()
        await super().close()

    async def on_ready(self):
        log.info("💎 Winter Hyacinth Bot hazır: %s (%s sunucu)", self.user, len(self.guilds))

    async def on_guild_channel_delete(self, channel):
        AI_SESSIONS.pop(channel.id, None)

    @tasks.loop(minutes=2)
    async def github_loop(self):
        await self.wait_until_ready()
        await self.check_github()

    @tasks.loop(minutes=2)
    async def devlog_loop(self):
        await self.wait_until_ready()
        await self.check_devlogs()

    @tasks.loop(minutes=10)  # kanal adı değişimi Discord'da 10 dk'da 2 ile sınırlı
    async def stats_loop(self):
        await self.wait_until_ready()
        guild = self.get_guild(GUILD_ID)
        ch = guild.get_channel(MEMBER_COUNT_CH) if guild else None
        if not ch:
            return
        new_name = f"👥 Members: {guild.member_count}"
        if ch.name != new_name:
            try:
                await ch.edit(name=new_name, reason="Member count update")
            except discord.HTTPException as e:
                log.warning("Üye sayacı güncellenemedi: %s", e)

    @tasks.loop(seconds=60)
    async def presence_loop(self):
        await self.wait_until_ready()
        guild = self.get_guild(GUILD_ID)
        options = list(STATUS_OPTIONS)
        if guild:
            options.append(f"👥 {guild.member_count} Members")
        self._status_i = (self._status_i + 1) % len(options)
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=options[self._status_i]))

    @tasks.loop(seconds=30)
    async def ai_timeout_loop(self):
        await self.wait_until_ready()
        guild = self.get_guild(GUILD_ID)
        if not guild:
            return
        now = time.time()
        for ch_id, session in list(AI_SESSIONS.items()):
            idle = now - session.last_activity
            channel = guild.get_channel(ch_id)
            if not channel:
                AI_SESSIONS.pop(ch_id, None)
                continue
            try:
                if idle >= AI_IDLE_LIMIT and not session.lock.locked():
                    await channel.send(embed=discord.Embed(
                        title="⏱️ Session Timed Out",
                        description="Bu AI oturumu **10 dakika** boyunca aktif olmadığı için kapatılıyor...", color=C.ERROR))
                    await asyncio.sleep(3)
                    await close_ai_channel(channel, "AI session timed out")
                elif idle >= AI_IDLE_WARN and not session.warned:
                    session.warned = True
                    await channel.send(embed=discord.Embed(
                        description="⚠️ **1 dakika** içinde mesaj gelmezse bu oturum kapanacak.", color=C.WARN))
            except discord.HTTPException as e:
                log.warning("AI timeout hatası: %s", e)

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        session = AI_SESSIONS.get(message.channel.id)
        if not session:
            return
        if message.author.id != session.user_id and message.author.id != message.guild.owner_id:
            return
        if message.content.startswith("//"):
            return

        prompt = message.content + await read_attachments(message)
        if not prompt.strip():
            return

        async with session.lock:
            session.last_activity, session.warned = time.time(), False
            async with message.channel.typing():
                ok, text, model = await self.gemini.generate(session.history, prompt)

            if ok:
                session.history += [{"role": "user", "parts": [{"text": prompt}]},
                                    {"role": "model", "parts": [{"text": text}]}]
                session.history = session.history[-AI_MAX_HISTORY:]
                session.turns += 1
                if model != GEMINI_MODELS[0]:
                    text += f"\n-# ⚡ {model}"
            session.last_activity = time.time()

            ref = message.to_reference(fail_if_not_exists=False)
            for i, chunk in enumerate(split_message(text)):
                await message.channel.send(chunk, reference=ref if i == 0 else None,
                                           mention_author=False, allowed_mentions=NO_MENTIONS)
                await asyncio.sleep(0.3)

    # ---- GitHub --------------------------------------------------------------
    @staticmethod
    def build_commit_embed(repo: str, d: dict) -> discord.Embed:
        repo_name = repo.split("/")[-1]
        commit = d["commit"]
        stats = d.get("stats", {})
        icons = {"added": "🟢 **Added:**", "modified": "🟡 **Modified:**", "removed": "🔴 **Removed:**", "renamed": "🔵 **Renamed:**"}

        files = d.get("files", [])
        summary = [f"{icons.get(f.get('status'), '⚪')} `{truncate(f.get('filename'), 60)}`" for f in files[:10]]
        if len(files) > 10:
            summary.append(f"*and {len(files) - 10} more files...*")

        embed = discord.Embed(title=f"🚀 GitHub Update: {repo_name}", url=d["html_url"], color=C.SUCCESS,
                              timestamp=discord.utils.utcnow())
        embed.set_author(name=f"Push by {commit['author']['name']}",
                         icon_url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png")
        message = truncate(commit["message"], 900).replace("```", "'''")
        embed.description = f"**Commit Message:**\n```text\n{message}\n```"
        embed.add_field(name="📊 Commit Statistics", inline=False, value=(
            f"🔹 **Total Lines Changed:** `{stats.get('total', 0)}`\n"
            f"➕ **Additions:** `{stats.get('additions', 0)}`\n➖ **Deletions:** `{stats.get('deletions', 0)}`"))
        embed.add_field(name="📋 Modified Files", value=truncate("\n".join(summary) or "No structural file changes.", 1024), inline=False)
        embed.add_field(name="🔗 Code Review", value=f"[Review on GitHub]({d['html_url']})")
        embed.set_footer(text=f"{d['sha'][:7]}")
        return embed

    async def check_github(self):
        try:
            headers = {"User-Agent": "WinterHyacinthBot", "Accept": "application/vnd.github+json"}
            if GITHUB_TOKEN:
                headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

            for repo in GITHUB_REPOS:
                api_url = f"https://api.github.com/repos/{repo}/commits"
                async with self.http_session.get(api_url, headers=headers, params={"per_page": 10}) as resp:
                    if resp.status != 200:
                        log.warning("GitHub %s HTTP %s", repo, resp.status)
                        continue
                    commits = await resp.json()
                if not commits:
                    continue

                latest = commits[0]["sha"]
                last = LAST_DATA["commits"].get(repo)
                if last is None:
                    LAST_DATA["commits"][repo] = latest
                    log.info("GitHub izleniyor: %s", repo)
                    continue
                if last == latest:
                    continue

                new = []
                for c in commits:
                    if c["sha"] == last:
                        break
                    new.append(c)
                else:
                    new = new[:1]  # force-push vb. durumunda sadece en yeniyi duyur

                ch = self.get_channel(ANNOUNCE_CH_ID)
                for c in reversed(new[:5]):
                    async with self.http_session.get(f"{api_url}/{c['sha']}", headers=headers) as d_resp:
                        if d_resp.status != 200:
                            continue
                        detail = await d_resp.json()
                    if ch:
                        await ch.send(content="🔔 **New Repository Activity Detected!**",
                                      embed=self.build_commit_embed(repo, detail), allowed_mentions=NO_MENTIONS)
                        log.info("GitHub: %s -> %s", repo, c["sha"][:7])
                LAST_DATA["commits"][repo] = latest
                await asyncio.sleep(0.5)
        except Exception:
            log.exception("GitHub kontrol hatası")

    async def check_devlogs(self):
        try:
            headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache",
                       "User-Agent": "WinterHyacinthBot"}
            if GITHUB_TOKEN:
                headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

            async with self.http_session.get(JSON_URL, headers=headers) as resp:
                if resp.status != 200:
                    return
                gist = await resp.json()

            content = (gist.get("files", {}).get("posts.json") or {}).get("content")
            if not content:
                return
            posts = [p for p in json.loads(content) if str(p.get("id", "")).isdigit()]
            if not posts:
                return

            newest = max(int(p["id"]) for p in posts)
            if LAST_DATA["post_id"] is None:
                LAST_DATA["post_id"] = str(newest)
                log.info("Devlog izleniyor (son ID: %s)", newest)
                return

            ch = self.get_channel(ANNOUNCE_CH_ID)
            if not ch:
                return
            old_id = int(LAST_DATA["post_id"])
            for post in sorted((p for p in posts if int(p["id"]) > old_id), key=lambda p: int(p["id"])):
                pid = str(post["id"])
                embed = discord.Embed(title=truncate(f"❄️ NEW DEVLOG: {post.get('baslik', 'Untitled')}", 256),
                                      description=truncate(post.get("ozet") or "", 2000), color=C.PRIMARY,
                                      url=f"{WEB_URL}?id={pid}", timestamp=discord.utils.utcnow())
                embed.add_field(name="Link", value=f"🔗 [Open Devlog]({WEB_URL}?id={pid})")
                banner = post.get("banner")
                if banner:
                    embed.set_image(url=f"{SITE_URL}/{banner}" if banner.startswith("img/") else banner)
                await ch.send(content="🔔 **New Article!**" + (" @everyone" if PING_EVERYONE_ON_DEVLOG else ""),
                              embed=embed, allowed_mentions=discord.AllowedMentions(everyone=PING_EVERYONE_ON_DEVLOG))
                LAST_DATA["post_id"] = pid
        except Exception:
            log.exception("Devlog kontrol hatası")


bot = WinterBot()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ Bu komut için yetkin yok."
    elif isinstance(error, app_commands.BotMissingPermissions):
        msg = "❌ Botun bu işlem için yetkisi yok. Rol/izinlerini kontrol et."
    elif isinstance(error, app_commands.CommandOnCooldown):
        msg = f"⏳ Çok hızlısın! **{error.retry_after:.1f} sn** sonra tekrar dene."
    else:
        log.exception("Komut hatası", exc_info=error)
        msg = "❌ Beklenmeyen bir hata oluştu. Lütfen tekrar dene."
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


HELP_PAGES = {
    "overview": ("❄️ Winter Hyacinth — Yardım Merkezi",
                 "Aşağıdaki menüden bir kategori seçerek komutları görebilirsin.\n\n"
                 "🌐 **Genel** — ping, info, userinfo, avatar, poll\n"
                 "🤖 **AI** — Gemini destekli sorular ve oturumlar\n"
                 "🎫 **Destek** — ticket sistemi\n"
                 "🛡️ **Moderasyon** — yetkililere özel araçlar"),
    "general": ("🌐 Genel Komutlar",
                "`/ping` — Gecikme ve API hızı\n`/info` — Sunucu & bot bilgisi\n"
                "`/userinfo [üye]` — Üye profili\n`/avatar [üye]` — Profil fotoğrafı\n"
                "`/poll` — 2-4 seçenekli anket oluştur"),
    "ai": ("🤖 AI Komutları",
           "`/ai <soru>` — Hızlı tek seferlik soru\n"
           "**Debug with AI** — Panelden özel, hafızalı oturum aç\n"
           "▫️ Dosya yükleyerek kod inceletebilirsin\n▫️ `//` ile başlayan mesajlar yok sayılır\n"
           "▫️ 🧹 butonu ile hafızayı sıfırla"),
    "support": ("🎫 Destek Komutları",
                "`/ticket` — Destek talebi aç\n`/ticketadd <üye>` — *(Staff)* Ticket'a üye ekle\n"
                "`/ticketremove <üye>` — *(Staff)* Ticket'tan üye çıkar\n`/setup` — *(Admin)* Panel gönder"),
    "moderation": ("🛡️ Moderasyon Komutları",
                   "`/clear <sayı> [üye]` — Mesaj sil\n`/kick` `/ban` — Üyeyi at / yasakla\n"
                   "`/timeout` `/untimeout` — Susturma\n`/slowmode <sn>` — Yavaş mod\n"
                   "Tüm işlemler log kanalına kaydedilir."),
}


def help_embed(key: str) -> discord.Embed:
    title, desc = HELP_PAGES[key]
    embed = discord.Embed(title=title, description=desc, color=C.PRIMARY)
    embed.set_footer(text="Winter Hyacinth • Official Bot")
    return embed


class HelpView(ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.message: Optional[discord.Message] = None

    @ui.select(placeholder="📚 Kategori seç...", options=[
        discord.SelectOption(label="Genel", value="general", emoji="🌐"),
        discord.SelectOption(label="AI", value="ai", emoji="🤖"),
        discord.SelectOption(label="Destek", value="support", emoji="🎫"),
        discord.SelectOption(label="Moderasyon", value="moderation", emoji="🛡️"),
        discord.SelectOption(label="Ana Sayfa", value="overview", emoji="🏠"),
    ])
    async def pick(self, interaction: discord.Interaction, select: ui.Select):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Bu menü sana ait değil. `/help` yazarak kendi menünü aç.", ephemeral=True)
        await interaction.response.edit_message(embed=help_embed(select.values[0]), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


@bot.tree.command(name="help", description="Tüm komutları ve özellikleri gösterir.")
async def help_slash(interaction: discord.Interaction):
    view = HelpView(interaction.user.id)
    await interaction.response.send_message(embed=help_embed("overview"), view=view, ephemeral=True)
    view.message = await interaction.original_response()


@bot.tree.command(name="ping", description="Botun gecikme süresini ve API hızını gösterir.")
async def ping_slash(interaction: discord.Interaction):
    ws = round(bot.latency * 1000)
    t0 = time.perf_counter()
    await interaction.response.send_message("🏓 Ölçülüyor...")
    api = round((time.perf_counter() - t0) * 1000)
    color = C.SUCCESS if ws < 150 else C.WARN if ws < 300 else C.ERROR
    embed = discord.Embed(title="🏓 Pong!", color=color)
    embed.add_field(name="📡 WebSocket", value=f"`{ws} ms`")
    embed.add_field(name="⚡ API", value=f"`{api} ms`")
    embed.add_field(name="⏱️ Uptime", value=f"`{fmt_uptime(time.time() - bot.start_time)}`")
    await interaction.edit_original_response(content=None, embed=embed)


@bot.tree.command(name="info", description="Winter Hyacinth sunucusu ve bot hakkında bilgi verir.")
@app_commands.guild_only()
async def info_slash(interaction: discord.Interaction):
    guild = interaction.guild
    humans = sum(1 for m in guild.members if not m.bot)
    embed = discord.Embed(title="❄️ Winter Hyacinth — Sunucu & Bot Bilgisi", color=C.PRIMARY, timestamp=discord.utils.utcnow())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👥 Üyeler", value=f"`{guild.member_count}` (👤 {humans} • 🤖 {guild.member_count - humans})")
    embed.add_field(name="💬 Kanallar", value=f"`{len(guild.text_channels)}` yazı • `{len(guild.voice_channels)}` ses")
    embed.add_field(name="👑 Sahip", value=f"<@{guild.owner_id}>")
    embed.add_field(name="📅 Kuruluş", value=discord.utils.format_dt(guild.created_at, "D"))
    embed.add_field(name="🚀 Boost", value=f"Seviye `{guild.premium_tier}` • `{guild.premium_subscription_count}`")
    embed.add_field(name="🆔 Sunucu ID", value=f"`{guild.id}`")
    embed.add_field(name="🤖 Bot", value=f"`{bot.latency * 1000:.0f} ms` • uptime `{fmt_uptime(time.time() - bot.start_time)}`", inline=False)
    embed.add_field(name="🧠 Aktif AI Oturumu", value=f"`{len(AI_SESSIONS)}`")
    embed.set_footer(text="Winter Hyacinth • Official Bot")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="userinfo", description="Bir üyenin profil bilgilerini gösterir.")
@app_commands.describe(member="Bilgisine bakılacak üye (boş bırakırsan sen)")
@app_commands.guild_only()
async def userinfo_slash(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    roles = [r.mention for r in reversed(member.roles) if r != interaction.guild.default_role]
    embed = discord.Embed(title=f"👤 {member.display_name}", color=member.color if member.color.value else C.PRIMARY,
                          timestamp=discord.utils.utcnow())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏷️ Kullanıcı", value=f"{member} {'🤖' if member.bot else ''}")
    embed.add_field(name="🆔 ID", value=f"`{member.id}`")
    embed.add_field(name="📅 Hesap", value=discord.utils.format_dt(member.created_at, "R"))
    embed.add_field(name="📥 Katılım", value=discord.utils.format_dt(member.joined_at, "R") if member.joined_at else "—")
    embed.add_field(name="🎖️ En Yüksek Rol", value=member.top_role.mention)
    embed.add_field(name=f"📜 Roller ({len(roles)})", value=truncate(" ".join(roles[:15]) or "—", 1024), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="avatar", description="Bir üyenin profil fotoğrafını büyük gösterir.")
@app_commands.describe(member="Üye (boş bırakırsan sen)")
async def avatar_slash(interaction: discord.Interaction, member: Optional[discord.User] = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"🖼️ {member.display_name}", color=C.PRIMARY)
    embed.set_image(url=member.display_avatar.with_size(1024).url)
    view = ui.View()
    view.add_item(ui.Button(label="Open Original", url=member.display_avatar.url, emoji="🔗"))
    await interaction.response.send_message(embed=embed, view=view)


NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]


@bot.tree.command(name="poll", description="Reaksiyonlu bir anket oluşturur.")
@app_commands.describe(question="Anket sorusu", option1="1. seçenek", option2="2. seçenek",
                       option3="3. seçenek (opsiyonel)", option4="4. seçenek (opsiyonel)")
@app_commands.guild_only()
async def poll_slash(interaction: discord.Interaction, question: str, option1: str, option2: str,
                     option3: Optional[str] = None, option4: Optional[str] = None):
    options = [o for o in (option1, option2, option3, option4) if o]
    embed = discord.Embed(title=f"📊 {truncate(question, 250)}", color=C.PRIMARY, timestamp=discord.utils.utcnow(),
                          description="\n\n".join(f"{NUM_EMOJIS[i]}  {truncate(o, 200)}" for i, o in enumerate(options)))
    embed.set_footer(text=f"Anketi başlatan: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, allowed_mentions=NO_MENTIONS)
    msg = await interaction.original_response()
    for i in range(len(options)):
        await msg.add_reaction(NUM_EMOJIS[i])

@bot.tree.command(name="ai", description="Gemini AI modeline hızlıca soru sorarsınız.")
@app_commands.describe(prompt="Sormak istediğiniz soru veya kod problemi")
@app_commands.checks.cooldown(1, 8.0, key=lambda i: i.user.id)
async def ai_slash(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    ok, text, model = await bot.gemini.generate([], prompt)

    q = discord.Embed(description=f"💬 {truncate(prompt, 500)}", color=C.PRIMARY if ok else C.ERROR)
    q.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    q.set_footer(text=f"Hyacinth AI • {model or 'Gemini'}")
    await interaction.followup.send(embed=q, allowed_mentions=NO_MENTIONS)
    for chunk in split_message(text):
        await interaction.followup.send(chunk, allowed_mentions=NO_MENTIONS)
        await asyncio.sleep(0.3)


@bot.tree.command(name="ticket", description="Destek bilet odası açar.")
@app_commands.guild_only()
async def ticket_slash(interaction: discord.Interaction):
    await interaction.response.send_modal(TicketModal())


def _ticket_channel_guard(interaction: discord.Interaction) -> Optional[str]:
    if not is_staff(interaction.user):
        return "❌ Bu komutu yalnızca yetkililer kullanabilir."
    if ticket_owner_id(interaction.channel) is None:
        return "❌ Bu komut sadece ticket kanallarında kullanılabilir."
    return None


@bot.tree.command(name="ticketadd", description="Ticket odasına bir üye ekler.")
@app_commands.guild_only()
async def ticketadd_slash(interaction: discord.Interaction, member: discord.Member):
    if err := _ticket_channel_guard(interaction):
        return await interaction.response.send_message(err, ephemeral=True)
    await interaction.channel.set_permissions(member, read_messages=True, send_messages=True, attach_files=True)
    await interaction.response.send_message(embed=discord.Embed(description=f"➕ {member.mention} ticket'a eklendi.", color=C.SUCCESS))


@bot.tree.command(name="ticketremove", description="Ticket odasından bir üyeyi çıkarır.")
@app_commands.guild_only()
async def ticketremove_slash(interaction: discord.Interaction, member: discord.Member):
    if err := _ticket_channel_guard(interaction):
        return await interaction.response.send_message(err, ephemeral=True)
    if member.id == ticket_owner_id(interaction.channel):
        return await interaction.response.send_message("❌ Ticket sahibi çıkarılamaz.", ephemeral=True)
    await interaction.channel.set_permissions(member, overwrite=None)
    await interaction.response.send_message(embed=discord.Embed(description=f"➖ {member.mention} ticket'tan çıkarıldı.", color=C.WARN))


@bot.tree.command(name="setup", description="Winter Hyacinth destek ve kariyer panelini gönderir.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.default_permissions(administrator=True)
@app_commands.guild_only()
async def setup_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="❄️ WINTER HYACINTH HUB", color=C.DARK,
                          description="Official Career & Support Center. Select an option below to proceed.")
    embed.set_image(url="https://i.imgur.com/jlevP0F.jpeg")
    embed.set_footer(text="Reliability • Innovation • Quality")
    await interaction.response.send_message(embed=embed, view=FAQView())
    log.info("/setup çalıştırıldı: %s", interaction.user)


def mod_guard(interaction: discord.Interaction, target: discord.Member) -> Optional[str]:
    guild = interaction.guild
    if target.id == interaction.user.id:
        return "Kendine bu işlemi uygulayamazsın."
    if target.id == guild.owner_id:
        return "Sunucu sahibine işlem uygulanamaz."
    if target.id == guild.me.id:
        return "Bana bu işlemi uygulayamazsın 😄"
    if interaction.user.id != guild.owner_id and target.top_role >= interaction.user.top_role:
        return "Bu üyenin rolü seninkine eşit veya daha yüksek."
    if target.top_role >= guild.me.top_role:
        return "Botun rolü bu üyeden yüksek değil. Bot rolünü yukarı taşı."
    return None


async def mod_log(interaction: discord.Interaction, action: str, target, reason: str, color: int, extra: str = ""):
    embed = discord.Embed(title=f"🛡️ {action}", color=color, timestamp=discord.utils.utcnow())
    embed.add_field(name="Hedef", value=f"{target.mention} (`{target.id}`)")
    embed.add_field(name="Yetkili", value=interaction.user.mention)
    embed.add_field(name="Sebep", value=truncate(reason, 1000), inline=False)
    if extra:
        embed.add_field(name="Detay", value=extra, inline=False)
    await send_log(interaction.guild, embed)


def mod_result(text: str, color: int) -> discord.Embed:
    return discord.Embed(description=text, color=color)


@bot.tree.command(name="clear", description="Belirtilen miktarda mesajı siler.")
@app_commands.describe(amount="Silinecek mesaj sayısı (1-100)", member="Sadece bu üyenin mesajlarını sil")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.checks.bot_has_permissions(manage_messages=True)
@app_commands.default_permissions(manage_messages=True)
@app_commands.guild_only()
async def clear_slash(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100],
                      member: Optional[discord.Member] = None):
    await interaction.response.defer(ephemeral=True)
    check = (lambda m: m.author.id == member.id) if member else None
    deleted = await interaction.channel.purge(limit=amount, check=check)
    await interaction.followup.send(embed=mod_result(f"🧹 **{len(deleted)}** mesaj temizlendi.", C.SUCCESS), ephemeral=True)
    await send_log(interaction.guild, discord.Embed(
        title="🧹 Mesajlar Temizlendi", color=C.INFO, timestamp=discord.utils.utcnow(),
        description=f"{interaction.user.mention} → {interaction.channel.mention}: **{len(deleted)}** mesaj"
                    + (f" ({member.mention})" if member else "")))


@bot.tree.command(name="kick", description="Bir üyeyi sunucudan atar.")
@app_commands.describe(member="Atılacak üye", reason="Sebep")
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.checks.bot_has_permissions(kick_members=True)
@app_commands.default_permissions(kick_members=True)
@app_commands.guild_only()
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "Sebep belirtilmedi"):
    if err := mod_guard(interaction, member):
        return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
    await member.kick(reason=f"{interaction.user}: {reason}")
    await interaction.response.send_message(embed=mod_result(f"👢 **{member}** sunucudan atıldı.\n**Sebep:** {reason}", C.WARN))
    await mod_log(interaction, "Kick", member, reason, C.WARN)


@bot.tree.command(name="ban", description="Bir üyeyi sunucudan yasaklar.")
@app_commands.describe(member="Yasaklanacak üye", reason="Sebep", delete_days="Silinecek mesaj geçmişi (gün)")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.checks.bot_has_permissions(ban_members=True)
@app_commands.default_permissions(ban_members=True)
@app_commands.guild_only()
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "Sebep belirtilmedi",
                    delete_days: app_commands.Range[int, 0, 7] = 0):
    if err := mod_guard(interaction, member):
        return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
    await interaction.guild.ban(member, reason=f"{interaction.user}: {reason}", delete_message_seconds=delete_days * 86400)
    await interaction.response.send_message(embed=mod_result(f"🔨 **{member}** yasaklandı.\n**Sebep:** {reason}", C.ERROR))
    await mod_log(interaction, "Ban", member, reason, C.ERROR, f"Mesaj silme: {delete_days} gün")


@bot.tree.command(name="timeout", description="Bir üyeyi süreli susturur.")
@app_commands.describe(member="Susturulacak üye", duration="Süre", reason="Sebep")
@app_commands.choices(duration=[
    app_commands.Choice(name="60 saniye", value=1), app_commands.Choice(name="5 dakika", value=5),
    app_commands.Choice(name="10 dakika", value=10), app_commands.Choice(name="1 saat", value=60),
    app_commands.Choice(name="1 gün", value=1440), app_commands.Choice(name="1 hafta", value=10080),
])
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.checks.bot_has_permissions(moderate_members=True)
@app_commands.default_permissions(moderate_members=True)
@app_commands.guild_only()
async def timeout_slash(interaction: discord.Interaction, member: discord.Member,
                        duration: app_commands.Choice[int], reason: str = "Sebep belirtilmedi"):
    if err := mod_guard(interaction, member):
        return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
    await member.timeout(timedelta(minutes=duration.value), reason=f"{interaction.user}: {reason}")
    await interaction.response.send_message(embed=mod_result(
        f"🔇 **{member}** susturuldu — **{duration.name}**\n**Sebep:** {reason}", C.WARN))
    await mod_log(interaction, "Timeout", member, reason, C.WARN, f"Süre: {duration.name}")


@bot.tree.command(name="untimeout", description="Bir üyenin susturmasını kaldırır.")
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.checks.bot_has_permissions(moderate_members=True)
@app_commands.default_permissions(moderate_members=True)
@app_commands.guild_only()
async def untimeout_slash(interaction: discord.Interaction, member: discord.Member):
    if err := mod_guard(interaction, member):
        return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
    await member.timeout(None, reason=f"Untimeout by {interaction.user}")
    await interaction.response.send_message(embed=mod_result(f"🔊 **{member}** susturması kaldırıldı.", C.SUCCESS))
    await mod_log(interaction, "Untimeout", member, "—", C.SUCCESS)


@bot.tree.command(name="slowmode", description="Kanalın yavaş modunu ayarlar (0 = kapalı).")
@app_commands.describe(seconds="Saniye (0-21600)")
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.checks.bot_has_permissions(manage_channels=True)
@app_commands.default_permissions(manage_channels=True)
@app_commands.guild_only()
async def slowmode_slash(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
    await interaction.channel.edit(slowmode_delay=seconds, reason=f"Slowmode by {interaction.user}")
    text = "🐢 Yavaş mod **kapatıldı**." if seconds == 0 else f"🐢 Yavaş mod **{seconds} sn** olarak ayarlandı."
    await interaction.response.send_message(embed=mod_result(text, C.INFO))


if __name__ == "__main__":
    if not TOKEN:
        log.critical("'.env' dosyasında DISCORD_BOT_TOKEN bulunamadı!")
        raise SystemExit(1)
    if not GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY bulunamadı! AI özellikleri çalışmayacak.")
    bot.run(TOKEN, log_handler=None)
