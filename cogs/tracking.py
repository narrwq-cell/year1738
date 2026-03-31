import discord
from discord.ext import commands
import logging
import database

logger = logging.getLogger("year1738.tracking")


class Tracking(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        database.increment_message_count(message.author.id, message.guild.id)
        database.add_points(message.author.id, message.guild.id, 1)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return

        joined = before.channel is None and after.channel is not None
        left = before.channel is not None and after.channel is None

        if joined:
            database.start_vc_session(member.id, member.guild.id)
            logger.debug(f"{member} joined VC in guild {member.guild.id}")
        elif left:
            seconds = database.end_vc_session(member.id, member.guild.id)
            if seconds is not None:
                logger.debug(f"{member} left VC after {seconds}s in guild {member.guild.id}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        welcome_channel_id = self.bot.config.get("welcome_channel_id")
        if not welcome_channel_id:
            return
        channel = member.guild.get_channel(int(welcome_channel_id))
        if channel is None:
            return
        welcome_msg = self.bot.config.get(
            "welcome_message", "Welcome to the server, {user}!"
        ).replace("{user}", member.mention)
        embed = discord.Embed(
            title="👋 Welcome!",
            description=welcome_msg,
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>")
        embed.add_field(name="Member #", value=str(member.guild.member_count))
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tracking(bot))
