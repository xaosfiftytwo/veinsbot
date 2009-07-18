import pysqlite2.dbapi2 as sql

db = sql.connect('monkey.db')
c = db.cursor()

# Note that sqlite does not support all this, but still creates the table
# ok. (just not as efficient maybe ...)

# No extra indexes necessary.
c.execute('''CREATE TABLE users (
               handle_lower VARCHAR(17) UNIQUE,
               handle VARCHAR(17),
               admin TINYINT DEFAULT 0
               )''')

c.execute('CREATE INDEX user_handle ON users (handle_lower)')

c.execute('''CREATE TABLE games (
               tourney_id INT,
               white_id INT,
               black_id INT,
               wrating INT,
               brating INT,
               round INT,
               result VARCHAR(7) DEFAULT '-',
               longresult VARCHAR(30) DEFAULT NULL,
               start_time char(19),
               moves TEXT DEFAULT NULL,
               times TEXT DEFAULT NULL
               )''')

c.execute('CREATE INDEX white_player ON games (white_id)')
c.execute('CREATE INDEX black_player ON games (black_id)')

c.execute('''CREATE TABLE tourneys (
                name VARCHAR,
                description VARCHAR,
                controls VARCHAR(9) DEFAULT '45 45',
                status VARCHAR(7) DEFAULT 'OPEN',
                round INT DEFAULT 1,
                show BOOL DEFAULT 1
                )''')

c.execute('CREATE INDEX tourney_name ON tourneys (name)')
c.execute('CREATE INDEX tourney_show ON tourneys (show)')

c.execute('''CREATE TABLE players (
                tourney_id INT,
                player_id INT,
                score FLOAT DEFAULT 0
                )''')

c.execute('CREATE INDEX player_tourney ON players (player_id, tourney_id)')
