import re
import discord
from discord import app_commands
from discord.ext import commands
import logging
import database

logger = logging.getLogger("year1738.react_roles")

# Separator used inside each option: emoji‣name‣@role
_OPTION_SEP = "‣"
_MENTION_RE = re.compile(r"<@&(\d+)>")
_AT_RE = re.compile(r"^@(.+)$")


def _parse_selfroles_options(
    options_str: str, guild: discord.Guild
) -> list[tuple[str, str, discord.Role]]:
    """Parse the pipe-separated options string into (emoji, name, role) tuples.

    Accepted formats per option (separated by ``|``):
      ``<emoji>‣<display name>‣<@role_mention or @role_name>``
    """
    results: list[tuple[str, str, discord.Role]] = []
    for raw in options_str.split("|"):
        raw = raw.strip()
        if not raw:
            continue
        parts = [p.strip() for p in raw.split(_OPTION_SEP)]
        if len(parts) != 3:
            raise ValueError(
                f"Option `{raw}` is not in the expected format `emoji{_OPTION_SEP}name{_OPTION_SEP}@role`."
            )
        emoji, name, role_ref = parts

        # Try to resolve the role - handle <@&ID>, @name, or bare name
        mention_match = _MENTION_RE.fullmatch(role_ref)
        at_match = _AT_RE.match(role_ref)
        if mention_match:
            role = guild.get_role(int(mention_match.group(1)))
        elif at_match:
            role_name = at_match.group(1)
            role = discord.utils.get(guild.roles, name=role_name)
        else:
            role = discord.utils.get(guild.roles, name=role_ref)

        if role is None:
            raise ValueError(f"Role `{role_ref}` could not be found in this server.")
        results.append((emoji, name, role))
    return results


class ReactRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="selfroles",
        description="Create a self-roles message where members can pick multiple roles.",
    )
    @app_commands.describe(
        title="Title shown at the top of the embed (e.g. SELF ROLES)",
        description="Short description shown below the title",
        options=(
            "Pipe-separated role options in format: "
            "emoji‣Name‣@Role | emoji‣Name‣@Role"
        ),
    )
    @app_commands.default_permissions(manage_roles=True)
    async def selfroles(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        options: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            parsed = _parse_selfroles_options(options, interaction.guild)
        except ValueError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return

        if not parsed:
            await interaction.followup.send(
                "❌ No valid options found. Make sure you use the format "
                "`emoji‣Name‣@Role` separated by `|`.",
                ephemeral=True,
            )
            return

        # Build the embed
        embed = discord.Embed(
            title=title.upper(),
            description=description,
            color=discord.Color(0x0A0A0A),
        )
        embed.set_footer(text="Tap an emoji below to add or remove a role")

        role_lines = "\n".join(
            f"{emoji}  **{name}** — {role.mention}"
            for emoji, name, role in parsed
        )
        embed.add_field(name="Available Roles", value=role_lines, inline=False)

        # Post the embed
        msg = await interaction.channel.send(embed=embed)

        # Store every emoji→role mapping and add reactions
        failed_emojis: list[str] = []
        for emoji, _name, role in parsed:
            database.add_react_role(
                interaction.guild_id, interaction.channel_id, msg.id, emoji, role.id
            )
            try:
                await msg.add_reaction(emoji)
            except discord.HTTPException:
                failed_emojis.append(emoji)
                logger.warning(
                    "Failed to add reaction %s to message %d", emoji, msg.id
                )

        # Confirm to the admin
        summary_lines = [
            f"{emoji}  **{name}** → {role.mention}" for emoji, name, role in parsed
        ]
        summary = "\n".join(summary_lines)
        note = (
            f"\n\n⚠️ Could not add reactions: {' '.join(failed_emojis)}"
            if failed_emojis
            else ""
        )
        await interaction.followup.send(
            f"✅ Self-roles message created!\n\n{summary}{note}",
            ephemeral=True,
        )

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
