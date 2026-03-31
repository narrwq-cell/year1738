import discord
from discord import app_commands
from discord.ext import commands
import datetime
import database

EMBED_COLOR = discord.Color.from_rgb(0, 0, 0)  # Black
BOT_FOOTER = "year1738 Bot"

# ── helpers ────────────────────────────────────────────────────────────────────

def _progress_bar(value: int, maximum: int, length: int = 10) -> str:
    """Return a Unicode block progress bar scaled to the top value."""
    if maximum == 0:
        filled = 0
    else:
        filled = round(length * value / maximum)
    filled = max(0, min(filled, length))
    return "█" * filled + "░" * (length - filled)


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show the server leaderboard.")
    @app_commands.describe(category="Which leaderboard to show: hours | messages | points")
    @app_commands.choices(category=[
        app_commands.Choice(name="Voice Hours", value="hours"),
        app_commands.Choice(name="Messages", value="messages"),
        app_commands.Choice(name="Points", value="points"),
    ])
    async def leaderboard(self, interaction: discord.Interaction, category: str) -> None:
        await interaction.response.defer()
        limit = self.bot.config.get("leaderboard_size", 10)
        guild = interaction.guild

        if category == "hours":
            rows = database.get_leaderboard_hours(guild.id, limit)
            title = "🎙️  Voice Channel Leaderboard"
            subtitle = "Top members by voice channel time"
            def get_value(row):
                return row["vc_seconds"]
            def fmt_value(v):
                return f"{v / 3600:.1f}h"
            unit = "hours"
        elif category == "messages":
            rows = database.get_leaderboard_messages(guild.id, limit)
            title = "💬  Message Leaderboard"
            subtitle = "Top members by messages sent"
            def get_value(row):
                return row["message_count"]
            def fmt_value(v):
                return f"{v:,} msgs"
            unit = "messages"
        else:
            rows = database.get_leaderboard_points(guild.id, limit)
            title = "⭐  Points Leaderboard"
            subtitle = "Top members by reputation points"
            def get_value(row):
                return row["points"]
            def fmt_value(v):
                return f"{v:,} pts"
            unit = "points"

        medals = ["🥇", "🥈", "🥉"]
        top_value = get_value(rows[0]) if rows else 1

        embed = discord.Embed(
            title=title,
            color=EMBED_COLOR,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.description = f"*{subtitle}*\n\u200b"  # italic subtitle + blank spacer
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_author(name=guild.name,
                         icon_url=guild.icon.url if guild.icon else None)

        description_lines = []
        for i, row in enumerate(rows):
            medal = medals[i] if i < 3 else f"`#{i + 1}`"
            member = guild.get_member(row["user_id"])
            name = member.display_name if member else f"Unknown ({row['user_id']})"
            value = get_value(row)
            bar = _progress_bar(value, top_value)
            description_lines.append(
                f"{medal} **{name}**\n"
                f"┗ `{bar}` {fmt_value(value)}"
            )

        embed.description = (
            f"*{subtitle}*\n\u200b\n"
            + "\n\n".join(description_lines)
            if description_lines
            else f"*{subtitle}*\n\nNo data yet! Start chatting or joining voice channels."
        )
        embed.set_footer(text=f"{BOT_FOOTER}  •  Top {limit} members  •  {guild.name}")
        await interaction.followup.send(embed=embed)

    # ── /rank ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="rank", description="Show your (or another member's) rank card.")
    @app_commands.describe(member="Member to check (defaults to yourself)")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        await interaction.response.defer()
        member = member or interaction.user
        guild = interaction.guild

        stats = database.get_user_stats(member.id, guild.id)
        if not stats:
            await interaction.followup.send(
                f"❌ No activity data found for {member.mention}.", ephemeral=True
            )
            return

        # Efficient single-query rank lookups and top values
        msg_rank = database.get_user_rank_messages(guild.id, member.id)
        hrs_rank = database.get_user_rank_hours(guild.id, member.id)
        pts_rank = database.get_user_rank_points(guild.id, member.id)
        tops = database.get_leaderboard_top_values(guild.id)
        total = guild.member_count or 1

        embed = discord.Embed(
            title=f"📊  Rank Card — {member.display_name}",
            color=discord.Color.from_rgb(0, 0, 0),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_author(name=guild.name,
                         icon_url=guild.icon.url if guild.icon else None)

        # Messages
        msg_bar = _progress_bar(stats["message_count"], tops["top_messages"] or 1)
        embed.add_field(
            name="💬  Messages",
            value=(
                f"`{msg_bar}` **{stats['message_count']:,}**\n"
                f"Rank **#{msg_rank}** of {total:,}"
            ),
            inline=False,
        )

        # Voice hours
        hrs_bar = _progress_bar(stats["vc_seconds"], tops["top_seconds"] or 1)
        embed.add_field(
            name="🎙️  Voice Time",
            value=(
                f"`{hrs_bar}` **{stats['vc_seconds'] / 3600:.1f}h**\n"
                f"Rank **#{hrs_rank}** of {total:,}"
            ),
            inline=False,
        )

        # Points
        pts_bar = _progress_bar(stats["points"], tops["top_points"] or 1)
        embed.add_field(
            name="⭐  Points",
            value=(
                f"`{pts_bar}` **{stats['points']:,}**\n"
                f"Rank **#{pts_rank}** of {total:,}"
            ),
            inline=False,
        )

        embed.set_footer(text=f"{BOT_FOOTER}  •  Joined: {member.joined_at.strftime('%b %d, %Y') if member.joined_at else 'unknown'}")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))

