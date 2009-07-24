import sys
import pysqlite2.dbapi2 as sql

db = sql.connect('tourneys.sqlite')
c = db.cursor()

args = sys.argv
if len(args) != 5:
    print '''Usage:
python create_game <tourney_name> <round> <white_handle> <black_handle>
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

try:
    this_round = int(args[2])
except ValueError:
    print '*** %s is not a valid integer.' % (args[2],)
    sys.exit(1)

wplayer = args[3]
c.execute('''SELECT rowid FROM users WHERE handle_lower=?''', (wplayer,))
wpid = c.fetchall()
if len(wpid) == 0:
    print '*** %s not found' % (wplayer,)
    sys.exit(1)
elif len(wpid) > 1:
    print '*** %s: more then one user matches. this _should_ be impossible.' % (wplayer,)
    sys.exit(1)
else:
    (wpid,) = wpid[0]

bplayer = args[4]
c.execute('''SELECT rowid FROM users WHERE handle_lower=?''', (bplayer,))
bpid = c.fetchall()
if len(bpid) == 0:
    print '*** %s not found' % (bplayer,)
    sys.exit(1)
elif len(bpid) > 1:
    print '*** %s: more then one user matches. this _should_ be impossible.' % (bplayer,)
    sys.exit(1)
else:
    (bpid,) = bpid[0]
        
c.execute('''INSERT INTO games (tourney_id, white_id, black_id, result, round) VALUES (?, ?, ?, ?, ?)''', (tourney_id, wpid, bpid, '-', this_round))

db.commit()

