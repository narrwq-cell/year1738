import discord
from discord.ext import commands
import re
import json
import datetime
import asyncio
import logging
import database
from cogs.moderation import send_mod_log, get_or_create_muted_role

logger = logging.getLogger("year1738.auto_mod")

INVITE_PATTERN = re.compile(
    r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/[a-zA-Z0-9\-]+",
    re.IGNORECASE,
)


class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._mute_tasks: dict[tuple, asyncio.Task] = {}

    @property
    def cfg(self) -> dict:
        return self.bot.config.get("auto_mod", {})

    def _is_enabled(self) -> bool:
        return self.cfg.get("enabled", True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self._is_enabled():
            return
        if message.author.bot or message.guild is None:
            return
        # Skip members with manage_messages permission
        if message.author.guild_permissions.manage_messages:
            return

        violations = []

        # Profanity filter
        if self.cfg.get("profanity_filter", True):
            content_lower = message.content.lower()
            profanity_list = self.bot.config.get("profanity_words", [])
            for word in profanity_list:
                if word.lower() in content_lower:
                    violations.append(("profanity", f"Profanity detected: `{word}`"))
                    break

        # Invite link detection
        if self.cfg.get("invite_link_detection", True):
            if INVITE_PATTERN.search(message.content):
                violations.append(("invite", "Unauthorized Discord invite link"))

        # All-caps spam
        caps_threshold = self.cfg.get("caps_threshold", 0.7)
        caps_min = self.cfg.get("caps_min_length", 10)
        if len(message.content) >= caps_min:
            letters = [c for c in message.content if c.isalpha()]
            if letters and sum(1 for c in letters if c.isupper()) / len(letters) >= caps_threshold:
                violations.append(("caps", "Excessive caps"))

        # Mass mention spam
        mention_threshold = self.cfg.get("mass_mention_threshold", 5)
        if len(message.mentions) >= mention_threshold:
            violations.append(("mass_mention", f"Mass mention ({len(message.mentions)} users)"))

        # Spam detection
        if self.cfg.get("spam_detection", True):
            spam_result = await self._check_spam(message)
            if spam_result:
                violations.append(("spam", spam_result))

        if not violations:
            return

        # Delete the message
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        # Determine severity: use the most severe violation
        severity_order = ["spam", "mass_mention", "invite", "caps", "profanity"]
        severity = next((v for v in severity_order if any(viol[0] == v for viol in violations)), "profanity")

        reason = "; ".join(v[1] for v in violations)
        await self._take_action(message.author, message.guild, message.channel, reason, severity)

    async def _check_spam(self, message: discord.Message) -> str:
        """Returns a violation reason string or empty string if no spam detected."""
        user_id = message.author.id
        guild_id = message.guild.id
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        window = self.cfg.get("spam_time_window", 5)
        threshold = self.cfg.get("spam_message_threshold", 5)

        row = database.get_spam_data(user_id, guild_id)
        try:
            times = json.loads(row["message_times"])
        except (json.JSONDecodeError, TypeError):
            times = []

        # Remove timestamps outside the window
        times = [t for t in times if now - t < window]
        times.append(now)

        # Check repeated text
        last_msg = row["last_message"] or ""
        repeat_count = row["repeat_count"] or 0
        if message.content and message.content.lower() == last_msg.lower():
            repeat_count += 1
        else:
            repeat_count = 1

        database.update_spam_data(user_id, guild_id, json.dumps(times), message.content, repeat_count)

        if len(times) >= threshold:
            return f"Message spam ({len(times)} messages in {window}s)"
        if repeat_count >= 4:
            return f"Repeated message spam ({repeat_count} times)"
        return ""

    async def _take_action(
        self,
        member: discord.Member,
        guild: discord.Guild,
        channel: discord.abc.Messageable,
        reason: str,
        severity: str,
    ) -> None:
        warn_threshold = self.cfg.get("warn_threshold", 3)
        mute_threshold = self.cfg.get("mute_threshold", 5)
        kick_threshold = self.cfg.get("kick_threshold", 7)
        mute_duration = self.cfg.get("mute_duration_minutes", 10)

        # Always add a warning
        database.add_warning(guild.id, member.id, self.bot.user.id, f"[Auto-Mod] {reason}")
        warn_count = database.get_warning_count(guild.id, member.id)

        action_taken = "warned"

        if warn_count >= kick_threshold:
            try:
                await member.kick(reason=f"[Auto-Mod] {reason} (too many violations)")
                action_taken = "kicked"
                database.log_mod_action(guild.id, member.id, self.bot.user.id, "kick", f"[Auto-Mod] {reason}")
            except (discord.Forbidden, discord.HTTPException):
                pass
        elif warn_count >= mute_threshold:
            try:
                role_name = self.bot.config.get("muted_role_name", "Muted")
                muted_role = await get_or_create_muted_role(guild, role_name)
                await member.add_roles(muted_role, reason=f"[Auto-Mod] {reason}")
                action_taken = f"muted for {mute_duration}m"
                database.log_mod_action(guild.id, member.id, self.bot.user.id, "mute",
                                        f"[Auto-Mod] {reason}", duration_minutes=mute_duration)
                key = (member.id, guild.id)
                if key in self._mute_tasks:
                    self._mute_tasks[key].cancel()
                self._mute_tasks[key] = asyncio.create_task(
                    self._unmute_after(member, muted_role, mute_duration * 60)
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        embed = discord.Embed(
            title="🤖 Auto-Mod Action",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
        embed.add_field(name="Action", value=action_taken.title(), inline=True)
        embed.add_field(name="Violation", value=reason, inline=False)
        embed.add_field(name="Total Warnings", value=str(warn_count), inline=True)

        try:
            await channel.send(embed=embed, delete_after=10)
        except discord.Forbidden:
            pass
        await send_mod_log(self.bot, guild, embed)

    async def _unmute_after(self, member: discord.Member, role: discord.Role, seconds: int) -> None:
        await asyncio.sleep(seconds)
        try:
            await member.remove_roles(role, reason="Auto-Mod mute expired")
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoMod(bot))
