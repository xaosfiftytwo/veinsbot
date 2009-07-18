#-*- coding: utf-8 -*-
from icsbot.misc.tells import parse
import time

class Games(object):
    """Class to creates an games object with the extra info on games to start and
    games to end, and those always cached. For a database with the items:
        c.execute('''CREATE TABLE games (
                       rowid INTEGER PRIMARY KEY,
                       result VARCHAR(7) DEFAULT '-',
                       )''')
    And of course more, check code, seriously :).

    It does the important thing of adding:
    to_end and to_start (so icsbot['games'].to_end and icsbot['games'].to_start)
    which makes sure that those are always cached and the list available.
    to_end are all those with * or ADJ as result, to_start all those with - as
    result.

    This class is then expanded to also handle gamestarting and gameending related
    events. This module needs the sgames dataset being filled by parser.gamelist.
    
    There is the option of having the class announce games. For that you need
    to set an announce_channel = 144, etc. You can set a list/tuple of times to
    announce, default announce_times = (00, 15, 30, 45). If you set no_td=True,
    the bot will ask players to match them instead of issue the match command.
    """
    def __init__(self, icsbot, database, announce_channel=None, announce_times=(00, 15, 30, 45), no_td=False):
        """Run function to create the necessary games things.
        """
        from icsbot.misc import sqldata
        
        self.icsbot = icsbot
        self.no_td = no_td
        
        games = icsbot['games', 'rowid']
        
        sqldata.SqlData(database=database, dataset=games, table='games', joins='LEFT JOIN users as white ON white.rowid=white_id LEFT JOIN users as black ON black.rowid=black_id LEFT JOIN tourneys ON tourneys.rowid=tourney_id', columns='start_time, wrating, brating, games.round as round, result, longresult, moves, times, controls, white_id, black_id, tourney_id', join_columns='white.handle as white, black.handle as black, tourneys.name as tourney, tourneys.description as tourney_description, controls')
        
        self.games = games
        
        games.sql.cursor.execute('SELECT rowid FROM games WHERE result="*" or result="ADJ"')
        to_end = games.sql.cursor.fetchall()
        games.to_end = set()
        for spam in to_end:
            games.to_end.add(games[spam[0]])
        
        self.games.to_start = set()
        
        # A set of games we need to store info on. This is just privateself.
        self.to_store = set()
        
        games.register('result', self.result_change)
        icsbot['sgames'].register('start_time', self.game_start)
        icsbot['sgames'].register('update_time', self.game_might_run)
        icsbot['sgames'].register('end_time', self.game_end)
        
        icsbot['sgames'].register('got_all', self.all_games_were_gotten)
        
        # We will do this on the seperate item in the case the bot gets bigger
        # and uses it in other ways. That way we will not get as much overhead.
        #icsbot['moves'].register('loaded', self.store_info)
        
        icsbot.reg_tell('play', self.play, lambda usr, tags: usr['rowid'])
        icsbot.reg_tell('grab', self.grab, lambda usr, tags: usr['admin'])
        icsbot.reg_tell('reload', self.reload_games, lambda usr, tags: usr['admin'])
        icsbot.reg_tell('pending', self.pending_command)        
        icsbot.reg_tell('games', self.list_games)

        self.announce_times = list(announce_times)
        self.announce_times.sort()
        self.announce_channel = announce_channel
        
        # Careful using return here, everything below this would not work.
        l = list(time.localtime())
        l[5:] = [0]*4
        for i, m in enumerate(announce_times):
            if m > l[4]:
                l[4] = m
                self.icsbot.timer(time.mktime(l), self.announce, i)
                return
                
        l[4] = announce_times[0]
        self.icsbot.timer(time.mktime(l), self.announce, 0)
        
        
    def announce(self, time_idx):
        # copied from list_games:
        g_r = []
        for g in self.games.to_end:
            if g['gamenumber']:
                # We sort them by gamenumber for lack of something better:
                g_r.append(g)
        
        if len(g_r) == 0:
            return
        g_r.sort(lambda x, y: x['gamenumber']<y['gamenumber'])
        
        for g in g_r:
            self.icsbot.send('tell %s Game: %s vs. %s in the %s round %s running. "observe %s"' % (self.announce_channel, g['white'], g['black'], g['tourney'], g['round'], g['gamenumber']))
        
        next = (time_idx + 1) % len(self.announce_times)
        l = list(time.localtime())
        if l[4] < self.announce_times[next]:
            l[4] = self.announce_times[next]
        else:
            l[4] = self.announce_times[next] + 60
        
        l[5:] = [0]*4
        self.icsbot.timer(time.mktime(l), self.announce, next)
    
    def pending(self):
        """Iterator over all pending games. Fetches them from the database.
        """
        self.games.sql.cursor.execute('SELECT rowid FROM games WHERE result="-" or result="ADJ" or result="*"')
        pending = self.games.sql.cursor.fetchall()
        for spam in pending:
            yield self.games[spam[0]] 
        

    def grab(self, user, args, tags):
        """Grab a games move/result when it was not grabbed automatically.
        This command is not finished at the moment, as it will not set the
        result to * itself, and can thus only print games that were seen
        starting. The argument must be a correct input for FICS smoves command.
        
        EXAMPLE:
            o grab 123 seberg -1
        """
        try: game_id, args = args.split(None, 1)
        except: return self.icsbot.qtell.split(user, 'USAGE: grab game_id <FICS game identifier for smoves command>, see help.')
        try: game_id = int(game_id)
        except: return self.icsbot.qtell.split(user, 'USAGE: grab game_id <FICS game identifier for smoves command>, game_id must be an Integer.')
        
        if not self.games[game_id]:
            return self.icsbot.qtell.split(user, 'Invalid game identification number, please check the database.')
        
        game = self.games[game_id]
        
        # reload, in case of change in the database.
        game.load('rowid')
        if game not in self.games.to_end:
            self.games.to_end.add('game')
        
        moves = self.icsbot['moves']['smoves %s -1' % game['white']]
        moves['__games_should_be'] = game
        moves['__games_try'] = None
        moves['__games_initiator'] = user
        moves.register('loaded', self.store_info)
        moves.load('loaded')
        return self.icsbot.qtell.split(user, 'Grabbing game from FICS command "smoves %s" if possible.' % args)
  
  
    def reload_games(self, usr, args, tags):
        """Reload
        ======
        This command will reload all games data in the bot, making sure that
        there is no bogus data.
        """
        # Lets recreate the list of games that should be ending:
        self.games.sql.cursor.execute('SELECT rowid FROM games WHERE result="*" or result="ADJ"')
        to_end = games.sql.cursor.fetchall()
        self.games.to_end = set()
        for spam in to_end:
            self.games.to_end.add(games[spam[0]])
        
        # Now, lets force a reload on all stored items:
        for g in self.games.itervalues():
            g.load('rowid')
        
        # At this point, the only thing that still can be bogus is the list of
        # games to start. Lets just check if there is none there that should
        # be finished already:
        for g_s in self.to_start.copy():
            if g_s['result'] != '*' or g_s['result'] != '-' or g_s['result'] != 'ADJ':
                self.to_start.remove(g_s)
        
        
    
    def pending_command(self, usr, args, tags):
        """Pending
        ======
        This command allows you to view pending games of yourself or a user.
        Also you can use -t tourney_name if you want all games from that tourney
        
        EXAMPLES:
            o pending -> your pending games
            o pending seberg -> seberg's pending games
            o pending -t test -> pending games for tourney test 
        """
        args = parse(args)

        if args[1].has_key('t') and len(args[1]['t']) > 0:
            tourn = args[1]['t'][0]
        else:
            tourn = None

        if args[0]:
            user = self.icsbot['users'][args[0][0]]
            if not user['rowid']:
                return self.icsbot.qtell.split(usr, 'The user %s is not registered with me.' % user['handle'])
        else:
            if not usr['rowid'] and not tourn:
                return self.icsbot.qtell.split(usr, 'As you are not registered with me, you must give a handle or a tourney.')
            user = usr
        
        if not tourn:
            self.games.sql.dcursor.execute('SELECT rowid FROM games WHERE (white_id=? or black_id=?) and (result="-" or result="*" or result="ADJ")', (user['rowid'],user['rowid']))
            gs = self.games.sql.dcursor.fetchall()
            if not gs:
                return self.icsbot.qtell.split(usr, '%s has no unifinished games.' % user['handle'])
            else:
                to_send = ['Unfinished games of %s:' % user['handle']]
        
        else:
            self.games.sql.dcursor.execute('SELECT rowid, * FROM tourneys WHERE name=?', (tourn,))
            tourney = self.games.sql.dcursor.fetchall()
            if len(tourney) == 0:
                return self.icsbot.qtell.split(usr, 'The tourney "%s" does not exist.' % tourn)
            elif len(tourney) > 1:
                return self.icsbot.qtell.split(usr, 'More then one tourney matches. This _should_ be impossible.')
        
            tourney = tourney[0]
            self.games.sql.dcursor.execute('SELECT rowid FROM games WHERE tourney_id=? and (result="-" or result="*")', (tourney['rowid'],))
            gs = self.games.sql.dcursor.fetchall()
            if not gs:
                return self.icsbot.qtell.split(usr, 'There are no unifinished games in tourney %s.' % tourney['name'])
            else:
                to_send = ['Unfinished in tourney %s:' % tourney['name']]
  
        to_send.append('+---------+-------------------+-------------------+-------+---------+')
        to_send.append('| Tourney |             white | black             | Round |  Result |')
        to_send.append('+---------+-------------------+-------------------+-------+---------+')
        for g in gs:
            # Yes, this does do some more SQLs then necessary :).
            g = self.games[g['rowid']]
            to_send.append('| %7s | %17s | %-17s | %5s | %s |' % (g['tourney'], g['white'], g['black'], g['round'], g['result'].center(7)))
        to_send.append('+---------+-------------------+-------------------+-------+---------+')
        return self.icsbot.qtell.send_list(usr, to_send)
        

    def list_games(self, usr, args, tags):
        g_r = []
        for g in self.games.to_end:
            if g['gamenumber']:
                g_r.append(g)
        
        if len(g_r) == 0:
            return self.icsbot.qtell.split(usr, 'There are currently no games in progress.')
        
        # We sort them by gamenumber for lack of something better:
        g_r.sort(lambda x, y: x['gamenumber']<y['gamenumber'])
        
        to_send = ['All games in progress:']
        to_send.append('+------+---------+-------------------+-------------------+-------+')
        to_send.append('| Game | Tourney |             white | black             | Round |')
        to_send.append('+------+---------+-------------------+-------------------+-------+')
        for g in g_r:
            to_send.append('| %4s | %7s | %17s | %-17s | %5s |' % (g['gamenumber'], g['tourney'], g['white'], g['black'], g['round']))
        to_send.append('+------+---------+-------------------+-------------------+-------+')
        return self.icsbot.qtell.send_list(usr, to_send)

  
    def play(self, user, args, tags):
        """play [tourney] [-o opponent] [-r round]
        Ask the bot to issue a match command for you and start looking for the
        game to start. This commands assumes the first game that fits to be
        the right game.
        EXAMPLES:
            o play
            o play test
            o play -o seberg
            o play test -o seberg -r 2
        -t and -r can be given in any order at any point.        
        """
        args = parse(args)
        if args[0]:
            tourney = args[0][0]
        else:
            tourney = None
        if args[1].has_key('o') and len(args[1]['o']) > 0:
            opp_handle = args[1]['o'][0].lower()
        else:
            opp_handle = None
        if args[1].has_key('r') and len(args[1]['r']) > 0:
            try: round_ = int(args[1]['r'][0])
            except: return self.icsbot.qtell.split(usr, 'Round must be an integer.')
        else:
            round_ = None
        
        handle_n = user['handle']
        handle = handle_n.lower()
        for g_p in self.pending():
            if g_p['white'].lower() == handle or g_p['black'].lower() == handle:
                if tourney and tourney.lower() != g_p['tourney'].lower():
                    continue
                
                if round_ is not None and round_ != g_p['round']:
                    continue
                
                if opp_handle is not None and (g_p['white'].lower() != opp_handle and g_p['black'].lower() != opp_handle):
                    continue
                
                if g_p['black'].lower() == handle:
                    if not self.icsbot['users'][g_p['white']]['online']:
                        return self.icsbot.qtell.split(user, 'Your opponent %s for the game in the tourney "%s" appears not to be online.' % (g_p['white'], g_p['tourney']))
                    l = [g_p['black'], g_p['white'], g_p['controls'], 'black']
                else:
                    if not self.icsbot['users'][g_p['black']]['online']:
                        return self.icsbot.qtell.split(user, 'Your opponent %s for the game in the tourney "%s" appears not to be online.' % (g_p['black'], g_p['tourney']))
                    l = [g_p['white'], g_p['black'], g_p['controls'], 'white']

                if opp_handle and opp_handle.lower() != l[1].lower():
                    continue
                
                if not ' r' in l[2] or ' u' in l[2]:
                    l[2] = l[2] + ' r'
                
                if self.no_td:
                    self.icsbot.send('tell %s Please "match %s %s %s"' % tuple(l))
                else:
                    self.icsbot.send('rmatch %s %s %s %s' % tuple(l))
                opponent = self.icsbot['users'][l[1]]
                self.icsbot.send(self.icsbot.qtell.split(opponent, 'You have recieved a match request for your game in the %s against %s, please accept or decline it.' % (g_p['tourney'], handle_n)))
                self.icsbot.send(self.icsbot.qtell.split(user, 'A match request for your game in the %s against %s has been send. If this is the wrong game, please withdraw the match request and use: play tourney_name or play -o opponent' % (g_p['tourney'], handle_n)))     
                self.games.to_start.add(g_p)
                return
        return self.icsbot.qtell.split(user, 'I have not found a game to start for you.')
        

    def result_change(self, game, item, old, new):
        # Remove the game if needed:
        if old == '-':
            self.games.to_start.remove(game)
        elif old == 'ADJ' or old == '*':
            self.games.to_end.remove(game)
            
        if new == '-':
            game['gamenumber'] = None
        elif new == 'ADJ':
            game['gamenumber'] = None
            self.games.to_end.add(game)
        elif new == '*':
            self.games.to_end.add(game)

    def game_might_run(self, game, item, old, new):
        if not game['start_time']:
            self.game_start(game, already_running=True)
            
            
    def game_start(self, game, *args, **kwargs):
        # Just for added features:
        if kwargs.has_key('already_running'):
            already_running = kwargs['already_running']
        else:
            already_running = False
            
        to_remove = set()
        for g_s in self.games.to_start:                                 
            if g_s['white'].lower() == game['white'].lower() and g_s['black'].lower() == game['black'].lower():
                # Store the gamenumber (before the result is set, so that
                # an even for the result set to * can access it):
                g_s['gamenumber'] = game['game']
                
                g_s['result'] = '*' # There is some magic here if the result
                                    # was not already * because result_change
                                    # gets executed.
                self.icsbot.send(['tell %s Good luck in your game, the start has been noted.' % game['white'], 'tell %s Good luck in your game, the start has been noted.' % game['black']])
                if self.announce_channel is not None:
                    self.icsbot.send('tell %s Game started: %s vs. %s in the %s round %s. "observe %s"' % (self.announce_channel, g_s['white'], g_s['black'], g_s['tourney'], g_s['round'], g_s['gamenumber']))
                return
            
            # There is a chance, that we are waiting for it to start, but the players won't start at all:
            elif g_s['white'].lower() == game['white'].lower() and g_s['black'].lower() == game['white'].lower()\
               or g_s['white'].lower() == game['black'].lower() and g_s['black'].lower() == game['black'].lower():
                to_remove.add(g_s)
            
            for g in to_remove:
                self.games.to_start.remove(g)
            
    
        # Now, if the game was not one that we wanted to see starting, there
        # is a chance we are waiting for it to end. This might be if it got
        # adjourned before, or if we lost connection ourselfes.
        for g_e in self.games.to_end:
            if g_e['gamenumber'] is not None:
                continue
            if g_e['white'].lower() == game['white'].lower() and g_e['black'].lower() == game['black'].lower():
                # No announce, the game might have been running for a while.
                g_e['gamenumber'] = game['game']
                g_e['result'] = '*'
                self.icsbot.send(['tell %s Good luck in your game, the start has been noted.' % game['white'], 'tell %s Good luck in your game, the start has been noted.' % game['black']])
                if self.announce_channel is not None:
                    self.icsbot.send('tell %s Game started: %s vs. %s in the %s round %s. "observe %s"' % (self.announce_channel, g_e['white'], g_e['black'], g_e['tourney'], g_e['round'], g_e['gamenumber']))
                return
    
    
    def game_end(self, game, item, old, new):
        # We could save this loop here by registering with the game only, but
        # I don't feel like changing this right now. There is no performance
        # trouble anyways.
        for g_e in self.games.to_end:
            if g_e['white'].lower() == game['white'].lower() and g_e['black'].lower() == game['black'].lower():
                # We do not yet store the information. We will get the information with moves with the
                # moves command first. We store the result only there.
                result = game['result']
                if result == '*':
                    if 'adjourned' in game['longresult']:
                        result = 'ADJ'
                        g_e['result'] = 'ADJ'
                    else:
                        result = '-'
                        g_e['result'] = '-'
                        
                # We put it here because we want it to also work on aborts, as well as not on just game sets.
                self.icsbot.send(['tell %s The game end was noted.' % g_e['white'], 'tell %s The game end was noted.' % g_e['black']])
                if self.announce_channel is not None:
                    self.icsbot.send('tell %s Game: %s vs. %s in the %s round %s ended as %s' % (self.announce_channel, g_e['white'], g_e['black'], g_e['tourney'], g_e['round'], result))
                
                # No need to grab something then:
                if g_e['result'] == '-' or g_e['result'] == 'ADJ':
                    return

                moves = self.icsbot['moves']['smoves %s -1' % game['white']]
                moves['__games_should_be'] = g_e
                moves['__games_try'] = ('w', -1)
                moves.register('loaded', self.store_info)
                moves.load('loaded')
                return
    
    
    def all_games_were_gotten(self, status, item, old, new):
        if new == True:
            for g_e in self.games.to_end:
                if not g_e['gamenumber'] and g_e['result'] == '*':
                    print 'Warning: Appearently game %s ended while I was not there. Attempting to grab from the players history games. If it did not work, you will have to use the grab command on this game ID, or insert move/result manually. There will/should be a second warning if it failed though.' % g_e['rowid']
                    moves = self.icsbot['moves']['smoves %s -1' % g_e['white']]
                    moves['__games_should_be'] = g_e
                    moves['__games_try'] = ('w', -1)
                    moves.register('loaded', self.store_info)
                    moves.load('loaded')
                    
    
    def store_info(self, moves, item, old, new):
        g_e = moves['__games_should_be']
        del moves['__games_should_be']
        # First check, because history game _might_ not exist.
        if moves['white'] is not None and g_e['white'].lower() == moves['white'].lower() and g_e['black'].lower() == moves['black'].lower():
            g_e['result'] = moves['result']
            g_e['longresult'] = moves['longresult']
            g_e['moves'] = ' '.join(moves['moves'])
            g_e['times'] = ' '.join([str(m) for m in moves['times']])
            g_e['wrating'] = moves['wrating']
            g_e['brating'] = moves['brating']
            g_e['start_time'] = str(moves['start_time'])
            del moves['__games_try']
            if moves['__games_initiator']:
                return self.icsbot.qtell.split(moves['__games_initiator'], 'Game fetching appearently successfull.')
            return
        else:
            if moves['__games_initiator']:
                return self.icsbot.qtell.split(moves['__games_initiator'], 'Game fetching FAILED.')
            if moves['__games_try'] != ('b', -10):
                if moves['__games_try'][0] == 'w':
                    new = ('b', moves['__games_try'][1])
                    del moves['__games_try']
                    moves = self.icsbot['moves']['smoves %s %s' % (g_e['black'], new[1])]
                    moves['__games_should_be'] = g_e
                    moves['__games_try'] = new
                    moves.register('loaded', self.store_info)
                    moves.load('loaded')
                else:
                    new = ('w', moves['__games_try'][1]-1)
                    del moves['__games_try']
                    moves = self.icsbot['moves']['smoves %s %s' % (g_e['white'], new[1])]
                    moves['__games_should_be'] = g_e
                    moves['__games_try'] = new
                    moves.register('loaded', self.store_info)
                    moves.load('loaded')
            else:
                print 'Warning: game saving attempt for game %s failed. You should have a look at unfinished games.' % g_e['rowid']
