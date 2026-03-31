import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal
import re
import json
import datetime
import asyncio
import logging
import database
from cogs.moderation import send_mod_log, get_or_create_muted_role

logger = logging.getLogger("year1738.auto_mod")

_MOD_COLOR = discord.Color.from_rgb(10, 10, 10)
BOT_FOOTER = "year1738 Auto-Mod"
MAX_DISPLAYED_VIOLATIONS = 15

INVITE_PATTERN = re.compile(
    r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/[a-zA-Z0-9\-]+",
    re.IGNORECASE,
)
LINK_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
# Matches standard Unicode emoji and custom Discord emoji
EMOJI_PATTERN = re.compile(
    r"[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FA9F]"
    r"|<a?:[a-zA-Z0-9_]+:[0-9]+>",
    re.UNICODE,
)
# Zalgo / combining character spam: 3+ combining diacritics in a row
ZALGO_PATTERN = re.compile(r"[\u0300-\u036f\u0489\u1dc0-\u1dff\ufe20-\ufe2f]{3,}", re.UNICODE)

# In-memory recent-join tracking for raid detection: guild_id -> list of timestamps
_recent_joins: dict[int, list[float]] = {}


class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._mute_tasks: dict[tuple, asyncio.Task] = {}
        self._cleanup_task: asyncio.Task | None = None

    async def cog_load(self) -> None:
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.bot.tree.add_command(self.automod_group)

    def cog_unload(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
        self.bot.tree.remove_command(self.automod_group.name)

    # ── Config helpers ──────────────────────────────────────────────────────────

    @property
    def _base_cfg(self) -> dict:
        return self.bot.config.get("auto_mod", {})

    def _is_enabled(self) -> bool:
        return self._base_cfg.get("enabled", True)

    def _guild_cfg(self, guild_id: int) -> dict:
        """Merge base config with per-guild overrides stored in the database."""
        cfg = dict(self._base_cfg)
        cfg.update(database.get_automod_settings(guild_id))
        return cfg

    def _is_whitelisted(self, message: discord.Message, cfg: dict) -> bool:
        if message.channel.id in cfg.get("whitelisted_channels", []):
            return True
        member_role_ids = {r.id for r in message.author.roles}
        if member_role_ids & set(cfg.get("whitelisted_roles", [])):
            return True
        return False

    # ── Raid protection ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if not self._is_enabled():
            return
        guild_id = member.guild.id
        cfg = self._guild_cfg(guild_id)

        now = datetime.datetime.now(datetime.timezone.utc).timestamp()

        # Rapid-join raid detection
        if cfg.get("raid_protection", True):
            raid_window = cfg.get("raid_join_window", 10)
            raid_threshold = cfg.get("raid_join_threshold", 5)
            joins = _recent_joins.setdefault(guild_id, [])
            joins[:] = [t for t in joins if now - t < raid_window]
            joins.append(now)
            if len(joins) >= raid_threshold:
                embed = discord.Embed(
                    title="⚠️ POTENTIAL RAID DETECTED",
                    description=(
                        f"`{len(joins)}` accounts joined within `{raid_window}s`.\n"
                        f"Latest: **{member}** (`{member.id}`)"
                    ),
                    color=_MOD_COLOR,
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                )
                embed.set_footer(text=BOT_FOOTER)
                await send_mod_log(self.bot, member.guild, embed)

        # New account detection (< 24 h old)
        if cfg.get("new_account_detection", True):
            account_age = datetime.datetime.now(datetime.timezone.utc) - member.created_at
            if account_age.total_seconds() < 86400:
                embed = discord.Embed(
                    title="🆕 NEW ACCOUNT JOINED",
                    color=_MOD_COLOR,
                    timestamp=datetime.datetime.now(datetime.timezone.utc),
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="User", value=f"**{member}**  ·  `{member.id}`", inline=False)
                embed.add_field(
                    name="Account Age",
                    value=f"<t:{int(member.created_at.timestamp())}:R>",
                    inline=True,
                )
                embed.set_footer(text=BOT_FOOTER)
                await send_mod_log(self.bot, member.guild, embed)

    # ── Message listener ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self._is_enabled():
            return
        if message.author.bot or message.guild is None:
            return
        if message.author.guild_permissions.manage_messages:
            return

        cfg = self._guild_cfg(message.guild.id)
        if self._is_whitelisted(message, cfg):
            return

        violations: list[tuple[str, str]] = []

        # Profanity / forbidden words
        if cfg.get("profanity_filter", True):
            content_lower = message.content.lower()
            word_list = list(set(
                self.bot.config.get("profanity_words", [])
                + cfg.get("forbidden_words", [])
            ))
            for word in word_list:
                if word.lower() in content_lower:
                    violations.append(("profanity", "Forbidden word detected"))
                    break

        # Invite links
        if cfg.get("invite_link_detection", True):
            if INVITE_PATTERN.search(message.content):
                violations.append(("invite", "Unauthorized Discord invite link"))

        # All-caps spam
        if cfg.get("caps_detection", True):
            caps_threshold = cfg.get("caps_threshold", 0.7)
            caps_min = cfg.get("caps_min_length", 10)
            if len(message.content) >= caps_min:
                letters = [c for c in message.content if c.isalpha()]
                if letters and sum(1 for c in letters if c.isupper()) / len(letters) >= caps_threshold:
                    violations.append(("caps", "Excessive caps"))

        # Mass mentions
        if cfg.get("mass_mention_detection", True):
            mention_threshold = cfg.get("mass_mention_threshold", 5)
            if len(message.mentions) >= mention_threshold:
                violations.append(("mass_mention", f"Mass mention ({len(message.mentions)} users)"))

        # @everyone / @here (by non-permitted users)
        if cfg.get("everyone_ping_detection", True):
            if message.mention_everyone and not message.author.guild_permissions.mention_everyone:
                violations.append(("everyone_ping", "Unauthorized @everyone/@here ping"))

        # Link spam
        if cfg.get("link_spam_detection", True):
            link_threshold = cfg.get("link_spam_threshold", 3)
            links = LINK_PATTERN.findall(message.content)
            if len(links) >= link_threshold:
                violations.append(("link_spam", f"Link spam ({len(links)} links)"))

        # Emoji spam
        if cfg.get("emoji_spam_detection", True):
            emoji_threshold = cfg.get("emoji_spam_threshold", 10)
            emojis = EMOJI_PATTERN.findall(message.content)
            if len(emojis) >= emoji_threshold:
                violations.append(("emoji_spam", f"Emoji spam ({len(emojis)} emojis)"))

        # Character spam (e.g. "aaaaaaaa")
        if cfg.get("char_spam_detection", True):
            char_threshold = cfg.get("char_spam_threshold", 8)
            if re.search(rf"(.)\1{{{char_threshold - 1},}}", message.content):
                violations.append(("char_spam", "Character spam (repeated characters)"))

        # Zalgo / combining-character text
        if cfg.get("zalgo_detection", True):
            if ZALGO_PATTERN.search(message.content):
                violations.append(("zalgo", "Zalgo/Unicode text spam"))

        # Rapid message / duplicate spam
        if cfg.get("spam_detection", True):
            spam_result = await self._check_spam(message, cfg)
            if spam_result:
                violations.append(("spam", spam_result))

        if not violations:
            return

        # Delete offending message
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        # Most-severe violation drives the log label
        severity_order = [
            "spam", "everyone_ping", "mass_mention", "invite",
            "link_spam", "emoji_spam", "char_spam", "zalgo", "caps", "profanity",
        ]
        severity = next(
            (v for v in severity_order if any(viol[0] == v for viol in violations)),
            violations[0][0],
        )
        reason = "; ".join(v[1] for v in violations)
        await self._take_action(message.author, message.guild, message.channel, reason, severity, cfg)

    # ── Spam detection helper ───────────────────────────────────────────────────

    async def _check_spam(self, message: discord.Message, cfg: dict) -> str:
        user_id = message.author.id
        guild_id = message.guild.id
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        window = cfg.get("spam_time_window", 5)
        threshold = cfg.get("spam_message_threshold", 5)
        repeat_threshold = cfg.get("repeat_message_threshold", 4)

        row = database.get_spam_data(user_id, guild_id)
        try:
            times = json.loads(row["message_times"])
        except (json.JSONDecodeError, TypeError):
            times = []

        times = [t for t in times if now - t < window]
        times.append(now)

        last_msg = row["last_message"] or ""
        repeat_count = row["repeat_count"] or 0
        if message.content and message.content.lower() == last_msg.lower():
            repeat_count += 1
        else:
            repeat_count = 1

        database.update_spam_data(user_id, guild_id, json.dumps(times), message.content, repeat_count)

        if len(times) >= threshold:
            return f"Message spam ({len(times)} messages in {window}s)"
        if repeat_count >= repeat_threshold:
            return f"Repeated message spam ({repeat_count} times)"
        return ""

    # ── Action escalation ───────────────────────────────────────────────────────

    async def _take_action(
        self,
        member: discord.Member,
        guild: discord.Guild,
        channel: discord.abc.Messageable,
        reason: str,
        severity: str,
        cfg: dict,
    ) -> None:
        # Record violation (cleans old ones first)
        database.clean_automod_violations(guild.id, member.id)
        violation_id = database.add_automod_violation(guild.id, member.id, severity, reason)
        violation_count = database.get_automod_violation_count(guild.id, member.id)

        action_taken = "warned"

        if violation_count >= 5:
            # 5th+ violation → ban
            try:
                await self._dm_user(member, reason, "banned", guild.name, cfg)
                await member.ban(reason=f"[Auto-Mod] {reason} (repeated violations)")
                action_taken = "banned"
                database.log_mod_action(guild.id, member.id, self.bot.user.id, "ban",
                                        f"[Auto-Mod] {reason}")
            except (discord.Forbidden, discord.HTTPException):
                pass
        elif violation_count == 4:
            # 4th violation → kick
            try:
                await self._dm_user(member, reason, "kicked", guild.name, cfg)
                await member.kick(reason=f"[Auto-Mod] {reason} (too many violations)")
                action_taken = "kicked"
                database.log_mod_action(guild.id, member.id, self.bot.user.id, "kick",
                                        f"[Auto-Mod] {reason}")
            except (discord.Forbidden, discord.HTTPException):
                pass
        elif violation_count == 3:
            # 3rd violation → 30-minute mute
            action_taken = await self._apply_mute(member, guild, reason, 30)
        elif violation_count == 2:
            # 2nd violation → 5-minute mute
            action_taken = await self._apply_mute(member, guild, reason, 5)
        else:
            # 1st violation → warn
            database.add_warning(guild.id, member.id, self.bot.user.id, f"[Auto-Mod] {reason}")
            action_taken = "warned"
            await self._dm_user(member, reason, "warned", guild.name, cfg)

        # Update the violation record with the action taken
        database.update_automod_violation_action(violation_id, action_taken)

        # Build the mod-log embed (black/white aesthetic)
        embed = discord.Embed(
            title="🛡️ AUTO-MOD ACTION",
            color=_MOD_COLOR,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="User", value=f"**{member}**  ·  `{member.id}`", inline=False)
        embed.add_field(name="Action", value=action_taken.title(), inline=True)
        embed.add_field(name="Violations (24h)", value=str(violation_count), inline=True)
        embed.add_field(name="Severity", value=severity.replace("_", " ").title(), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=BOT_FOOTER)

        if cfg.get("notify_in_channel", True):
            try:
                await channel.send(embed=embed, delete_after=10)
            except discord.Forbidden:
                pass
        await send_mod_log(self.bot, guild, embed)

    async def _apply_mute(
        self,
        member: discord.Member,
        guild: discord.Guild,
        reason: str,
        duration_minutes: int,
    ) -> str:
        try:
            role_name = self.bot.config.get("muted_role_name", "Muted")
            muted_role = await get_or_create_muted_role(guild, role_name)
            await member.add_roles(muted_role, reason=f"[Auto-Mod] {reason}")
            database.log_mod_action(guild.id, member.id, self.bot.user.id, "mute",
                                    f"[Auto-Mod] {reason}", duration_minutes=duration_minutes)
            key = (member.id, guild.id)
            if key in self._mute_tasks:
                self._mute_tasks[key].cancel()
            self._mute_tasks[key] = asyncio.create_task(
                self._unmute_after(member, muted_role, duration_minutes * 60)
            )
            return f"muted for {duration_minutes}m"
        except (discord.Forbidden, discord.HTTPException):
            return "mute failed (missing permissions)"

    async def _dm_user(
        self,
        member: discord.Member,
        reason: str,
        action: str,
        guild_name: str,
        cfg: dict,
    ) -> None:
        if not cfg.get("dm_on_action", True):
            return
        try:
            embed = discord.Embed(
                title="⚠️ AUTO-MOD NOTICE",
                description=f"Your message in **{guild_name}** was removed.",
                color=_MOD_COLOR,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Action Taken", value=action.title(), inline=True)
            embed.set_footer(text="Please follow the server rules.")
            await member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _unmute_after(self, member: discord.Member, role: discord.Role, seconds: int) -> None:
        await asyncio.sleep(seconds)
        try:
            await member.remove_roles(role, reason="Auto-Mod mute expired")
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _cleanup_loop(self) -> None:
        """Hourly task to purge automod violations older than 24 hours."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                database.clean_all_old_automod_violations()
            except Exception as exc:
                logger.error("Error during automod violation cleanup: %s", exc)
            await asyncio.sleep(3600)

    # ── /automod command group ──────────────────────────────────────────────────

    automod_group = app_commands.Group(
        name="automod",
        description="Auto-mod configuration and moderation commands",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @automod_group.command(name="config", description="View current auto-mod settings for this server")
    async def automod_config(self, interaction: discord.Interaction) -> None:
        cfg = self._guild_cfg(interaction.guild.id)

        embed = discord.Embed(
            title="🛡️ AUTO-MOD CONFIGURATION",
            color=_MOD_COLOR,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        features = [
            ("Profanity Filter", cfg.get("profanity_filter", True)),
            ("Invite Link Detection", cfg.get("invite_link_detection", True)),
            ("Caps Detection", cfg.get("caps_detection", True)),
            ("Mass Mention Detection", cfg.get("mass_mention_detection", True)),
            ("Everyone Ping Detection", cfg.get("everyone_ping_detection", True)),
            ("Spam Detection", cfg.get("spam_detection", True)),
            ("Link Spam Detection", cfg.get("link_spam_detection", True)),
            ("Emoji Spam Detection", cfg.get("emoji_spam_detection", True)),
            ("Char Spam Detection", cfg.get("char_spam_detection", True)),
            ("Zalgo Detection", cfg.get("zalgo_detection", True)),
            ("Raid Protection", cfg.get("raid_protection", True)),
            ("New Account Detection", cfg.get("new_account_detection", True)),
            ("DM on Action", cfg.get("dm_on_action", True)),
            ("Notify in Channel", cfg.get("notify_in_channel", True)),
        ]
        embed.add_field(
            name="Features",
            value="\n".join(f"{'✅' if enabled else '❌'}  {name}" for name, enabled in features),
            inline=False,
        )

        thresholds = (
            f"Mass Mention: **{cfg.get('mass_mention_threshold', 5)}** users\n"
            f"Spam: **{cfg.get('spam_message_threshold', 5)}** msgs / **{cfg.get('spam_time_window', 5)}s**\n"
            f"Duplicate Msg: **{cfg.get('repeat_message_threshold', 4)}** repeats\n"
            f"Emoji Spam: **{cfg.get('emoji_spam_threshold', 10)}** emojis\n"
            f"Link Spam: **{cfg.get('link_spam_threshold', 3)}** links\n"
            f"Char Spam: **{cfg.get('char_spam_threshold', 8)}** repeated chars\n"
            f"Raid: **{cfg.get('raid_join_threshold', 5)}** joins / **{cfg.get('raid_join_window', 10)}s**"
        )
        embed.add_field(name="Thresholds", value=thresholds, inline=False)

        wl_channels = cfg.get("whitelisted_channels", [])
        wl_roles = cfg.get("whitelisted_roles", [])
        embed.add_field(
            name="Whitelists",
            value=(
                f"Channels: {', '.join(f'<#{c}>' for c in wl_channels) or 'None'}\n"
                f"Roles: {', '.join(f'<@&{r}>' for r in wl_roles) or 'None'}"
            ),
            inline=False,
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @automod_group.command(
        name="whitelist",
        description="Add or remove a channel/role from the auto-mod whitelist",
    )
    @app_commands.describe(
        action="'add' or 'remove'",
        channel="Channel to whitelist",
        role="Role to whitelist",
    )
    async def automod_whitelist(
        self,
        interaction: discord.Interaction,
        action: Literal["add", "remove"],
        channel: discord.TextChannel = None,
        role: discord.Role = None,
    ) -> None:
        if channel is None and role is None:
            await interaction.response.send_message(
                "❌ Provide at least one `channel` or `role`.", ephemeral=True
            )
            return

        guild_cfg = database.get_automod_settings(interaction.guild.id)
        wl_channels: list = guild_cfg.get("whitelisted_channels", [])
        wl_roles: list = guild_cfg.get("whitelisted_roles", [])

        changed: list[str] = []
        if channel:
            if action == "add" and channel.id not in wl_channels:
                wl_channels.append(channel.id)
                changed.append(channel.mention)
            elif action == "remove" and channel.id in wl_channels:
                wl_channels.remove(channel.id)
                changed.append(channel.mention)
        if role:
            if action == "add" and role.id not in wl_roles:
                wl_roles.append(role.id)
                changed.append(role.mention)
            elif action == "remove" and role.id in wl_roles:
                wl_roles.remove(role.id)
                changed.append(role.mention)

        guild_cfg["whitelisted_channels"] = wl_channels
        guild_cfg["whitelisted_roles"] = wl_roles
        database.set_automod_settings(interaction.guild.id, guild_cfg)

        verb = "added to" if action == "add" else "removed from"
        targets = ", ".join(changed) if changed else "no changes made"
        embed = discord.Embed(
            title="✅ WHITELIST UPDATED",
            description=f"{targets} — {verb} the auto-mod whitelist.",
            color=_MOD_COLOR,
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @automod_group.command(
        name="violations",
        description="View a user's auto-mod violation history (last 24 hours)",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.describe(user="The member to check")
    async def automod_violations(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        violations = database.get_automod_violations(interaction.guild.id, user.id)
        embed = discord.Embed(
            title=f"📋 VIOLATIONS — {user}",
            color=_MOD_COLOR,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        if not violations:
            embed.description = "No violations in the last 24 hours."
        else:
            lines = []
            for v in violations[:MAX_DISPLAYED_VIOLATIONS]:
                ts = v["timestamp"][:16].replace("T", " ")
                vtype = v["violation_type"].replace("_", " ").title()
                action = v["action_taken"] or "—"
                lines.append(f"`{ts}` **{vtype}** → {action}")
            embed.description = "\n".join(lines)
            embed.add_field(name="Total (24h)", value=str(len(violations)), inline=True)
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @automod_group.command(
        name="clear",
        description="Clear all auto-mod violations for a user",
    )
    @app_commands.describe(user="The member whose violations to clear")
    async def automod_clear(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        database.clear_automod_violations(interaction.guild.id, user.id)
        embed = discord.Embed(
            title="✅ VIOLATIONS CLEARED",
            description=f"All auto-mod violations for {user.mention} have been cleared.",
            color=_MOD_COLOR,
        )
        embed.set_footer(text=BOT_FOOTER)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoMod(bot))

