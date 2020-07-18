import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone
import random
import os
from db import get_database
import queries as q

client = commands.Bot('/')

def handle_error(f):
    async def inner(ctx, *args, **kwargs):
        try:
            await f(ctx, *args, **kwargs)
        except Exception as e:
            await ctx.send("Oh no, something went wrong! Please alert <@164963698274729985>!")
            raise e
    return inner

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
@handle_error
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
    await ctx.send(f"{author.mention} Rolling {pool} {die_or_dice} at difficulty {diff}!", embed=embed)

# Check that the user wants to continue interacting with Luna
async def do_stop(ctx, msg):
    if msg.content.lower() in ABORT_COMMANDS:
        await ctx.send("Okay, feel free to ask again later!")
        return True
    return False

# Get the scene start header!
def get_scene_start_header(title: str, author, description: str, url = None):
    embed = discord.Embed(title=title, color=author.color, description=description)
    embed.timestamp = datetime.now(timezone.utc)
    embed.set_footer(text=author.display_name, icon_url=author.avatar_url)

    if url is not None:
        embed.url = url
    
    return embed

def get_message_link(msg):
    return f"https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"

STAFF_ROLE_ID = 731086961741267024
# Check if the person is staff
def is_staff(member):
    for role in member.roles:
        if role.id == STAFF_ROLE_ID:
            return True
    return False


ROLEPLAY_CHANNELS_CATEGORY = 731098249275899947
SCENE_LOG = 733418460629172274
ABORT_COMMANDS = ["stop", "nevermind", "nvm"]
@client.command(name="scene")
@handle_error
async def start_scene(ctx, *args):
    def reply(m):
        return m.channel == channel and m.author == author

        # Get user input stuff
    title = " ".join(args)
    if len(title) >= 256:
        await ctx.send("I would love to open a scene for you, but your title is too long. Please try again, making sure to keep your title under 256 characters!")
        return
    channel = ctx.message.channel
    author = ctx.message.author
    guild = ctx.message.channel.guild
    await ctx.send(f"I will start a scene named `{title}` for you. Which characters are in this scene?")
    
    async with ctx.typing():
        msg = await ctx.bot.wait_for('message', check=reply)
        if await do_stop(ctx, msg):
            return
    characters = msg.content
    await ctx.send("Okay! Where is the scene happening? Feel free to look at <#732651975061274734> for inspiration!")
    
    async with ctx.typing():
        msg = await ctx.bot.wait_for('message', check=reply)
        if await do_stop(ctx, msg):
            return
    location = msg.content
    # Check the database to see if there is a free channel
    db = get_database("scene", guild.id)
    c = q.get_open_channel(db)
    if c is None:
        # Need to make the channel
        category = guild.get_channel(ROLEPLAY_CHANNELS_CATEGORY)
        channel_number = q.count_channels(db)
        channel = await guild.create_text_channel(f'rp-{channel_number + 1}', category=category)
        # Update db to keep everything in sync
        q.add_new_channel(db, channel.id, channel.name)
        c = channel.id
    # Lock the channel
    q.reserve_channel(db, c, title, author.id)
    await ctx.send(f"Your scene has been opened in <#{c}>. Have fun!")

    # Notify channel of scene start
    channel = guild.get_channel(c)
    # Channel editing has low rate limit, so do it async
    asyncio.create_task(channel.edit(reason=f"Scene '{title}' started with {author.display_name}", topic=f"{title}: {characters} @ {location}"))

    scene_start = await channel.send(f"{author.mention} Scene started!", embed=get_scene_start_header(title, author, f"{characters} @ {location}"))
    # Put it in scene logs
    scenelog = guild.get_channel(SCENE_LOG)
    await scenelog.send(embed=get_scene_start_header(title, author, f"{characters} @ {location}", get_message_link(scene_start)))


@client.command(name = "end")
@handle_error
async def end_scene(ctx):
    # Message is deleted first
    await ctx.message.delete()

    db = get_database("scene", ctx.message.guild.id)
    info = q.get_channel_info(db, ctx.message.channel.id)
    # It has to be a channel that is an RP channel & in use
    if info is None or info.is_available:
        return
    author = ctx.message.author
    # Next, check that the author is either the same as the person who made the scene, or is a staff
    if info.created_by == author.id or is_staff(author):
        q.free_channel(db, ctx.message.channel.id)
        await ctx.send(embed=discord.Embed(description="End scene."))
        # Finally, reset the channel message.
        await ctx.message.channel.edit(reason=f"Scene ended by {author.display_name}", topic="A roleplay channel. Type /scene your_scene_name in any channel to get started!")

@client.command(name = "error")
@handle_error
async def error(ctx):
    raise Exception("test exception")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=30)

    os.makedirs("databases", exist_ok=True)
    client.run(os.getenv("DISCORD_TOKEN"))