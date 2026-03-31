import discord
from discord import app_commands
from discord.ext import commands
import datetime
import database

EMBED_COLOR = discord.Color.gold()


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
            title = "🎙️ Top Voice Channel Users"
            def fmt(row):
                hours = row["vc_seconds"] / 3600
                return f"**{hours:.1f}h**"
        elif category == "messages":
            rows = database.get_leaderboard_messages(guild.id, limit)
            title = "💬 Top Chatters"
            def fmt(row):
                return f"**{row['message_count']:,} messages**"
        else:
            rows = database.get_leaderboard_points(guild.id, limit)
            title = "⭐ Top Points"
            def fmt(row):
                return f"**{row['points']:,} points**"

        embed = discord.Embed(title=title, color=EMBED_COLOR, timestamp=datetime.datetime.now(datetime.timezone.utc))
        medals = ["🥇", "🥈", "🥉"]
        description_lines = []
        for i, row in enumerate(rows):
            medal = medals[i] if i < 3 else f"**#{i + 1}**"
            member = guild.get_member(row["user_id"])
            name = member.display_name if member else f"Unknown ({row['user_id']})"
            description_lines.append(f"{medal} {name} — {fmt(row)}")

        embed.description = "\n".join(description_lines) if description_lines else "No data yet!"
        embed.set_footer(text=f"Showing top {limit} members")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Leaderboard(bot))
