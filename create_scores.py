import pysqlite2.dbapi2 as sql

db = sql.connect('monkey.db')
c = db.cursor()

c.execute('''CREATE TABLE game_scores (
                win FLOAT DEFAULT 0 ,
                draw FLOAT DEFAULT 0,
                loss FLOAT DEFAULT 0
                )''')

c.execute('''CREATE TABLE league_scores (
                rank INT,
                score FLOAT DEFAULT 0
                )''')

c.execute('CREATE INDEX rank ON league_scores (rank)')

c.execute('''INSERT INTO game_scores (win, draw, loss) VALUES (?, ?, ?)''', (1.0, 0.5, 0.0))

c.execute('''INSERT INTO league_scores (rank, score) VALUES (?, ?)''', (1, 3.0))
c.execute('''INSERT INTO league_scores (rank, score) VALUES (?, ?)''', (2, 2.0))
c.execute('''INSERT INTO league_scores (rank, score) VALUES (?, ?)''', (3, 1.0))
db.commit()
