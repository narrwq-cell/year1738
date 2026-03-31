import discord
from discord import app_commands
from discord.ext import commands
import datetime

BOT_FOOTER = "year1738"
BLACK = discord.Color.from_rgb(10, 10, 10)


class Utilities(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /ping ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="LATENCY",
            description=f"**{latency_ms} ms**",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)

    # ── /userinfo ─────────────────────────────────────────────────────────────

    @app_commands.command(name="userinfo", description="Display info about a user.")
    @app_commands.describe(member="Member to look up (defaults to yourself)")
    async def userinfo(
        self, interaction: discord.Interaction, member: discord.Member = None
    ) -> None:
        member = member or interaction.user
        roles = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]
        embed = discord.Embed(
            title="USER INFO",
            description=f"**{member}**",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Nickname", value=member.nick or "—", inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(member.created_at.timestamp())}:F>",
            inline=False,
        )
        embed.add_field(
            name="Joined Server",
            value=f"<t:{int(member.joined_at.timestamp())}:F>" if member.joined_at else "—",
            inline=False,
        )
        embed.add_field(
            name=f"Roles  ·  {len(roles)}",
            value=" ".join(roles) if roles else "—",
            inline=False,
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)

    # ── /serverinfo ───────────────────────────────────────────────────────────

    @app_commands.command(name="serverinfo", description="Display info about the server.")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        embed = discord.Embed(
            title="SERVER INFO",
            description=f"**{guild.name}**",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "—", inline=True)
        embed.add_field(name="Members", value=f"**{guild.member_count:,}**", inline=True)
        embed.add_field(name="Roles", value=f"**{len(guild.roles)}**", inline=True)
        embed.add_field(name="Text Channels", value=f"**{text_channels}**", inline=True)
        embed.add_field(name="Voice Channels", value=f"**{voice_channels}**", inline=True)
        embed.add_field(name="Boost Level", value=f"**{guild.premium_tier}**", inline=True)
        embed.add_field(
            name="Created",
            value=f"<t:{int(guild.created_at.timestamp())}:F>",
            inline=False,
        )
        embed.set_footer(text=f"{BOT_FOOTER}  ·  ID: {guild.id}")
        await interaction.response.send_message(embed=embed)

    # ── /avatar ───────────────────────────────────────────────────────────────

    @app_commands.command(name="avatar", description="Show a member's avatar.")
    @app_commands.describe(member="Member whose avatar to show (defaults to yourself)")
    async def avatar(
        self, interaction: discord.Interaction, member: discord.Member = None
    ) -> None:
        member = member or interaction.user
        embed = discord.Embed(
            title="AVATAR",
            description=f"**{member}**",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_image(url=member.display_avatar.url)
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)

    # ── /membercount ──────────────────────────────────────────────────────────

    @app_commands.command(name="membercount", description="Show the current member count.")
    async def membercount(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        embed = discord.Embed(
            title="MEMBER COUNT",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="Total", value=f"**{guild.member_count:,}**", inline=True)
        embed.add_field(name="Humans", value=f"**{humans:,}**", inline=True)
        embed.add_field(name="Bots", value=f"**{bots:,}**", inline=True)
        embed.set_footer(text=f"{BOT_FOOTER}  ·  {guild.name}")
        await interaction.response.send_message(embed=embed)

    # ── /help ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="help", description="Show all available commands.")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="COMMANDS",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(
            name="UTILITIES",
            value="`/ping`  `/userinfo`  `/serverinfo`\n`/avatar`  `/membercount`  `/help`",
            inline=False,
        )
        embed.add_field(
            name="FUN",
            value="`/joke`  `/8ball`  `/dice`  `/flip`  `/random`",
            inline=False,
        )
        embed.add_field(
            name="MODERATION",
            value="`/ban`  `/unban`  `/kick`  `/warn`\n`/warnings`  `/clearwarnings`  `/mute`  `/unmute`  `/clear`",
            inline=False,
        )
        embed.add_field(
            name="STATS",
            value="`/leaderboard`  `/rank`",
            inline=False,
        )
        embed.add_field(
            name="EMBEDS",
            value="`/announce`  `/say`  `/rules`\n`/roleinfo`  `/channelinfo`  `/botinfo`",
            inline=False,
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utilities(bot))
