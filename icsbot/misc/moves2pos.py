try:
    _
except NameError:
    import gettext
    gettext.install('icsbot')

from ..thirdparty.pychess.Utils.Board import Board
from ..thirdparty.pychess.Utils.Move import parseSAN

"""This is a wrapper around pychess's Board/Move represenations. This wrapper
only supports chess as is.

Please note, this wrapper installes gettext into the __buildint__ namespace
if it does not yet exist, to be able to import pychess correctly.
"""


def moves2pos(moves):
    """Return a list of positions from a SAN move list (as used by icsbot).
    This includes the starting position.
    """
    boards = [Board(True)]
    for move in moves:
        move = parseSAN(boards[-1], move)
        boards.append(boards[-1].move(move))
    
    return boards


def moves2fen(moves):
    """Return a list of fens position from SAN move list.
    """
    boards = moves2pos(moves)
    return [board.asFen() for board in boards]
