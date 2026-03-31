import discord
from discord import app_commands
from discord.ext import commands
import datetime
import database


class Polls(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a poll.")
    @app_commands.describe(question="The question to ask")
    async def poll(self, interaction: discord.Interaction, question: str) -> None:
        embed = discord.Embed(
            title="📊 Poll",
            description=question,
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=f"Poll by {interaction.user} • React to vote!")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        database.log_poll(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            message_id=msg.id,
            question=question,
            creator_id=interaction.user.id,
        )

    @app_commands.command(name="custompoll", description="Create a poll with custom options.")
    @app_commands.describe(
        question="The question to ask",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)",
    )
    async def custompoll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None,
    ) -> None:
        options = [o for o in [option1, option2, option3, option4] if o]
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        embed = discord.Embed(
            title="📊 Poll",
            description=f"**{question}**\n\n"
            + "\n".join(f"{number_emojis[i]} {opt}" for i, opt in enumerate(options)),
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=f"Poll by {interaction.user} • React to vote!")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        for i in range(len(options)):
            await msg.add_reaction(number_emojis[i])


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Polls(bot))
