import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import asyncio
import logging
import database

logger = logging.getLogger("year1738.moderation")

# Action-specific colors
_ACTION_COLORS = {
    "ban":    0xED4245,  # Red
    "unban":  0x57F287,  # Green
    "kick":   0xFFA500,  # Orange
    "warn":   0xFEE75C,  # Yellow
    "mute":   0x00B0F4,  # Blue
    "unmute": 0x57F287,  # Green
}
_DEFAULT_MOD_COLOR = 0x5865F2  # Blurple fallback

BOT_FOOTER = "year1738 Bot"


def _mod_embed(title: str, action: str = "", **fields) -> discord.Embed:
    color = discord.Color(_ACTION_COLORS.get(action, _DEFAULT_MOD_COLOR))
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    for name, value in fields.items():
        embed.add_field(name=name, value=str(value), inline=True)
    embed.set_footer(text=BOT_FOOTER)
    return embed


async def send_mod_log(bot: commands.Bot, guild: discord.Guild, embed: discord.Embed) -> None:
    channel_id = bot.config.get("mod_log_channel_id")
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass


async def get_or_create_muted_role(guild: discord.Guild, role_name: str) -> discord.Role:
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        role = await guild.create_role(name=role_name, reason="Auto-created Muted role")
        for channel in guild.channels:
            try:
                await channel.set_permissions(role, send_messages=False, speak=False, add_reactions=False)
            except (discord.Forbidden, discord.HTTPException):
                pass
    return role


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_mutes: dict[tuple, asyncio.Task] = {}

    # ── Ban ────────────────────────────────────────────────────────────────────

    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(member="Member to ban", reason="Reason for ban", delete_days="Days of messages to delete (0-7)")
    @app_commands.default_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
        delete_days: int = 0,
    ) -> None:
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ You cannot ban someone with an equal or higher role.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            await member.send(
                f"You have been **banned** from **{interaction.guild.name}**.\n**Reason:** {reason}"
            )
        except discord.Forbidden:
            pass
        await member.ban(reason=f"{reason} | Mod: {interaction.user}", delete_message_days=max(0, min(delete_days, 7)))
        database.log_mod_action(interaction.guild_id, member.id, interaction.user.id, "ban", reason)
        embed = _mod_embed(
            "🔨 Member Banned",
            action="ban",
            **{
                "User": f"{member} ({member.id})",
                "Moderator": str(interaction.user),
                "Reason": reason,
                "Timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            }
        )
        await interaction.followup.send(embed=embed)
        await send_mod_log(self.bot, interaction.guild, embed)

    # ── Unban ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="unban", description="Unban a user by their ID.")
    @app_commands.describe(user_id="The ID of the user to unban", reason="Reason for unban")
    @app_commands.default_permissions(ban_members=True)
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "No reason provided",
    ) -> None:
        await interaction.response.defer()
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.followup.send("❌ Invalid user ID.", ephemeral=True)
            return
        try:
            user = await self.bot.fetch_user(uid)
            await interaction.guild.unban(user, reason=reason)
        except discord.NotFound:
            await interaction.followup.send("❌ That user is not banned.", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to unban users.", ephemeral=True)
            return
        database.log_mod_action(interaction.guild_id, uid, interaction.user.id, "unban", reason)
        embed = _mod_embed(
            "✅ Member Unbanned",
            action="unban",
            **{
                "User": f"{user} ({uid})",
                "Moderator": str(interaction.user),
                "Reason": reason,
            }
        )
        await interaction.followup.send(embed=embed)
        await send_mod_log(self.bot, interaction.guild, embed)

    # ── Kick ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    @app_commands.default_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ You cannot kick someone with an equal or higher role.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            await member.send(
                f"You have been **kicked** from **{interaction.guild.name}**.\n**Reason:** {reason}"
            )
        except discord.Forbidden:
            pass
        await member.kick(reason=f"{reason} | Mod: {interaction.user}")
        database.log_mod_action(interaction.guild_id, member.id, interaction.user.id, "kick", reason)
        embed = _mod_embed(
            "👢 Member Kicked",
            action="kick",
            **{
                "User": f"{member} ({member.id})",
                "Moderator": str(interaction.user),
                "Reason": reason,
                "Timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            }
        )
        await interaction.followup.send(embed=embed)
        await send_mod_log(self.bot, interaction.guild, embed)

    # ── Warn ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="warn", description="Warn a member.")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @app_commands.default_permissions(kick_members=True)
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        await interaction.response.defer()
        database.add_warning(interaction.guild_id, member.id, interaction.user.id, reason)
        count = database.get_warning_count(interaction.guild_id, member.id)
        try:
            await member.send(
                f"⚠️ You have been **warned** in **{interaction.guild.name}**.\n"
                f"**Reason:** {reason}\n**Total warnings:** {count}"
            )
        except discord.Forbidden:
            pass
        embed = _mod_embed(
            "⚠️ Member Warned",
            action="warn",
            **{
                "User": f"{member} ({member.id})",
                "Moderator": str(interaction.user),
                "Reason": reason,
                "Total Warnings": count,
            }
        )
        await interaction.followup.send(embed=embed)
        await send_mod_log(self.bot, interaction.guild, embed)

    # ── Warnings ───────────────────────────────────────────────────────────────

    @app_commands.command(name="warnings", description="View warnings for a member.")
    @app_commands.describe(member="Member to check warnings for")
    @app_commands.default_permissions(kick_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        rows = database.get_warnings(interaction.guild_id, member.id)
        embed = discord.Embed(
            title=f"⚠️ Warnings — {member}",
            color=discord.Color(0xFEE75C),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if not rows:
            embed.description = "✅ No warnings on record."
        else:
            for i, row in enumerate(rows, 1):
                embed.add_field(
                    name=f"Warning #{i}",
                    value=f"**Reason:** {row['reason']}\n**Date:** {row['timestamp'][:10]}",
                    inline=False,
                )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed)

    # ── Clear Warnings ─────────────────────────────────────────────────────────

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member.")
    @app_commands.describe(member="Member to clear warnings for")
    @app_commands.default_permissions(administrator=True)
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        database.clear_warnings(interaction.guild_id, member.id)
        await interaction.response.send_message(f"✅ Cleared all warnings for {member.mention}.")

    # ── Mute ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="mute", description="Mute a member.")
    @app_commands.describe(member="Member to mute", duration="Duration in minutes (0 = permanent)", reason="Reason")
    @app_commands.default_permissions(manage_roles=True)
    async def mute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: int = 10,
        reason: str = "No reason provided",
    ) -> None:
        await interaction.response.defer()
        role_name = self.bot.config.get("muted_role_name", "Muted")
        muted_role = await get_or_create_muted_role(interaction.guild, role_name)
        if muted_role in member.roles:
            await interaction.followup.send(f"❌ {member.mention} is already muted.", ephemeral=True)
            return
        await member.add_roles(muted_role, reason=reason)
        database.log_mod_action(
            interaction.guild_id, member.id, interaction.user.id, "mute", reason,
            duration_minutes=duration if duration > 0 else None
        )
        duration_text = f"{duration} minute(s)" if duration > 0 else "permanent"
        embed = _mod_embed(
            "🔇 Member Muted",
            action="mute",
            **{
                "User": f"{member} ({member.id})",
                "Moderator": str(interaction.user),
                "Duration": duration_text,
                "Reason": reason,
            }
        )
        await interaction.followup.send(embed=embed)
        await send_mod_log(self.bot, interaction.guild, embed)
        if duration > 0:
            key = (member.id, interaction.guild_id)
            if key in self.active_mutes:
                self.active_mutes[key].cancel()
            self.active_mutes[key] = asyncio.create_task(
                self._auto_unmute(member, muted_role, duration * 60)
            )

    async def _auto_unmute(self, member: discord.Member, role: discord.Role, seconds: int) -> None:
        await asyncio.sleep(seconds)
        try:
            await member.remove_roles(role, reason="Mute duration expired")
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ── Unmute ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="unmute", description="Unmute a member.")
    @app_commands.describe(member="Member to unmute", reason="Reason")
    @app_commands.default_permissions(manage_roles=True)
    async def unmute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ) -> None:
        role_name = self.bot.config.get("muted_role_name", "Muted")
        muted_role = discord.utils.get(interaction.guild.roles, name=role_name)
        if muted_role is None or muted_role not in member.roles:
            await interaction.response.send_message(f"❌ {member.mention} is not muted.", ephemeral=True)
            return
        await member.remove_roles(muted_role, reason=reason)
        key = (member.id, interaction.guild_id)
        if key in self.active_mutes:
            self.active_mutes[key].cancel()
            del self.active_mutes[key]
        database.log_mod_action(interaction.guild_id, member.id, interaction.user.id, "unmute", reason)
        embed = _mod_embed(
            "🔊 Member Unmuted",
            action="unmute",
            **{
                "User": f"{member} ({member.id})",
                "Moderator": str(interaction.user),
                "Reason": reason,
            }
        )
        await interaction.response.send_message(embed=embed)
        await send_mod_log(self.bot, interaction.guild, embed)

    # ── Clear ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="clear", description="Delete messages from a channel.")
    @app_commands.describe(amount="Number of messages to delete (1-100)", member="Only delete messages from this member")
    @app_commands.default_permissions(manage_messages=True)
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: int,
        member: discord.Member = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        amount = max(1, min(amount, 100))
        def check(msg):
            return member is None or msg.author == member
        deleted = await interaction.channel.purge(limit=amount, check=check)
        await interaction.followup.send(f"✅ Deleted {len(deleted)} message(s).", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
