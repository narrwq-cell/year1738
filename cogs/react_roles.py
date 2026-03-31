import discord
from discord import app_commands
from discord.ext import commands
import logging
import database

logger = logging.getLogger("year1738.react_roles")


class ReactRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="reactrole", description="Add a react role to a message.")
    @app_commands.describe(
        message_id="ID of the message",
        emoji="Emoji users should react with",
        role="Role to assign",
    )
    @app_commands.default_permissions(manage_roles=True)
    async def reactrole(
        self,
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role,
    ) -> None:
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)
            return
        try:
            msg = await interaction.channel.fetch_message(mid)
        except discord.NotFound:
            await interaction.response.send_message("❌ Message not found in this channel.", ephemeral=True)
            return

        database.add_react_role(interaction.guild_id, interaction.channel_id, mid, emoji, role.id)
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            pass
        await interaction.response.send_message(
            f"✅ React role set up! Users who react with {emoji} will receive {role.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="removereactrole", description="Remove a react role from a message.")
    @app_commands.describe(message_id="ID of the message", emoji="Emoji to remove")
    @app_commands.default_permissions(manage_roles=True)
    async def removereactrole(
        self, interaction: discord.Interaction, message_id: str, emoji: str
    ) -> None:
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)
            return
        database.remove_react_role(mid, emoji)
        await interaction.response.send_message(f"✅ React role removed for emoji {emoji}.", ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.bot.user.id:
            return
        emoji_str = str(payload.emoji)
        row = database.get_react_role(payload.message_id, emoji_str)
        if row is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        member = guild.get_member(payload.user_id)
        if member is None:
            return
        role = guild.get_role(row["role_id"])
        if role is None:
            return
        try:
            await member.add_roles(role, reason="React role")
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.bot.user.id:
            return
        emoji_str = str(payload.emoji)
        row = database.get_react_role(payload.message_id, emoji_str)
        if row is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        member = guild.get_member(payload.user_id)
        if member is None:
            return
        role = guild.get_role(row["role_id"])
        if role is None:
            return
        try:
            await member.remove_roles(role, reason="React role removed")
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReactRoles(bot))
