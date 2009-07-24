import sys
import pysqlite2.dbapi2 as sql

db = sql.connect('tourneys.sqlite')
c = db.cursor()

args = sys.argv
if len(args) != 3:
    print '''Usage:
python join_tourney <tourney_name> <handle>
'''
    sys.exit(1)

c.execute('''SELECT rowid FROM tourneys WHERE name=?''', (args[1],))
tourneys = c.fetchall()
if len(tourneys) == 0:
    print '*** Tourney %s not found' % (args[1],)
    sys.exit(1)
elif len(tourneys) > 1:
    print '*** %s: more then one tourney matches. this _should_ be impossible.' % (args[1],)
    sys.exit(1)
else:
    (tourney_id,) = tourneys[0]

player = args[2]
c.execute('''SELECT rowid FROM users WHERE handle_lower=?''', (player,))
pid = c.fetchall()
if len(pid) == 0:
    print '*** %s not found' % (player,)
    sys.exit(1)
elif len(pid) > 1:
    print '*** %s: more then one user matches. this _should_ be impossible.' % (player,)
    sys.exit(1)
else:
    (pid,) = pid[0]
        
c.execute('''INSERT INTO players (tourney_id, player_id) VALUES (?, ?)''', (tourney_id, pid))

db.commit()

