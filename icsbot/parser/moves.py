"""
This Moves class provides parsing and saving for the moves/smoves command.
For this it defines/gets the icsbot['moves'] dataset.
"""

import re, time

import icsbot.misc.regex as reg

import datetime

class Moves(object):
    """
    This class defines the 'moves' dataset. When a moves/smoves command is
    issued, it does the following (so not all is catched atm):
        o Adds the item to the moves Dataset handle is just a number ...
        o Adds Move['white'] and Move['black'] as the handles.
        o Adds Move['longresult'] = 'black resignes' and Move['result'] = '1-0'
        o Adds Move['moves'] = ['e4', 'e5', ...]
        o Adds Move['times'] = [seconds, seconds, ...] corresponding times.
        o Adds Move['gamenumber'] = gamenumber or None if it was smoves and
           False if we got nothing.
        o Adds Move['loaded'] = time_in_epoch so you can register this!
           (And you should register to _only_ this and load it for update).
        o Adds Move['rated'] = True | False
        o Adds Move['type'] = wild/fr, standard, etc. (as in moves output)
        o Adds Move['time'] and move['inc'] as integers.
        o Adds Move['wrating'] and Move['brating'], the ratings at the start
           of the game.
        o Adds Move['start_time'] a datetime.datetime object.
    
    NOTE:
        o If you want to get an item, you must create the moves item
           that is named like the command to send. IE.
           do icsbot['moves']['smoves seberg -1'].load('loaded')
        o No sanity checks, but if I parse a moves and there is nothing
           pending, I just drop it. (well, just VERY basic warnings. just don't
           give the module anything that might not return a good result ;)).
           This also means that you should always use gamenumbers with move,
           because then I DO get a warning from the server.
    """
    
    def __init__(self, icsbot, trigger_duplicate=True):
        regex = re.compile('^(?:Movelist for game (?P<gamenumber>\d+):)?\s*(?P<white>%s) \((?P<wrating>(\d+|UNR))\) vs. (?P<black>%s) \((?P<brating>(\d+|UNR))\) --- (?P<start_time>[^\n]+)\n\r(?P<rated>(Unrated|Rated)) (?P<variant>[^ ]+) match, initial time: (?P<time>\d+) minutes, increment: (?P<inc>\d+) seconds\.\s*\n\rMove [A-z ]+\n\r[- ]+\n\r(?P<data>[^{]+)\{(?P<longresult>[^}]*)\} (?P<result>[^ \n\r]*)' % (reg.HANDLE, reg.HANDLE), re.DOTALL)
        self._icsbot = icsbot
        self._icsbot.send('iset movecase 1')
        self._icsbot.send('iset ms 1')
        self._icsbot.send('set tzone gmt')
        
        self._moves = self._icsbot['moves']
        self._to_grep = []
        
        self.MOVE_REG = re.compile('([a-hBNKQPRx@+#=1-8O-]+)\s+\((\d+):(\d+.\d+)\)')
        
        self._icsbot.reg_comm(regex, self)
        self._icsbot.reg_comm('There is no such game.', self.no_game)
        self._icsbot.reg_comm(re.compile('(?P<player>%s) has no history games.' % reg.HANDLE), self.no_game)
        self._icsbot.reg_comm(re.compile(r"There are only \d+ entries in (?P<player>%s)'s history." % reg.HANDLE), self.no_game)
        self._icsbot['moves'].register('loaded', self.to_load, loader=True)
        
        self.trigger_duplicate = trigger_duplicate
    

    def to_load(self, moves, spam):
        self._to_grep.append(moves)
        self._icsbot.send(moves['handle'])
        

    def __call__(self, matches):
        if len(self._to_grep)==0:
            return
        d = matches.groupdict()
              
        if d['gamenumber'] is not None:
            if len(self._to_grep[0]['handle'].split()) == 2:
                d['gamenumber'] = int(d['gamenumber'])
            else:
                print 'WARNING: I was expecting a list for a running game and got one for a finished. This might result it further wrong fetching!'
        
        else:
            if len(self._to_grep[0]['handle'].split()) == 2:
                print 'WARNING: I was expecting a list for a stored game and got one for a running. This might result it further wrong fetching!'
        
        if d['rated'] == 'Rated':
            d['rated'] = True
        else:
            d['rated'] = False
        
        d['time'] = int(d['time'])
        d['inc']  = int(d['inc'])
    
        try:
            d['start_time'] = datetime.datetime.strptime(d['start_time'], '%a %b %d, %H:%M GMT %Y')
        except:
            print 'The timezone of this account is not set to GMT, I need GMT for datetime.datetime'
        
        # Would use one liner ifs, but 2.4 compatibility ...        
        if d['wrating'] == 'UNR':
            d['wrating'] = None
        else:
            d['wrating'] = int(d['wrating'])

        if d['brating'] == 'UNR':
            d['brating'] = None
        else:
            d['brating'] = int(d['brating'])
        
        data = d['data']
        del d['data']
        
        d['moves'] = []
        d['times'] = []
        
        data = self.MOVE_REG.findall(data)
        for mov in data:
            d['moves'] += [mov[0]]
            d['times'] += [float(mov[1])*60+float(mov[2])]


        if not self.trigger_duplicate:
            if self._to_grep[0]['moves'] == d['moves'] and self._to_grep[0]['start_time'] == d['start_time']:
                print 'Debug notice game gotten through %s gotten double.' % self._to_grep[0]['handle']
                # It appears to be a dupe, and won't update.
                del self._to_grep[0]
                return
            
        self._to_grep[0].items.update(d)
        self._to_grep[0]['loaded'] = time.time()
        del self._to_grep[0]
    
    
    def no_game(self, matches):
        if len(self._to_grep)==0:
            return
        else:
            print 'There was an error accessing a history or going on moves list. For "%s". Matches were:' % self._to_grep[0]['handle'], matches.groups()
            print 
            self._to_grep[0]['gamenumber'] = False
            self._to_grep[0]['loaded'] = time.time()
            del self._to_grep[0]

