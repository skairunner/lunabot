import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta
import random
import os
from db import get_database
import queries as q
from help import help

if os.getenv("DEVELOPMENT_ENVIRONMENT"):
    client = commands.Bot('?')
else:
    client = commands.Bot('/')

ROLEPLAY_CHANNELS_CATEGORY = 731098249275899947
BOT_CHANNELS = [732660335424569456, 734420054724051014, 733979833758908516]
ROLE_TORPID = 747031337759801404
ROLE_EMBRACED = 733018737355128853
CLAN_ROLES = {
    "brujah": 733019640900485126,
    "gangrel": 733019904973996033,
    "malkavian": 733019933520298087,
    "nosferatu": 733020022628417576,
    "toreador": 733020057063653436,
    "tremere": 733020081394811022,
    "ventrue": 733020100117921885,
    "caitiff": 733028399433383966
}

def get_clan(guild, clan_name: str):
    '''Given a string, return a Role'''
    if clan_name in CLAN_ROLES:
        return guild.get_role(CLAN_ROLES[clan_name])
    return None

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

@client.event
async def on_message(msg):
    '''Do all handling related to checking for messages'''
    if msg.channel.category_id == ROLEPLAY_CHANNELS_CATEGORY:
        # Count!
        db = get_database("leaderboard", msg.guild.id)
        q.record_message(db, msg)
    # Do other command processing too
    await client.process_commands(msg)

@client.event
async def on_raw_message_delete(payload):
    db = get_database("leaderboard", payload.guild_id)
    q.delete_message(db, payload.message_id)
    print(f'Deleted msg with id {payload.message_id}')

#
# DICE COMMANDS
#

def get_dice_emoji(die, difficulty: int = 6):
    if die == 1:
        return ":skull:"
    if die == 10:
        return ":star2:"
    if difficulty <= die:
        return ":drop_of_blood:"
    return ":x:"

def get_soak_dice_emoji(die):
    if 6 <= die:
        return ":shield:"
    return ":black_circle:"

def get_damage_dice_emoji(die):
    if 6 <= die:
        return ":dagger:"
    return ":black_circle:"

# Get the color of the user who sent the message
def get_context_color(ctx):
    return ctx.message.author.color

def get_nick_or_name(ctx):
    author = ctx.message.author
    if author.nick:
        return author.nick
    return author.name

def roll_heuristic(die, diff, specialized=False, no_botch=False):
    if specialized and die == 10:
        return 2
    if die >= diff:
        return 1
    if die == 1 and not no_botch:
        return -1
    return 0
    
async def handle_roll(ctx, pool: int, args, is_specialized = False, is_willpowered = False, is_damage = False, is_soak = False):
    if ctx.message.channel.id not in BOT_CHANNELS:
        await ctx.send("Please use roll commands in <#732660335424569456>! <a:nom:737681170682216549>")
        return

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
    successes = sum([roll_heuristic(roll, diff, is_specialized, is_damage or is_soak) for roll in rolls])
    if is_willpowered:
        if successes < 0:
            successes = 1
        else:
            successes += 1
    if is_damage:
        emoji = [get_damage_dice_emoji(roll) for roll in rolls]
    elif is_soak:
        emoji = [get_soak_dice_emoji(roll) for roll in rolls]
    else:
        emoji = [get_dice_emoji(roll, diff) for roll in rolls]
    die_or_dice = "dice" if pool > 1 else "die"
    if is_willpowered:
        emoji = ["<a:flex:734373583173976075>"] + emoji
    embed_desc = " ".join(emoji)
    embed = discord.Embed(title=remainder, colour=get_context_color(ctx), description=embed_desc)
    author = ctx.message.author
    embed.add_field(name="Rolls", value=str(rolls), inline=True)
    if is_damage:
        if successes < 0:
            successes = 0
        embed.add_field(name="Damage", value=successes, inline=True)
    elif is_soak:
        if successes < 0:
            successes = 0
        embed.add_field(name="Soaked", value=successes, inline=True)
    else:
        if successes < 0:
            embed.add_field(name="Successes", value="Botch!", inline=True)
        else:
            embed.add_field(name="Successes", value=successes, inline=True)
    embed.set_footer(text=get_nick_or_name(ctx), icon_url=author.avatar_url)
    embed.timestamp = datetime.now(timezone.utc)

    if is_damage:
        fmtstr = f"{author.mention} Rolling {pool} damage!"
    elif is_soak:
        fmtstr = f"{author.mention} Rolling {pool} soak!"
    else:
        fmtstr = f"{author.mention} Rolling {pool} {die_or_dice} at difficulty {diff}!"
    await ctx.send(fmtstr, embed=embed)

@help("[dicepool] [difficulty=6] [comment...]", "Plain roll.", "Roll without any special modifiers. If difficulty is not specified, defaults to 6. The comment is optional.")
@client.command(name='r')
@handle_error
async def roll_short(ctx, pool: int, *args):
    await handle_roll(ctx, int(pool), args, False)

@help("wp(?) spec(?) [dicepool] [difficulty=6] [comment...]", "Roll, with optional modifiers.", """Roll with dicepool against difficulty. If difficulty is not specified, it defaults to 6. THe comment is optional. 

You can specify the roll as using willpower by writing 'wp' with no quotes, like this: /roll wp 4

You can specify the roll as specialized, counting 10s as two successes rather than one, by writing 'spec' with no quotes, like this: /roll spec 6

You can also apply both specialization and willpower like this: /roll wp spec 4

The following can be used as shortcuts:
  /r  - Plain roll
  /rs - Roll with specialty
  /w  - Roll with willpower
  /ws - Roll with willpower and specialty
""")
@client.command(name='roll')
@handle_error
async def roll_long(ctx, *args):
    is_specced = False
    is_willpowered = False
    while args[0] in ["spec", "wp"]:
        if args[0] == "spec":
            is_specced = True
        elif args[0] == "wp":
            is_willpowered = True
        args = args[1:]

    pool = int(args[0])
    args = args[1:]
    await handle_roll(ctx, pool, args, is_specced, is_willpowered)

rollspec_decorator = help("[dicepool] [difficulty=6] [comment...]", "Roll with specialization", "Roll with specialization, counting 10s as two successes. If difficulty is not specified, defaults to 6. The comment is optional.")

@rollspec_decorator
@client.command(name='rs')
@handle_error
async def rollspec_short(ctx, pool: int, *args):
    await handle_roll(ctx, int(pool), args, True)

@rollspec_decorator
@client.command(name='rollspec')
@handle_error
async def rollspec_long(ctx, pool: int, *args):
    await handle_roll(ctx, int(pool), args, True)

@help("[dicepool] [difficulty=6] [comment...]", "Roll using willpower", "Rolls using willpower. If difficulty is not specified, defaults to 6. The comment is optional.")
@client.command(name='w')
@handle_error
async def roll_wp(ctx, pool: int, *args):
    await handle_roll(ctx, int(pool), args, is_willpowered = True)


@help("[damage dice] [comment...]", "Roll damage", "Roll damage dice. The comment is optional.")
@client.command(name='dmg')
@handle_error
async def roll_dmg(ctx, pool: int, *args):
    await handle_roll(ctx, int(pool), args, is_damage = True)

@help("[soak dice] [comment...]", "Roll soak", "Roll soak dice. The comment is optional.")
@client.command(name="soak")
@handle_error
async def roll_soak(ctx, pool:int, *args):
    await handle_roll(ctx, int(pool), args, is_soak = True)


#
# SCENE COMMANDS
#

# Check that the user wants to continue interacting with Luna
async def do_stop(ctx, msg):
    if msg.content.lower() in ABORT_COMMANDS:
        await ctx.send("Okay, feel free to ask again later!")
        return True
    if msg.content.lower().startswith("/scene"):
        await ctx.send("It seems you're trying to open multiple scenes at the same time. I'm going to stop opening this scene so we can start over.")
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
    return f"https://discordapp.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"

STAFF_ROLE_ID = 731086961741267024
ADMIN_ROLE_ID = 724654442233987085
# Check if the person is staff
def is_staff(member):
    for role in member.roles:
        if role.id == STAFF_ROLE_ID:
            return True
    return False

# Check if the person is admin
def is_admin(member):
    for role in member.roles:
        if role.id == ADMIN_ROLE_ID:
            return True
    return False

SCENE_LOG = 733418460629172274
ABORT_COMMANDS = ["stop", "nevermind", "nvm"]
@help("[title]", "Start a scene.", "Start a scene. Luna will then ask some follow-up questions about the characters involved and the location.")
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
    if len(title) == 0:
        await ctx.send("It seems you didn't specify a scene title. Please try again!")
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


@help("", "End the scene.", "Ends the scene in the channel that this command is called. Only the user who opened the scene can close it, or a moderator.")
@client.command(name = "end")
@handle_error
async def end_scene(ctx, *args):
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

@help("", "List RP channels", "Lists all the RP channels that exist, as well as whether they are open")
@client.command(name = "listrp")
@handle_error
async def list_scenes(ctx):
    db = get_database("scene", ctx.message.guild.id)
    info = q.list_channels(db)
    output = []
    for name, scene_name in info:
        name = "#" + name[:7]
        scene_name = '"' + scene_name[:30] + '"' if scene_name is not None else "Open!"
        output.append(f'{name.rjust(8)}: {scene_name}')
    output = "\n".join(output)
    await ctx.send(f"```\n{output}\n```")

#
# LEADERBOARD COMMANDS
#

HUMAN_DATE_FORMAT = "%H:%M, %A, %B %e, %Y"
def get_period_human(before=None, after=None):
    '''Turn a period into a human-friendly format'''
    if before is None and after is None:
        raise ValueError("Must provide at least one of before / after!")
    if before is None and after is not None:
        return f"after {after.strftime(HUMAN_DATE_FORMAT)}"
    if before is not None and after is None:
        return f"before {before.strftime(HUMAN_DATE_FORMAT)}"
    return f"between {after.strftime(HUMAN_DATE_FORMAT)} and {before.strftime(HUMAN_DATE_FORMAT)}"

# Fetch leaderboard info & formats it into a Message-ready format
def into_leaderboard(ctx, before=None, after=None, limit=None):
    board = q.count_messages(get_database("leaderboard", ctx.guild.id), before=before, after=after, limit=limit)
    board = [(ctx.guild.get_member(author_id).display_name, count) for author_id, count in board]
    board = [f'    {"Name".center(16, "-")}  Posts'] +  [f'{str(i).rjust(2)}. {t[0][:16].rjust(16)}     {str(t[1]).rjust(2)}' for i, t in enumerate(board, 1)]
    return "```" + "\n".join(board) + "```"

@help("", "Shows the week leaderboard.", "Shows the leaderboard for the current week, from Sunday to the current day.")
@client.command(name="weekly")
@handle_error
async def show_leaderboard_weekly(ctx):
    '''Show the leaderboard for this week'''
    now = datetime.now(timezone.utc)
    start_of_week = now - timedelta(days=(now.weekday() + 1) % 7, hours=now.hour, minutes=now.minute)
    await ctx.send("Here's the leaderboard for this week!\n" + into_leaderboard(ctx, after=start_of_week, limit=10))

@help("", "Show last week's leaderboard", "Shows the leaderboard for last week.")
@client.command(name="lastweek")
@handle_error
async def show_leaderboard_lastweek(ctx):
    '''Show the leaderboard for last week.'''
    now = datetime.now(timezone.utc)
    start_of_last_week = now - timedelta(days=((now.weekday() + 1) % 7 + 7), hours=now.hour, minutes=now.minute)
    start_of_week = now - timedelta(days=(now.weekday() + 1) % 7, hours=now.hour, minutes=now.minute)
    await ctx.send("Here's the leaderboard for last week!\n" + into_leaderboard(ctx, after=start_of_last_week, before=start_of_week))


@help("", "TBA", "Not implemented yet.")
@client.command(name="leaderboard")
@handle_error
async def show_leaderboard(ctx, *args):
    '''Show the leaderboard for a period'''
    pass

@help("[#]", "Delete messages", "Clear the last # messages. Can only be used by staff.")
@client.command(name="clear_last")
@handle_error
async def clear_last(ctx, x: int):
    x = int(x)
    '''clear the last X messages. Only up to 100 at a time.'''
    if not is_admin(ctx.message.author):
        await ctx.send(f"I'm sorry, {ctx.message.author.display_name}, I'm afraid I can't do that. (Only admins can!)")
        return
    if x == 0:
        await ctx.send("Um. Okay, I deleted 0 messages. Just for you.")
        return
    if x < 0 or x > 100:
        await ctx.send("I can only delete a number of messages between 1 and 100. <:nosferatu:732691044574953502>")
        return
    # Do the deleet
    messages =  await ctx.message.channel.history(limit=x).flatten()
    await ctx.channel.delete_messages(messages)
    


#
#  Misc administration
#

def parse_member(ctx, s: str):
    import re
    '''Interpret the string as a member, either searching by id or extracting an ID from a mention. Return None if not possible'''
    # First, if parseable as int, try to get the user
    try:
        id = int(s)
        member = ctx.guild.get_member(id)
        if member is not None:
            return member
    except ValueError:
        pass
    # Next, try to parse as a mention
    match = re.fullmatch(r'<@!?(\d+)>', s.strip())
    if match is not None:
        id = int(match.group(1))
        return ctx.guild.get_member(id)
    return None

@help("[user id/mention] [clan]", "Embrace", "Give the Embraced role to a user, removing Torpid if applicable. Only usable by staff.")
@client.command(name = "embrace")
@handle_error
async def embrace(ctx, *args):
    if len(args) < 1:
        await ctx.send("Please specify who's being embraced!")
        return
    elif len(args) < 2:
        await ctx.send("Please specify which clan to embrace them into!")
        return
    identifier = args[0]
    clan = args[1].lower()
    if not is_staff(ctx.message.author):
        await ctx.send("The gift of the Blood can only be bestowed ... by staff. :woman_vampire:")
        return
    target = parse_member(ctx, identifier)
    if target is None:
        await ctx.send("I couldn't find the person you're trying to embrace :sob:")
        return
    await target.remove_roles(ctx.guild.get_role(ROLE_TORPID), reason=f"Embraced by {ctx.message.author.display_name}")
    clan_role = get_clan(ctx.guild, clan)
    if clan_role is None:
        await ctx.send(f"I'm not sure what clan '{clan}' is :dizzy_face:")
        return
    await target.add_roles(ctx.guild.get_role(ROLE_EMBRACED), clan_role, reason=f"Embraced by {ctx.message.author.display_name}")
    await ctx.send(f"Embraced {target.mention} as {clan}!")

@help("[user id/mention]", "Put someone into Torpor", "Put a user into Torpor, removing the Embraced roll and adding the Torpid role.")
@client.command(name = "torpor")
@handle_error
async def torpor(ctx, *args):
    if not is_staff(ctx.message.author):
        await ctx.send("You aren't powerful enough to put a vampire into Torpor. Only staff can do that. :cross:")
        return
    if len(args) < 1:
        await ctx.send("Please specify who you're putting into torpor! :coffin:")
        return
    target = parse_member(ctx, args[0])
    if target is None:
        await ctx.send("I couldn't find the person you're trying to torpor :sob:")
        return
    await target.remove_roles(ctx.guild.get_role(ROLE_EMBRACED), reason=f"Torpored by {ctx.message.author.display_name}")
    await target.add_roles(ctx.guild.get_role(ROLE_TORPID), reason=f"Torpored by {ctx.message.author.display_name}")
    await ctx.send(f"Put {target.mention} into Torpor!")

@help("", "Make something go wrong", "Triggers the effects that normally happen when Luna suffers an error, which also includes pinging Sky. Use with caution.")
@client.command(name = "error")
@handle_error
async def error(ctx):
    raise Exception("test exception")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=30)

    os.makedirs("databases", exist_ok=True)
    client.run(os.getenv("DISCORD_TOKEN"))
