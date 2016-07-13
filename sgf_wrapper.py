'''
Code to extract a series of positions + their next moves from an SGF.

Most of the complexity here is dealing with two features of SGF:
- Stones can be added via "play move" or "add move", the latter being used
  to configure L+D puzzles, but also for initial handicap placement.
- Plays don't necessarily alternate colors; they can be repeated B or W moves
  This feature is used to handle free handicap placement.

Since our Go position data structure flips all colors based on whose turn it is
we have to look ahead at next move to correctly create a position.
'''
from collections import namedtuple

import go
from go import Position, place_stone, deduce_groups
from utils import parse_sgf_coords as pc
import sgf

def sgf_prop(value_list):
    'Converts raw sgf library output to sensible value'
    if value_list is None:
        return None
    if len(value_list) == 1:
        return value_list[0]
    else:
        return value_list

# SGFs have a notion of "add stones" and "play stones".
# Add stones can have arbitrary numbers of either color stone, and is used
# to set up L+D puzzles or handicap stones.
# SGF spec says that you shouldn't resolve captures in an add stone node.
def handle_add_stones(pos, node):
    black_stones_added = node.properties.get('AB', [])
    white_stones_added = node.properties.get('AW', [])
    working_board = pos.board
    for b in black_stones_added:
        working_board = place_stone(working_board, 1, pc(b))
    for w in white_stones_added:
        working_board = place_stone(working_board, -1, pc(w))
    if black_stones_added or white_stones_added:
        return pos._replace(board=working_board, groups=deduce_groups(working_board))
    else:
        return pos

def get_next_move(node):
    if not node.next:
        return None, None
    props = node.next.properties
    if 'W' in props:
        return 'W', props['W'][0] or None
    else:
        return 'B', props['B'][0] or None

# Play stones should have just 1 stone. Play is not necessarily alternating;
# sometimes B plays repeatedly at the start in free handicap placement.
# Must look at next node to figure out who was "supposed" to have played.
def handle_play_stones(pos, node):
    props = node.properties
    if 'W' in props:
        pos = pos.play_move(pc(props['W'][0]))
    elif 'B' in props:
        pos = pos.play_move(pc(props['B'][0]))
    next_player, _ = get_next_move(node)
    if next_player == 'W' and pos.player1turn:
        pos = pos._replace(player1turn=False)
    elif next_player == 'B' and not pos.player1turn:
        pos = pos._replace(player1turn=True)
    return pos

class SgfWrapper(object):
    '''
    Wrapper for sgf files, exposing contents as go.Position instances
    with open(filename) as f:
        sgf = sgf_wrapper.SgfWrapper(f.read())
        for position, move, result in sgf.get_main_branch():
            print(position)
    '''

    def __init__(self, file_contents):
        self.collection = sgf.parse(file_contents)
        self.game = self.collection.children[0]
        props = self.game.root.properties
        assert int(sgf_prop(props.get('GM', ['1']))) == 1, "Not a Go SGF!"
        self.result = sgf_prop(props.get('RE'))
        self.komi = float(sgf_prop(props.get('KM')))
        self.board_size = int(sgf_prop(props.get('SZ')))
        go.set_board_size(self.board_size)

    def get_main_branch(self):
        pos = Position.initial_state()
        pos = pos._replace(komi=self.komi)
        current_node = self.game.root
        while pos is not None and current_node is not None:
            pos = handle_add_stones(pos, current_node)
            pos = handle_play_stones(pos, current_node)
            _, next_move = get_next_move(current_node)
            current_node = current_node.next
            yield PositionWithContext(pos, next_move, self.result)

class PositionWithContext(namedtuple("SgfPosition", "position next_move result")):
    '''
    Wrapper around go.Position.
    Stores a position, the move that came next, and the eventual result.
    '''
    def is_usable(self):
        return self.position is not None and self.next_move is not None and self.result != "Void"

    def __str__(self):
        return str(self.position) + '\nNext move: {} Result: {}'.format(self.next_move, self.result)
