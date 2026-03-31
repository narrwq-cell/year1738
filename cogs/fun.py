import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime

BOT_FOOTER = "year1738"
BLACK = discord.Color.from_rgb(10, 10, 10)

JOKES = [
    ("Why don't scientists trust atoms?", "Because they make up everything!"),
    ("Why did the scarecrow win an award?", "Because he was outstanding in his field!"),
    ("Why don't eggs tell jokes?", "They'd crack each other up!"),
    ("What do you call a fake noodle?", "An impasta!"),
    ("Why did the math book look so sad?", "Because it had too many problems."),
    ("What do you call a sleeping dinosaur?", "A dino-snore!"),
    ("Why did the bicycle fall over?", "Because it was two-tired!"),
    ("What do you call cheese that isn't yours?", "Nacho cheese!"),
    ("Why can't you give Elsa a balloon?", "Because she'll let it go!"),
    ("What's a computer's favorite snack?", "Microchips!"),
    ("Why do cows wear bells?", "Because their horns don't work!"),
    ("What did the ocean say to the beach?", "Nothing, it just waved!"),
    ("Why did the golfer bring an extra pair of pants?", "In case he got a hole in one!"),
    ("How does a penguin build its house?", "Igloos it together!"),
    ("Why can't a nose be 12 inches long?", "Because then it would be a foot!"),
]

MAGIC_8_BALL = [
    "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes, definitely.",
    "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
    "Yes.", "Signs point to yes.",
    "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
    "Cannot predict now.", "Concentrate and ask again.",
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]

_8BALL_POSITIVE = frozenset([
    "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes, definitely.",
    "You may rely on it.", "As I see it, yes.", "Most likely.", "Outlook good.",
    "Yes.", "Signs point to yes.",
])
_8BALL_NEUTRAL = frozenset([
    "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
    "Cannot predict now.", "Concentrate and ask again.",
])


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="joke", description="Get a random joke.")
    async def joke(self, interaction: discord.Interaction) -> None:
        setup_text, punchline = random.choice(JOKES)
        embed = discord.Embed(
            title="RANDOM JOKE",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="Setup", value=setup_text, inline=False)
        embed.add_field(name="Punchline", value=f"||{punchline}||", inline=False)
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question.")
    @app_commands.describe(question="Your yes/no question")
    async def eightball(self, interaction: discord.Interaction, question: str) -> None:
        answer = random.choice(MAGIC_8_BALL)
        if answer in _8BALL_POSITIVE:
            outlook = "Positive"
        elif answer in _8BALL_NEUTRAL:
            outlook = "Neutral"
        else:
            outlook = "Negative"
        embed = discord.Embed(
            title="MAGIC 8-BALL",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=f"*{answer}*", inline=False)
        embed.add_field(name="Outlook", value=outlook, inline=True)
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dice", description="Roll a die.")
    @app_commands.describe(sides="Number of sides (default: 6)", count="Number of dice to roll (default: 1)")
    async def dice(self, interaction: discord.Interaction, sides: int = 6, count: int = 1) -> None:
        sides = max(2, min(sides, 1000))
        count = max(1, min(count, 10))
        rolls = [random.randint(1, sides) for _ in range(count)]
        dice_display = "  ".join(f"**{r}**" for r in rolls)
        embed = discord.Embed(
            title=f"ROLL  {count}d{sides}",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="Rolls", value=dice_display, inline=False)
        if count > 1:
            embed.add_field(name="Total", value=f"**{sum(rolls)}**", inline=True)
            embed.add_field(name="Average", value=f"**{sum(rolls) / count:.1f}**", inline=True)
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="flip", description="Flip a coin.")
    async def flip(self, interaction: discord.Interaction) -> None:
        result = random.choice(["Heads", "Tails"])
        embed = discord.Embed(
            title="COIN FLIP",
            description=f"**{result}**",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="random", description="Generate a random number.")
    @app_commands.describe(minimum="Minimum value (default: 1)", maximum="Maximum value (default: 100)")
    async def random_number(
        self, interaction: discord.Interaction, minimum: int = 1, maximum: int = 100
    ) -> None:
        if minimum >= maximum:
            await interaction.response.send_message(
                "Minimum must be less than maximum.", ephemeral=True
            )
            return
        result = random.randint(minimum, maximum)
        embed = discord.Embed(
            title="RANDOM NUMBER",
            description=f"**{result}**",
            color=BLACK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=f"{BOT_FOOTER}  ·  Range: {minimum} — {maximum}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
