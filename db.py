# A very stripped-down migration management system
import sqlite3
import os

MIGRATIONS = {
    "scene": [
        [
            """
                -- The channel id column is discord's snowflake id
                -- if scene_name is NULL, that means it isn't in use.
                -- Created is the date the scene was opened, while updated is the last post time.
                CREATE TABLE channel_scenes(
                    id INTEGER PRIMARY KEY,
                    channel_name TEXT,
                    created_by INTEGER,
                    created NUMERIC,
                    updated NUMERIC,
                    scene_name TEXT);
            """,
            """
            -- A simple table to keep track of how many rp- channels exist
            CREATE TABLE channels(id INTEGER PRIMARY KEY);
            """
        ]
    ]
}


class Database:
    def __init__(self, server_type: str, server_id: int):
        self.server_type = server_type
        self.server_id = server_id
        self.conn = sqlite3.connect(f'databases/{server_type} {server_id}.db')
        # Create version table if it doesnt exist and check version
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _version(id INTEGER PRIMARY KEY AUTOINCREMENT, date NUMERIC, version INTEGER);
        """)
        version = cursor.execute("""
            SELECT max(version) FROM _version;
        """).fetchone()
        version = 0 if version[0] is None else version[0]
        self.upgrade(version)

    def get(self):
        return self.conn.cursor()
    
    def commit(self):
        self.conn.commit()

    def upgrade(self, start_version: int):
        # retrieve the migrations
        migration = MIGRATIONS[self.server_type]
        # execute required migrations in order        
        cursor = self.get()
        for i in range(start_version, len(migration)):
            for statement in migration[i]:
                cursor.execute(statement)
            cursor.execute("""INSERT INTO _version(date, version) VALUES(datetime('now'), ?);""", (i+1,))
        self.commit()


OPEN_DATABASES = {}
def get_database(server_type: str, server_id: int) -> Database:
    key = (server_type, server_id)
    if key not in OPEN_DATABASES:
        OPEN_DATABASES[key] = Database(server_type, server_id)
    return OPEN_DATABASES[key]


if __name__ == "__main__":
    os.makedirs("databases", exist_ok=True)
    db = Database("scene", 0)