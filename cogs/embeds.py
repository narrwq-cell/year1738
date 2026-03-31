"""
cogs/embeds.py — Rich embed builder commands.

Commands:
  /announce  — Post a polished announcement embed to any channel
  /say       — Post a simple embed message as the bot
  /rules     — Post a numbered server-rules embed
  /roleinfo  — Rich embed for a role
  /channelinfo — Rich embed for a text channel
  /botinfo   — Bot statistics (uptime, latency, guilds, users)
"""

import discord
from discord import app_commands
from discord.ext import commands
import datetime
import platform
import importlib.metadata

# ── helpers ────────────────────────────────────────────────────────────────────

def _parse_color(hex_str: str, fallback: int = 0x5865F2) -> discord.Color:
    """Parse a hex color string like 'FF5733' or '#FF5733' into a discord.Color."""
    try:
        return discord.Color(int(hex_str.lstrip("#"), 16))
    except ValueError:
        return discord.Color(fallback)


def _progress_bar(value: int, maximum: int, length: int = 12) -> str:
    """Return a Unicode block progress bar."""
    if maximum == 0:
        filled = 0
    else:
        filled = round(length * value / maximum)
    filled = max(0, min(filled, length))
    return "█" * filled + "░" * (length - filled)


def _humanize_delta(delta: datetime.timedelta) -> str:
    """Convert a timedelta to a human-readable string like '2d 3h 14m'."""
    total = int(delta.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


# ── cog ────────────────────────────────────────────────────────────────────────

class Embeds(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /announce ──────────────────────────────────────────────────────────────

    @app_commands.command(name="announce", description="Post a polished announcement embed.")
    @app_commands.describe(
        title="Announcement title",
        description="Announcement body text",
        channel="Channel to post in (defaults to current channel)",
        color="Hex color e.g. FF5733 (default: gold)",
        thumbnail="URL of a small thumbnail image (top-right)",
        image="URL of a large banner image (bottom)",
        footer="Custom footer text",
        ping_role="Role to ping with the announcement",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def announce(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        channel: discord.TextChannel = None,
        color: str = "F0B232",
        thumbnail: str = None,
        image: str = None,
        footer: str = None,
        ping_role: discord.Role = None,
    ) -> None:
        target = channel or interaction.channel
        embed = discord.Embed(
            title=f"📢  {title}",
            description=description,
            color=_parse_color(color),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        if image:
            embed.set_image(url=image)
        footer_text = footer or f"Announced by {interaction.user}"
        embed.set_footer(
            text=footer_text,
            icon_url=interaction.user.display_avatar.url,
        )

        mention = ping_role.mention if ping_role else ""
        try:
            await target.send(content=mention or None, embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {target.mention}.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"✅ Announcement posted in {target.mention}.", ephemeral=True
        )

    # ── /say ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="say", description="Post a simple embed as the bot.")
    @app_commands.describe(
        message="The message to send",
        channel="Channel to post in (defaults to current channel)",
        color="Hex color e.g. 5865F2",
        title="Optional embed title",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def say(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: discord.TextChannel = None,
        color: str = "5865F2",
        title: str = None,
    ) -> None:
        target = channel or interaction.channel
        embed = discord.Embed(
            title=title,
            description=message,
            color=_parse_color(color),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=interaction.guild.name,
                         icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        try:
            await target.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {target.mention}.", ephemeral=True
            )
            return
        await interaction.response.send_message("✅ Message sent.", ephemeral=True)

    # ── /rules ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="rules", description="Post the server rules as a formatted embed.")
    @app_commands.describe(
        rules="Rules separated by | (e.g. 'Be respectful | No spam | No NSFW')",
        channel="Channel to post in (defaults to current channel)",
        color="Hex color (default: blurple)",
        title="Custom title (default: 📜 Server Rules)",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def rules(
        self,
        interaction: discord.Interaction,
        rules: str,
        channel: discord.TextChannel = None,
        color: str = "5865F2",
        title: str = "📜  Server Rules",
    ) -> None:
        target = channel or interaction.channel
        rule_list = [r.strip() for r in rules.split("|") if r.strip()]
        if not rule_list:
            await interaction.response.send_message("❌ No rules provided.", ephemeral=True)
            return

        number_emojis = [
            "1️⃣","2️⃣","3️⃣","4️⃣","5️⃣",
            "6️⃣","7️⃣","8️⃣","9️⃣","🔟",
        ]
        lines = []
        for i, rule in enumerate(rule_list[:10]):
            num = number_emojis[i] if i < len(number_emojis) else f"**{i + 1}.**"
            lines.append(f"{num}  {rule}")

        embed = discord.Embed(
            title=title,
            description="\n\n".join(lines),
            color=_parse_color(color),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_author(
            name=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )
        embed.set_footer(text="Please read and follow all rules.")
        try:
            await target.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {target.mention}.", ephemeral=True
            )
            return
        await interaction.response.send_message("✅ Rules posted.", ephemeral=True)

    # ── /roleinfo ──────────────────────────────────────────────────────────────

    @app_commands.command(name="roleinfo", description="Display detailed info about a role.")
    @app_commands.describe(role="The role to inspect")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role) -> None:
        member_count = len(role.members)
        # Build a short list of notable permissions
        notable = [
            ("Administrator", role.permissions.administrator),
            ("Manage Guild", role.permissions.manage_guild),
            ("Manage Roles", role.permissions.manage_roles),
            ("Manage Channels", role.permissions.manage_channels),
            ("Manage Messages", role.permissions.manage_messages),
            ("Kick Members", role.permissions.kick_members),
            ("Ban Members", role.permissions.ban_members),
            ("Mention Everyone", role.permissions.mention_everyone),
        ]
        granted = [name for name, value in notable if value] or ["None"]

        embed = discord.Embed(
            title=f"🎭  Role Info — {role.name}",
            color=role.color if role.color.value else discord.Color.greyple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        embed.add_field(name="ID", value=str(role.id), inline=True)
        embed.add_field(name="Color", value=f"`#{role.color.value:06X}`" if role.color.value else "Default", inline=True)
        embed.add_field(name="Members", value=str(member_count), inline=True)
        embed.add_field(name="Position", value=str(role.position), inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(
            name="Created",
            value=f"<t:{int(role.created_at.timestamp())}:F>",
            inline=False,
        )
        embed.add_field(
            name="Key Permissions",
            value=", ".join(granted),
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    # ── /channelinfo ───────────────────────────────────────────────────────────

    @app_commands.command(name="channelinfo", description="Display detailed info about a channel.")
    @app_commands.describe(channel="The channel to inspect (defaults to current channel)")
    async def channelinfo(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
    ) -> None:
        ch = channel or interaction.channel
        embed = discord.Embed(
            title=f"#  Channel Info — {ch.name}",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="ID", value=str(ch.id), inline=True)
        embed.add_field(name="Type", value=str(ch.type).replace("_", " ").title(), inline=True)
        embed.add_field(name="Category", value=ch.category.name if ch.category else "None", inline=True)
        embed.add_field(
            name="Created",
            value=f"<t:{int(ch.created_at.timestamp())}:F>",
            inline=False,
        )
        if isinstance(ch, discord.TextChannel):
            embed.add_field(
                name="Topic",
                value=ch.topic or "No topic set",
                inline=False,
            )
            embed.add_field(
                name="Slowmode",
                value=f"{ch.slowmode_delay}s" if ch.slowmode_delay else "Off",
                inline=True,
            )
            embed.add_field(name="NSFW", value="Yes" if ch.is_nsfw() else "No", inline=True)
            embed.add_field(name="News", value="Yes" if ch.is_news() else "No", inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /botinfo ───────────────────────────────────────────────────────────────

    @app_commands.command(name="botinfo", description="Display bot statistics and info.")
    async def botinfo(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        now = datetime.datetime.now(datetime.timezone.utc)
        start = getattr(self.bot, "start_time", None) or now
        uptime = _humanize_delta(now - start)
        latency_ms = round(self.bot.latency * 1000)
        guild_count = len(self.bot.guilds)
        user_count = sum(g.member_count for g in self.bot.guilds if g.member_count)
        command_count = len(self.bot.tree.get_commands())

        try:
            dpy_version = importlib.metadata.version("discord.py")
        except importlib.metadata.PackageNotFoundError:
            dpy_version = "unknown"

        embed = discord.Embed(
            title=f"🤖  {self.bot.user.name}",
            description="A feature-rich Discord bot for moderation, fun, and community management.",
            color=discord.Color.blurple(),
            timestamp=now,
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="⏱️  Uptime", value=uptime, inline=True)
        embed.add_field(name="🏓  Latency", value=f"{latency_ms}ms", inline=True)
        embed.add_field(name="🌐  Servers", value=str(guild_count), inline=True)
        embed.add_field(name="👥  Total Users", value=f"{user_count:,}", inline=True)
        embed.add_field(name="⚡  Slash Commands", value=str(command_count), inline=True)
        embed.add_field(name="🐍  Python", value=platform.python_version(), inline=True)
        embed.add_field(name="📦  discord.py", value=dpy_version, inline=True)
        embed.add_field(name="🖥️  Platform", value=platform.system(), inline=True)
        embed.set_footer(text="year1738 Bot")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Embeds(bot))
