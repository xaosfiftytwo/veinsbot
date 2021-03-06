"""A small tourney manager on the base of the icsbot package.
"""

__original_author__ = 'Sebastian Berg'
__co_author__ = 'xaosfiftytwo'
__copyright__ = 'Sebastian Berg 2008'
__license__ = 'LGPL v3'

import time
import sys

import icsbot
import icsbot.status
import icsbot.parser.moves
import icsbot.parser.gamelist
import icsbot.misc.sqldata
from icsbot.misc.tells import parse

import games as games_module

from itertools import groupby
from operator import itemgetter

sys.stderr = file('output.txt', 'a')

database = 'tourneys.sqlite'

# Main loop in case of disconnections, just recreating the bot right now.
# Should not actually be necessary.
while True:
    # bot = icsbot.IcsBot(qtell_dummy=True) # Add qtell_dummy=True for running without TD.
    bot = icsbot.IcsBot() # Add qtell_dummy=True for running without TD.

    users = bot['users']
    # Enable Status getting on user (keeps online users)
    icsbot.status.Status(bot)
    # Add parsing for moves.
    icsbot.parser.moves.Moves(bot)
    # Enable getting of starting/ending games (and storing a list based on this)
    icsbot.parser.gamelist.GameList(bot)
    
    # Online users, as well as info from the database (if exists)
    icsbot.misc.sqldata.SqlData(database, dataset=users, table='users')
    
    # These are the stored games that I need pairings for, not the ones
    # on the server:
    games_module.Games(bot, database, announce_channel='177', no_td=False)
    games = bot['games']
    
    dcursor = games.sql.dcursor # just a hack to get a cursor to the database.

    # get game scores from the database
    dcursor.execute('SELECT win, draw, loss FROM game_scores ORDER BY rowid DESC')
    aux_scores = dcursor.fetchall()
    if len(aux_scores) == 0:
        raise AssertionError, 'No game scores found in db.'
    assert len(aux_scores) == 1, 'Duplicate game scores found in db.'

    scores = {'1-0': (aux_scores[0]['win'],aux_scores[0]['loss']), 
              '0-1': (aux_scores[0]['loss'],aux_scores[0]['win']), 
              '1/2-1/2': (aux_scores[0]['draw'],aux_scores[0]['draw'])
              }

    # get league scores from the database
    dcursor.execute('SELECT rank, score FROM league_scores ORDER BY rank ASC')
    aux_scores = dcursor.fetchall()
    league_scores = []
    for aux_score in aux_scores:
        league_scores.append(aux_score['score'])
                             
    
    ###################################
    
    def result_changed(game, item, old, new):
        if old in scores.keys():
            dcursor.execute('UPDATE players SET score=score-? WHERE player_id=? and tourney_id=?', (scores[old][0], game['white_id'], game['tourney_id']))
            dcursor.execute('UPDATE players SET score=score-? WHERE player_id=? and tourney_id=?', (scores[old][1], game['black_id'], game['tourney_id']))
    
        if new in scores.keys():
            dcursor.execute('UPDATE players SET score=score+? WHERE player_id=? and tourney_id=?', (scores[new][0], game['white_id'], game['tourney_id']))
            dcursor.execute('UPDATE players SET score=score+? WHERE player_id=? and tourney_id=?', (scores[new][1], game['black_id'], game['tourney_id']))
    
    games.register('result', result_changed)    
    
    # As guest we don't want to get kicked. So send bogus stuff every 50 minutes:
    def anti_kick_timer():
        bot.send('$asdf')
        bot.timer(time.time()+50*60, anti_kick_timer)
    
    bot.timer(time.time()+50*60, anti_kick_timer)
    
    
    # Some more tell commands:
    def standings(usr, args, tags):
        s = args.split()
        if len(args) < 1:
            return league_standings(usr, args, tags)
        else:
            return tourney_standings(usr, args, tags)

    def tourney_standings(usr, args, tags):
        s = args.split()
        dcursor.execute('SELECT rowid, * FROM tourneys WHERE name=?', (s[0],))
        tourney = dcursor.fetchall()
        if len(tourney) == 0:
            return bot.qtell.split(usr, 'The tourney "%s" does not exist.' % s[0])
        elif len(tourney) > 1:
            return bot.qtell.split(usr, 'More then one tourney matches. This _should_ be impossible.')
        
        dcursor.execute('SELECT users.handle as handle, score FROM players LEFT JOIN users ON users.rowid=player_id WHERE tourney_id=? ORDER BY score DESC, handle ASC', (tourney[0]['rowid'],))
        standings = dcursor.fetchall()
        
        if len(standings) < 1:
            return bot.qtell.split(usr, 'There are no players in this tourney.')
        
        l = ['+-------------------+-------+', '| handle            | score |', '+-------------------+-------+']
        for s in standings:
               l.append(unicode_to_ascii('| %-17s | %5s |' % (s['handle'], str(s['score']))))
        l.append('+-------------------+-------+')
        return bot.qtell.send_list(usr, l)

    # helper function
    def groupby_score(data, key=itemgetter(0), value=itemgetter(1)):
        """Summarise the supplied data.

        Produce a groupby_score of the data, grouped by the given key (default: the
        first item), and giving totals of the given value (default: the second
        item).
        
        The key and value arguments should be functions which, given a data
        record, return the relevant value.
        """

        for k, group in groupby(data, key):
            result = []
            for row in group:
                result.append(value(row))
            yield (k, result)

    # helper function
    def unicode_to_ascii(ustring):
        from unicodedata import normalize
        return normalize('NFKD', ustring).encode('ASCII', 'ignore')

    def league_standings(usr, args, tags):
        dcursor.execute('SELECT DISTINCT tourney_id FROM players ORDER BY tourney_id ASC')
        tourneys = dcursor.fetchall()

        if len(tourneys) == 0:
            return bot.qtell.split(usr, 'No tourneys found in players table.')

        league_standings = {}
        for tourney in tourneys:
            dcursor.execute('SELECT users.handle as handle, score FROM players LEFT JOIN users ON users.rowid=player_id WHERE tourney_id=? ORDER BY score DESC, handle ASC', (tourney['tourney_id'],))
            tourney_standings = dcursor.fetchall()
        
            if len(tourney_standings) < 1:
                continue

            aux_standings = []
            for standing in tourney_standings:
                aux_standings.append((int(standing['score'] * 10.0), standing['handle']))
            scorers = rank = 0
            for score, handles in groupby_score(aux_standings, key=itemgetter(0), value=itemgetter(1)):
                if score > 0:
                    for handle in handles:
                        league_standings[handle] = league_standings.get(handle, 0) + league_scores[rank]
                        scorers += 1
                    if scorers < len(league_scores):
                        rank += len(handles)
                        continue
                    else:
                        break
                else:
                    break

        # sort league_standings on score desc, handle asc
        aux_standings = [ (league_standings[k], k) for k in league_standings.keys() ]
        
        if len(aux_standings) == 0:
            return bot.qtell.split(usr, 'No player has scored ever.')

        aux_standings.sort(reverse=True)
        aux_standings = [ (score, handles) for score, handles in groupby_score(aux_standings, key=itemgetter(0), value=itemgetter(1)) ]

        l = ['+-------------------+-------+', '| handle            | score |', '+-------------------+-------+']
        for (score, handles) in aux_standings:
            handles.sort()
            for handle in handles:
               l.append(unicode_to_ascii('| %-17s | %5s |' % (handle, str(score))))
        l.append('+-------------------+-------+')
        return bot.qtell.send_list(usr, l)
    
    def who(usr, args, tags):
        s = args.split()
        if len(s) < 1:
            return bot.qtell.split(usr, 'You must give a tournament.')
        
        dcursor.execute('SELECT rowid, * FROM tourneys WHERE name=?', (s[0],))
        tourney = dcursor.fetchall()
        if len(tourney) == 0:
            return bot.qtell.split(usr, 'The tourney "%s" does not exist.' % s[0])
        elif len(tourney) > 1:
            return bot.qtell.split(usr, 'More then one tourney matches. This _should_ be impossible.')
        
        dcursor.execute('SELECT users.handle as handle, score FROM players LEFT JOIN users ON users.rowid=player_id WHERE tourney_id=? ORDER BY handle ASC', (tourney[0]['rowid'],))
        standings = dcursor.fetchall()
        
        if len(standings) < 1:
            return bot.qtell.split(usr, 'There are no players in this tourney.')
        
        l = ['+-------------------+', '| handle            |', '+-------------------+']
        for s in standings:
               l.append(unicode_to_ascii('| %-17s |' % (s['handle'],)))
        l.append('+-------------------+')
        return bot.qtell.send_list(usr, l)
    
    
    def join(usr, args, tags):
        """join <tourneyname>, will add you to the players for the tourney."""
        # We only make it executable for registered users.
        s = args.split()
        if len(s) < 1:
            return bot.qtell.split(usr, 'You must give a tournament.')
        dcursor.execute('SELECT rowid, * FROM tourneys WHERE name=? and status="OPEN"', (s[0],))
        tourney = dcursor.fetchall()
        if len(tourney) == 0:
            return bot.qtell.split(usr, 'The tourney "%s" does not exist or is not OPEN.' % s[0])
        elif len(tourney) > 1:
            return bot.qtell.split(usr, 'More then one tourney matches. This _should_ be impossible.')
        tourney = tourney[0]
        
        dcursor.execute('SELECT * FROM players WHERE player_id=? and tourney_id=?', (usr['rowid'], tourney['rowid']))
        if len(dcursor.fetchall()) > 0:
            return bot.qtell.split(usr, 'You are already signed up for this tourney.')
        
        dcursor.execute('INSERT INTO players (tourney_id, player_id) VALUES (?, ?)', (tourney['rowid'], usr['rowid']))
        
        return bot.qtell.split(usr, 'You were added as a player in the tourney.')
    
    
    def add_player(usr, args, tags):
        """+player handle [handle ...]"""
        s = args.split()
        if len(s) == 0:
            return bot.qtell.split(usr, 'You must give at least one handle.')
        added = []
        wrong = []
        existed = []
        for user in s:
            if user:
                if len(user)>17 or not user.isalpha():
                    wrong.append(user)
                    continue
                if not users[user]['rowid']:
                    users[user]['admin'] = False
                    #dcursor.execute('INSERT INTO users (handle_lower, handle) VALUES (?, ?)', (user.lower(), user))
                    added.append(user)
                    users[user].load('rowid') # make sure that it is now handled
                                              # by the database.
                else:
                    existed.append(user)
        return bot.qtell.split(usr, 'The following users were added: %s\nThese handles are invalid: %s\nThese already existed in the database: %s' % (', '.join(added), ', '.join(wrong), ', '.join(existed)))       
    
    
    def list_tourneys(usr, args, tags):
        to_send = []
        to_send.append('+---------+---------+--------+-------+')
        to_send.append('| Tourney | Control | Status | Round |')
        to_send.append('+---------+---------+--------+-------+')
        dcursor.execute('SELECT * FROM tourneys WHERE show=1 ORDER BY rowid')
        tourneys = dcursor.fetchall()
        if not tourneys:
            return bot.qtell.split(usr, 'There are currently no tourneys (shown).')
        for tourney in tourneys:
            to_send.append(unicode_to_ascii(
                    '| %7s | %7s | %6s | %5s |' % 
                    (tourney['name'], tourney['controls'], tourney['status'], tourney['round'])))
        to_send.append('+---------+---------+--------+-------+')
        return bot.qtell.send_list(usr, to_send)
    
    
    def die(usr, args, tags):
        """die will kill the bot permanently
        """
        import sys
        sys.exit()
    
    def restart(usr, args, tags):
        """restart will have the bot log out, restart and come back.
        """
        bot.close()
    
    
    def create_pgn(usr, args, tags):
        """createpgn tourney [round] [-c <clock_type>]
        Prompts bot to create a tourney/round pgn with the name tourney_name-round.pgn
        or just tourney_name if no round was given, and dump it into the pgns folder.
        -c sets the clock type that is used. Currently can have 1. no option
        -> no time stamps, 2. clk -> clock reading (default) 3. emt -> (elapsed move
        time) time stamps.
        """
        import icsbot.misc.pgn as pgn
        import os
        
        clocks = {None: None, 'clk': pgn.clk, 'emt': pgn.emt}
        
        args = parse(args)
        if len(args[0]) > 0:
            tourn = args[0][0]
        else:
            return bot.qtell.split(usr, 'You must give a tourney.')
        
        if len(args[0]) > 1:
            try:
                r = int(args[0][1])
            except:
                return bot.qtell.split(usr, 'Round must be an integer.')
        else:
            r = None
        
        to_send = []
        if args[1].has_key('c') and len(args[1]['c']) > 0:
            if args[1]['c'][0] in clocks:
                clock = clocks[args[1]['c'][0]]
            else:
                to_send = ['Invalid clock setting "%s", defaulting to no clock info.' % args[1]['c']]
                clock = clocks[None]
        else:
            clock = clocks[None]
        
        if r is not None:
            insert = ' and round=%s' % r
        else:
            insert = ''
        
        dcursor.execute('SELECT rowid, * FROM tourneys WHERE name=?', (tourn,))
        tourney = dcursor.fetchall()
        if len(tourney) == 0:
            return bot.qtell.split(usr, 'The tourney "%s" does not exist.' % tourn)
        elif len(tourney) > 1:
            return bot.qtell.split(usr, 'More then one tourney matches. This _should_ be impossible.')
    
        tourney = tourney[0]
        dcursor.execute('SELECT rowid FROM games WHERE tourney_id=?%s and (result!="-" or result!="*")' % insert, (tourney['rowid'],))
        gs = dcursor.fetchall()
        if not gs:
            return bot.qtell.split(usr, 'There are no finished games in tourney %s for round %s.' % (tourney['name'], r))
        
        pgns = []
        for g in gs:
            g = games[g['rowid']]
            g.load('rowid')
            g = g.copy()
            tc = g['controls']
            tc = tc.split()
            g['time'] = int(tc[0])
            g['inc'] = int(tc[1])
            if g['tourney_description'] is not None:
                g['tourney'] = g['tourney_description']
            pgns.append(pgn.make_pgn(g, format_time=clock))
        
        pgns = filter(lambda x: x is not False, pgns)
        
        try:
            if r is None:
                f = file('pgns' + os.path.sep + tourney['name'] + '.pgn', 'w')
            else:
                f = file('pgns' + os.path.sep + tourney['name'] + '_%s' % str(r).zfill(2) + '.pgn', 'w')
            
            f.write('\n\n'.join(pgns))
            
        except IOError:
            return bot.qtell.split(usr, 'There was an error saving the pgn, maybe the pgns folder does not exist.')
        
        return bot.qtell.send_list(usr, to_send + ['The pgn was created successfully.'])
        
    
    bot.reg_tell('standings', standings)
    bot.reg_tell('who', who)
    # If the user does not have 'rowid', he is not in the database.
    bot.reg_tell('join', join, lambda usr, tags: usr['rowid'])
    bot.reg_tell('+player', add_player, lambda usr, tags: usr['admin'])
    bot.reg_tell('createpgn', create_pgn, lambda usr, tags: usr['admin'])
    bot.reg_tell('die', die, lambda usr, tags: usr['admin'] or '*' in tags or 'SR' in tags)
    bot.reg_tell('restart', restart, lambda usr, tags: usr['admin'] or '*' in tags or 'SR' in tags)
    bot.reg_tell('list', list_tourneys)
    
    try:
        bot.connect('handle', 'password')
    except icsbot.InvalidLogin, msg:
        print msg
        if str(msg) == 'Handle in use.':
            print 'Restarting'
            time.sleep(3)
            continue
        print 'Quitting.'
        break
    except icsbot.ConnectionClosed, msg:
        print 'Connection was lost, because:', msg
        print 'Restarting'
        time.sleep(3)
        continue
    except icsbot.socket.error, msg:
        print 'Socket error:', msg
        print 'Restarting'
        time.sleep(3)
        continue
    
    print 'Connected to FICS.'
    
    try:
        bot.run()
    except icsbot.ConnectionClosed, msg:
        if str(msg) == 'Someone logged in as me.':
            print 'Connection was lost, because someone logged in as me.'
            print 'Quitting.'
            break
        print 'Connection was lost, because:', msg
        print 'Restarting'
    except icsbot.socket.error, msg:
        print 'Socket error:', msg
        print 'Restarting'
    
    time.sleep(3)
