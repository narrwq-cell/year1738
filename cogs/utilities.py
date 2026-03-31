import discord
from discord import app_commands
from discord.ext import commands
import datetime
import database


class Utilities(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: **{latency_ms}ms**",
            color=discord.Color.green() if latency_ms < 150 else discord.Color.orange(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Get information about a user.")
    @app_commands.describe(member="The member to look up (defaults to yourself)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        member = member or interaction.user
        stats = database.get_user_stats(member.id, interaction.guild_id)
        roles = [r.mention for r in member.roles if r != interaction.guild.default_role]
        embed = discord.Embed(
            title=f"👤 User Info — {member}",
            color=member.color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(member.created_at.timestamp())}:F>",
            inline=False,
        )
        embed.add_field(
            name="Joined Server",
            value=f"<t:{int(member.joined_at.timestamp())}:F>" if member.joined_at else "Unknown",
            inline=False,
        )
        embed.add_field(
            name=f"Roles ({len(roles)})",
            value=" ".join(roles[:10]) or "None",
            inline=False,
        )
        if stats:
            embed.add_field(name="Messages Sent", value=f"{stats['message_count']:,}", inline=True)
            embed.add_field(name="VC Hours", value=f"{stats['vc_seconds'] / 3600:.1f}h", inline=True)
            embed.add_field(name="Points", value=f"{stats['points']:,}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Get information about the server.")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        embed = discord.Embed(
            title=f"🏠 Server Info — {guild.name}",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="ID", value=str(guild.id), inline=True)
        embed.add_field(
            name="Created",
            value=f"<t:{int(guild.created_at.timestamp())}:F>",
            inline=False,
        )
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Emojis", value=str(len(guild.emojis)), inline=True)
        embed.add_field(name="Boost Level", value=str(guild.premium_tier), inline=True)
        embed.add_field(name="Boosts", value=str(guild.premium_subscription_count), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Get a user's avatar.")
    @app_commands.describe(member="Member whose avatar to display")
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None) -> None:
        member = member or interaction.user
        embed = discord.Embed(
            title=f"🖼️ Avatar — {member.display_name}",
            color=discord.Color.blurple(),
        )
        embed.set_image(url=member.display_avatar.url)
        embed.add_field(
            name="Links",
            value=f"[PNG]({member.display_avatar.with_format('png').url}) | "
                  f"[WEBP]({member.display_avatar.with_format('webp').url})",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="membercount", description="Get the server's member count.")
    async def membercount(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        total = guild.member_count
        humans = sum(1 for m in guild.members if not m.bot)
        bots = total - humans
        embed = discord.Embed(
            title=f"👥 Member Count — {guild.name}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Total", value=str(total), inline=True)
        embed.add_field(name="Humans", value=str(humans), inline=True)
        embed.add_field(name="Bots", value=str(bots), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="embed", description="Create a custom embed message.")
    @app_commands.describe(
        title="Embed title",
        description="Embed description",
        color="Hex color (e.g. FF5733)",
    )
    @app_commands.default_permissions(manage_messages=True)
    async def embed(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        color: str = "5865F2",
    ) -> None:
        try:
            color_int = int(color.lstrip("#"), 16)
        except ValueError:
            color_int = 0x5865F2
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color(color_int),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_footer(text=f"Posted by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="List all available commands.")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="📖 year1738 Bot — Help",
            description="Here are all available slash commands:",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(
            name="⚙️ Moderation",
            value="`/ban` `/kick` `/warn` `/warnings` `/clearwarnings` `/mute` `/unmute` `/clear` `/unban`",
            inline=False,
        )
        embed.add_field(
            name="📊 Leaderboards",
            value="`/leaderboard hours` `/leaderboard messages` `/leaderboard points`",
            inline=False,
        )
        embed.add_field(
            name="🎭 React Roles",
            value="`/reactrole` `/removereactrole`",
            inline=False,
        )
        embed.add_field(
            name="📋 Polls",
            value="`/poll` `/custompoll`",
            inline=False,
        )
        embed.add_field(
            name="🛠️ Utilities",
            value="`/ping` `/userinfo` `/serverinfo` `/avatar` `/membercount` `/embed` `/help`",
            inline=False,
        )
        embed.add_field(
            name="🎉 Fun",
            value="`/joke` `/8ball` `/dice` `/flip` `/random`",
            inline=False,
        )
        embed.set_footer(text="year1738 Bot • All commands are slash commands")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utilities(bot))
