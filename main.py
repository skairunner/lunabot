import discord
from discord.ext import commands
from datetime import datetime, timezone
import random
import os


client = commands.Bot('/')

@client.event
async def on_ready():
    print("mrow")

def get_dice_emoji(die, difficulty: int = 6):
    if die == 1:
        return ":skull:"
    if die == 10:
        return ":star2:"
    if difficulty <= die:
        return ":drop_of_blood:"
    return ":x:"

# Get the color of the user who sent the message
def get_context_color(ctx):
    return ctx.message.author.color

def get_nick_or_name(ctx):
    author = ctx.message.author
    if author.nick:
        return author.nick
    return author.name

@client.command(name='r')
async def roll(ctx, pool: int, *args):
    try:
        diff = int(args[0])
        remainder = " ".join(args[1:])
    except Exception:
        diff = 6
        remainder = " ".join(args[:])

    if diff > 10 or diff < 1:
        await ctx.send("The difficulty should be at least 1 and at most 10!")
        return

    rolls = [random.randint(1, 10) for x in range(pool)]
    successes = sum([1 if roll >= diff else 0 for roll in rolls])
    emoji = [get_dice_emoji(roll, diff) for roll in rolls]
    die_or_dice = "dice" if pool > 1 else "die"
    embed_desc = " ".join([get_dice_emoji(roll, diff) for roll in rolls])
    embed = discord.Embed(title=remainder, colour=get_context_color(ctx), description=embed_desc)
    author = ctx.message.author
    embed.add_field(name="Rolls", value=str(rolls), inline=True)
    embed.add_field(name="Successes", value=successes, inline=True)
    embed.set_footer(text=get_nick_or_name(ctx), icon_url=author.avatar_url)
    embed.timestamp = datetime.now(timezone.utc)
    await ctx.send(f"Rolling {pool} {die_or_dice} at difficulty {diff}!", embed=embed)

@client.command(name="")
async def start_scene():
    pass

if __name__ == "__main__":
    os.makedirs("databases", exist_ok=True)
    client.run(os.getenv("DISCORD_TOKEN"))