# Updated embed utility functions for minimalistic style

def create_minimalistic_embed(title, description):
    import discord
    embed = discord.Embed(title=title, description=description)
    embed.color = discord.Color.from_rgb(0, 0, 0)  # Black color
    return embed

# ... (other functions that create embeds will use create_minimalistic_embed)

