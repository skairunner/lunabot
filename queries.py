from db import Database
from datetime import datetime
from typing import Union

# Some commonly-used queries

#
# SCENE
#

def get_open_channel(db: Database) -> Union[None, int]:
    '''Return any channel with no scene going on, or return None if that isn't possible'''
    c = db.get()
    result = c.execute("SELECT id FROM channel_scenes WHERE created IS NULL;").fetchone()
    return None if result is None else result[0]

class ChannelInfo:
    def __init__(self, is_available: bool, created_by, created_at, updated_at):
        self.is_available = is_available
        self.created_by = None if is_available else created_by
        self.created_at = None if is_available else created_at
        self.updated_at = None if is_available else updated_at

def get_channel_info(db: Database, channel_id: int) -> Union[None, ChannelInfo]:
    '''Return the information for a given channel'''
    c = db.get()
    info = c.execute("SELECT created_by, created, updated FROM channel_scenes WHERE id=?", (channel_id,)).fetchone()
    if info is None:
        return None

    return ChannelInfo(
        True if info[0] is None else False,
        *info
    )

def add_new_channel(db: Database, channel_id: int, channel_name: str):
    '''Make the database aware of a new channel'''
    c = db.get()
    c.execute("INSERT INTO channels(id) VALUES(?)", (channel_id,))
    c.execute("INSERT INTO channel_scenes(channel_name, id) VALUES(?, ?)", (channel_name, channel_id))
    db.commit()

def reserve_channel(db: Database, channel_id: int, scene_name: str, author_id: int):
    '''Reserve a channel for a scene'''
    c = db.get()
    c.execute("UPDATE channel_scenes SET created=datetime('now', 'utc'), scene_name=?, updated=datetime('now', 'utc'), created_by=? WHERE id=?",
        (scene_name, author_id, channel_id))
    db.commit()

def free_channel(db: Database, channel_id: int):
    '''Free a channel for use in another scene'''
    c = db.get()
    c.execute("UPDATE channel_scenes SET created=NULL, updated=NULL, scene_name=NULL, created_by=NULL WHERE id=?", (channel_id,))
    db.commit()

def count_channels(db: Database) -> int:
    return db.get().execute("SELECT count(*) FROM channels;").fetchone()[0]

#
# LEADERBOARD
#

def date_as_sql(d: datetime):
    return d.strftime('%Y-%m-%d %H:%M:%S')

def record_message(db: Database, msg):
    '''Add message info to the database'''
    db.get().execute("INSERT INTO messages(author, date, channel_id, message_id) VALUES(?, datetime('now', 'utc'), ?, ?);",
    (msg.author.id, msg.channel.id, msg.id))
    db.commit()

def count_messages(db: Database, before=None, after=None, limit: int =None):
    '''Count the number of messages per person in the given time range'''
    clauses = []
    variables = []
    if before is not None:
        clauses.append("date < ?")
        variables.append(date_as_sql(before))
    if after is not None:
        clauses.append("date > ?")
        variables.append(date_as_sql(after))
    clauses = " AND ".join(clauses)
    where_clause = '' if before is None and after is None else f'WHERE {clauses}'
    limit_clause = '' if limit is None else f'LIMIT {limit}'
    return db.get().execute(f"SELECT author, COUNT(*) FROM messages {where_clause} GROUP BY author ORDER BY COUNT(*) DESC {limit_clause};", variables).fetchall()