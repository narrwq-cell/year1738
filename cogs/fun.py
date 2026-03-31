import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime


JOKES = [
    ("Why don't scientists trust atoms?", "Because they make up everything! 😄"),
    ("Why did the scarecrow win an award?", "Because he was outstanding in his field! 🌾"),
    ("Why don't eggs tell jokes?", "They'd crack each other up! 🥚"),
    ("What do you call a fake noodle?", "An impasta! 🍝"),
    ("Why did the math book look so sad?", "Because it had too many problems. 📚"),
    ("What do you call a sleeping dinosaur?", "A dino-snore! 🦕"),
    ("Why did the bicycle fall over?", "Because it was two-tired! 🚲"),
    ("What do you call cheese that isn't yours?", "Nacho cheese! 🧀"),
    ("Why can't you give Elsa a balloon?", "Because she'll let it go! 🎈"),
    ("What's a computer's favorite snack?", "Microchips! 💻"),
    ("Why do cows wear bells?", "Because their horns don't work! 🐄"),
    ("What did the ocean say to the beach?", "Nothing, it just waved! 🌊"),
    ("Why did the golfer bring an extra pair of pants?", "In case he got a hole in one! ⛳"),
    ("How does a penguin build its house?", "Igloos it together! 🐧"),
    ("Why can't a nose be 12 inches long?", "Because then it would be a foot! 👃"),
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


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="joke", description="Get a random joke.")
    async def joke(self, interaction: discord.Interaction) -> None:
        setup_text, punchline = random.choice(JOKES)
        embed = discord.Embed(
            title="😂 Random Joke",
            color=discord.Color.yellow(),
        )
        embed.add_field(name="Setup", value=setup_text, inline=False)
        embed.add_field(name="Punchline", value=f"||{punchline}||", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question.")
    @app_commands.describe(question="Your yes/no question")
    async def eightball(self, interaction: discord.Interaction, question: str) -> None:
        answer = random.choice(MAGIC_8_BALL)
        positive = ["It is certain.", "It is decidedly so.", "Without a doubt.",
                    "Yes, definitely.", "You may rely on it.", "As I see it, yes.",
                    "Most likely.", "Outlook good.", "Yes.", "Signs point to yes."]
        neutral = ["Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
                   "Cannot predict now.", "Concentrate and ask again."]
        if answer in positive:
            color = discord.Color.green()
        elif answer in neutral:
            color = discord.Color.orange()
        else:
            color = discord.Color.red()
        embed = discord.Embed(title="🎱 Magic 8-Ball", color=color)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=answer, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dice", description="Roll a die.")
    @app_commands.describe(sides="Number of sides (default: 6)", count="Number of dice to roll (default: 1)")
    async def dice(self, interaction: discord.Interaction, sides: int = 6, count: int = 1) -> None:
        sides = max(2, min(sides, 1000))
        count = max(1, min(count, 10))
        rolls = [random.randint(1, sides) for _ in range(count)]
        embed = discord.Embed(
            title=f"🎲 Rolling {count}d{sides}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Rolls", value=" | ".join(str(r) for r in rolls), inline=False)
        if count > 1:
            embed.add_field(name="Total", value=str(sum(rolls)), inline=True)
            embed.add_field(name="Average", value=f"{sum(rolls) / count:.1f}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="flip", description="Flip a coin.")
    async def flip(self, interaction: discord.Interaction) -> None:
        result = random.choice(["Heads", "Tails"])
        emoji = "🪙" if result == "Heads" else "🔄"
        embed = discord.Embed(
            title=f"{emoji} Coin Flip",
            description=f"**{result}!**",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="random", description="Generate a random number.")
    @app_commands.describe(minimum="Minimum value (default: 1)", maximum="Maximum value (default: 100)")
    async def random_number(
        self, interaction: discord.Interaction, minimum: int = 1, maximum: int = 100
    ) -> None:
        if minimum >= maximum:
            await interaction.response.send_message(
                "❌ Minimum must be less than maximum.", ephemeral=True
            )
            return
        result = random.randint(minimum, maximum)
        embed = discord.Embed(
            title="🎰 Random Number",
            description=f"**{result}**",
            color=discord.Color.purple(),
        )
        embed.set_footer(text=f"Range: {minimum} — {maximum}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
