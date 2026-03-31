import discord
from discord.ext import commands
import os
import json
import logging
from dotenv import load_dotenv
import database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("year1738")

with open("config.json", "r") as f:
    config = json.load(f)

COGS = [
    "cogs.moderation",
    "cogs.tracking",
    "cogs.leaderboard",
    "cogs.auto_mod",
    "cogs.react_roles",
    "cogs.polls",
    "cogs.utilities",
    "cogs.fun",
]


class Year1738Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=config.get("prefix", "!"), intents=intents)
        self.config = config

    async def setup_hook(self):
        database.setup_database()
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as exc:
                logger.error(f"Failed to load cog {cog}: {exc}")
        await self.tree.sync()
        logger.info("Slash commands synced.")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="over the server 👀"
            )
        )

    async def on_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.", ephemeral=True)
        elif isinstance(error, commands.CommandNotFound):
            pass
        else:
            logger.error(f"Unhandled command error: {error}")


bot = Year1738Bot()

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set.")
    bot.run(token)
