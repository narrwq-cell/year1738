import discord

# Your bot token
TOKEN = 'YOUR_TOKEN'

# Create an instance of the bot
bot = discord.Bot()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Run the bot
bot.run(TOKEN)