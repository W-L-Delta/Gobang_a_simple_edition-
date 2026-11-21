"""14x14 Gomoku / Renju rules and AI engine for the desktop app.

Performance notes
-----------------
The rules used to be evaluated by rebuilding a Python list of the whole run for
every direction of every candidate point.  On a 14x14 board with an
alpha-beta search that ran that check thousands of times per second, the list
building (and the ``in_bounds`` / ``row_of`` / ``col_of`` calls around it)
dominated the profile.

This version keeps exactly the same public API and the same rule semantics,
but replaces the hot paths with precomputed tables:

* ``POS`` / ``NEG`` / ``NEXT`` / ``PREV`` are ready-made direction rays, so a
  win check is a tight loop over valid board indices (no bounds arithmetic).
* ``_line_len`` stops at 6 stones, which is enough to distinguish exactly-five
  from an overline.
* ``is_legal_move`` first runs a *conservative* gate: a double-four needs three
  friendly stones within four cells of the point, and a double-three needs two
  different directions with two friendly stones within three cells.  Most
  candidate points fail both tests and are answered without any recursion.
* The search keeps an incremental neighbour count for candidate generation and
  an incremental set of "winning points" per player, so the tactical check that
  used to scan every candidate is O(1) and stays exact.
* Iterative deepening under a wall-clock budget, a Zobrist transposition table
  and the cheap point score provide better move ordering in the same time.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass

SIZE = 14
CELLS = SIZE * SIZE
EMPTY = 0
BLACK = 1
WHITE = 2
WIN_SCORE = 1_000_000_000
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))
DIR_INDEX = {direction: index for index, direction in enumerate(DIRECTIONS)}
HARD_MAX_DEPTH = 8
HARD_TIME_LIMIT = 1.15
HARD_ROOT_WIDTH = 10

CENTER_POINTS = (
    6 * SIZE + 6,
    6 * SIZE + 7,
    7 * SIZE + 6,
    7 * SIZE + 7,
)

FORBIDDEN_LABELS = {
    "overline": "长连",
    "doubleFour": "四四",
    "doubleThree": "三三",
}

DIFFICULTIES = {
    "easy": {"label": "简单", "tagline": "轻松热身"},
    "medium": {"label": "中等", "tagline": "认真对弈"},
    "hard": {"label": "困难", "tagline": "步步紧逼"},
}

PATTERN_GROUPS = (
    ("five", r"11111"),
    ("openFour", r"011110"),
    ("four", r"11110|01111|11011|10111|11101"),
    ("openThree", r"01110|010110|011010"),
    ("three", r"11100|00111|11010|01011|10110|01101|10011|11001|10101"),
    ("openTwo", r"001100|011000|000110|010100|001010|010010"),
    ("two", r"11000|00011|10100|00101|10010|01001"),
)
PATTERN_REGEXES = tuple((key, re.compile(source)) for key, source in PATTERN_GROUPS)


# ---------------------------------------------------------------------------
# Precomputed tables
# ---------------------------------------------------------------------------


def _build_tables():
    rows = tuple(index // SIZE for index in range(CELLS))
    cols = tuple(index % SIZE for index in range(CELLS))
    pos = []
    neg = []
    nxt = []
    prv = []
    for dr, dc in DIRECTIONS:
        pos_d = []
        neg_d = []
        nxt_d = []
        prv_d = []
        for index in range(CELLS):
            row = rows[index]
            col = cols[index]
            forward = []
            backward = []
            for step in range(1, SIZE):
                r = row + dr * step
                c = col + dc * step
                if not (0 <= r < SIZE and 0 <= c < SIZE):
                    break
                forward.append(r * SIZE + c)
            for step in range(1, SIZE):
                r = row - dr * step
                c = col - dc * step
                if not (0 <= r < SIZE and 0 <= c < SIZE):
                    break
                backward.append(r * SIZE + c)
            pos_d.append(tuple(forward))
            neg_d.append(tuple(backward))

            r, c = row + dr, col + dc
            nxt_d.append(r * SIZE + c if 0 <= r < SIZE and 0 <= c < SIZE else -1)
            r, c = row - dr, col - dc
            prv_d.append(r * SIZE + c if 0 <= r < SIZE and 0 <= c < SIZE else -1)
        pos.append(tuple(pos_d))
        neg.append(tuple(neg_d))
        nxt.append(tuple(nxt_d))
        prv.append(tuple(prv_d))

    # 11-cell windows (steps -5..5) used by the pattern classifier.
    windows = []
    for dr, dc in DIRECTIONS:
        window_d = []
        for index in range(CELLS):
            row = rows[index]
            col = cols[index]
            cells = []
            for step in range(-5, 6):
                r = row + dr * step
                c = col + dc * step
                cells.append(r * SIZE + c if 0 <= r < SIZE and 0 <= c < SIZE else -1)
            window_d.append(tuple(cells))
        windows.append(tuple(window_d))

    # Short rays: POS3/POS4 are the first 3/4 steps of POS.
    pos3 = tuple(tuple(cell[:3] for cell in direction) for direction in pos)
    neg3 = tuple(tuple(cell[:3] for cell in direction) for direction in neg)
    pos4 = tuple(tuple(cell[:4] for cell in direction) for direction in pos)
    neg4 = tuple(tuple(cell[:4] for cell in direction) for direction in neg)
    return rows, cols, pos, neg, nxt, prv, windows, pos3, neg3, pos4, neg4


(
    ROWS,
    COLS,
    POS,
    NEG,
    NEXT,
    PREV,
    WINDOW,
    POS3,
    NEG3,
    POS4,
    NEG4,
) = _build_tables()


def _build_neighbors(radius: int):
    table = []
    for index in range(CELLS):
        row = ROWS[index]
        col = COLS[index]
        cells = []
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                if dr == 0 and dc == 0:
                    continue
                r = row + dr
                c = col + dc
                if 0 <= r < SIZE and 0 <= c < SIZE:
                    cells.append(r * SIZE + c)
        table.append(tuple(cells))
    return tuple(table)


NEIGHBORS = {1: _build_neighbors(1), 2: _build_neighbors(2)}
NEIGHBOR2 = NEIGHBORS[2]

BASE_POINT_SCORE = (0, 1, 12, 160, 6_000, 1_000_000)
OPEN_MULTIPLIER = (0.12, 1.0, 2.2)
POINT_VALUE = tuple(
    tuple(int(base * multiplier) for base in BASE_POINT_SCORE)
    for multiplier in OPEN_MULTIPLIER
)

# Zobrist keys for the transposition table.  A fixed seed keeps searches
# reproducible between runs (the AI's random tie-breaking is the only source
# of variation).
_ZOBRIST_RNG = random.Random(0x5EED_2024)
ZOBRIST = tuple(
    (0, _ZOBRIST_RNG.getrandbits(64), _ZOBRIST_RNG.getrandbits(64))
    for _ in range(CELLS)
)
TURN_KEY = _ZOBRIST_RNG.getrandbits(64)

TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2


def _build_lines():
    entries = []

    def add(cells, direction):
        if len(cells) >= 5:
            entries.append((tuple(cells), direction))

    for r in range(SIZE):
        add([r * SIZE + c for c in range(SIZE)], 0)
    for c in range(SIZE):
        add([r * SIZE + c for r in range(SIZE)], 1)
    for c in range(SIZE):
        cells = []
        r, cc = 0, c
        while r < SIZE and cc < SIZE:
            cells.append(r * SIZE + cc)
            r += 1
            cc += 1
        add(cells, 2)
    for r in range(1, SIZE):
        cells = []
        rr, c = r, 0
        while rr < SIZE and c < SIZE:
            cells.append(rr * SIZE + c)
            rr += 1
            c += 1
        add(cells, 2)
    for c in range(SIZE):
        cells = []
        r, cc = 0, c
        while r < SIZE and cc >= 0:
            cells.append(r * SIZE + cc)
            r += 1
            cc -= 1
        add(cells, 3)
    for r in range(1, SIZE):
        cells = []
        rr, c = r, SIZE - 1
        while rr < SIZE and c >= 0:
            cells.append(rr * SIZE + c)
            rr += 1
            c -= 1
        add(cells, 3)
    return tuple(entries)


LINE_ENTRIES = _build_lines()
LINES = tuple(cells for cells, _direction in LINE_ENTRIES)
LINE_DIR = tuple(direction for _cells, direction in LINE_ENTRIES)
LINE_COUNT = len(LINES)

# LINE_ID[direction][cell] -> index in LINES (-1 if the line is shorter than 5)
LINE_ID = [[-1] * CELLS for _ in range(4)]
for _line_id, (_cells, _direction) in enumerate(LINE_ENTRIES):
    for _cell in _cells:
        LINE_ID[_direction][_cell] = _line_id


def _line_win_points(board: list[int], cells: tuple[int, ...], player: int) -> set[int]:
    """Empty cells that would complete a five for ``player`` on this line."""
    values = [board[cell] for cell in cells]
    length = len(values)
    count = 0
    for index in range(5):
        if values[index] == player:
            count += 1
    points: set[int] = set()
    for start in range(length - 4):
        if start:
            if values[start + 4] == player:
                count += 1
            if values[start - 1] == player:
                count -= 1
        if count == 4:
            for offset in range(start, start + 5):
                if values[offset] == EMPTY:
                    points.add(cells[offset])
                    break
    if points:
        # A five-window can be the edge of a longer run: filling it may make a
        # six (overline) for black, which is not a win.  Verify the actual
        # five-direction rule for the few points that reached this stage.
        points = {cell for cell in points if _is_five(board, cell, player)}
    return points


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------


def other(player: int) -> int:
    return WHITE if player == BLACK else BLACK


def create_board() -> list[int]:
    return [EMPTY] * CELLS


def row_of(move: int) -> int:
    return move // SIZE


def col_of(move: int) -> int:
    return move % SIZE


def in_bounds(row: int, col: int) -> bool:
    return 0 <= row < SIZE and 0 <= col < SIZE


def board_stone_count(board: list[int]) -> int:
    return CELLS - board.count(EMPTY)


def is_board_full(board: list[int]) -> bool:
    return EMPTY not in board


# ---------------------------------------------------------------------------
# Fast line primitives
# ---------------------------------------------------------------------------


def _line_len(board: list[int], move: int, player: int, direction: int) -> int:
    """Consecutive stones through ``move`` in one direction, capped at 6.

    ``move`` is assumed to belong to ``player`` (it is either already on the
    board or about to be placed).  Capping at 6 keeps the distinction between
    an exact five and an overline while allowing an early exit.
    """
    count = 1
    for index in POS[direction][move]:
        if board[index] != player:
            break
        count += 1
        if count == 6:
            return 6
    for index in NEG[direction][move]:
        if board[index] != player:
            break
        count += 1
        if count == 6:
            return 6
    return count


def _is_five(board: list[int], move: int, player: int) -> bool:
    if player == BLACK:
        for direction in range(4):
            if _line_len(board, move, player, direction) == 5:
                return True
    else:
        for direction in range(4):
            if _line_len(board, move, player, direction) >= 5:
                return True
    return False


def _has_overline(board: list[int], move: int, player: int) -> bool:
    for direction in range(4):
        if _line_len(board, move, player, direction) >= 6:
            return True
    return False


def _build_run_at(board: list[int], move: int, player: int, dr: int, dc: int) -> list[int]:
    direction = DIR_INDEX[(dr, dc)]
    return _run(board, move, player, direction)


def _run(board: list[int], move: int, player: int, direction: int) -> list[int]:
    """Full contiguous run through ``move`` in grid order (ascending index)."""
    nxt = NEXT[direction]
    prv = PREV[direction]
    run = []
    index = prv[move]
    while index >= 0 and board[index] == player:
        run.append(index)
        index = prv[index]
    run.reverse()
    run.append(move)
    index = nxt[move]
    while index >= 0 and board[index] == player:
        run.append(index)
        index = nxt[index]
    return run


def get_runs_at(board: list[int], move: int, player: int) -> list[list[int]]:
    return [_run(board, move, player, direction) for direction in range(4)]


def winning_line_for(board: list[int], move: int, player: int) -> list[int] | None:
    if not (0 <= move < CELLS) or board[move] != player:
        return None

    best = None
    for direction in range(4):
        run = _run(board, move, player, direction)
        length = len(run)
        is_win = length == 5 if player == BLACK else length >= 5
        if is_win and (best is None or length > len(best)):
            best = run
    return best


def check_win(board: list[int], last_move: int, player: int) -> list[int] | None:
    return winning_line_for(board, last_move, player)


def would_win_at(board: list[int], move: int, player: int) -> bool:
    if not (0 <= move < CELLS):
        return False
    value = board[move]
    if value != EMPTY and value != player:
        return False
    return _is_five(board, move, player)


def has_overline_at(board: list[int], move: int, player: int) -> bool:
    return _has_overline(board, move, player)


# ---------------------------------------------------------------------------
# Four / three counting (forbidden moves)
# ---------------------------------------------------------------------------


def _is_straight_four_run(
    board: list[int], run: list[int], dr: int, dc: int, player: int
) -> bool:
    if len(run) != 4:
        return False
    direction = DIR_INDEX[(dr, dc)]
    before = PREV[direction][run[0]]
    after = NEXT[direction][run[-1]]
    if before < 0 or after < 0:
        return False
    if board[before] != EMPTY or board[after] != EMPTY:
        return False
    before_two = PREV[direction][before]
    after_two = NEXT[direction][after]
    if before_two >= 0 and board[before_two] == player:
        return False
    if after_two >= 0 and board[after_two] == player:
        return False
    return True


def count_fours_at(board: list[int], move: int, player: int) -> int:
    signatures: set[tuple[int, ...]] = set()

    for direction in range(4):
        for completion in POS4[direction][move] + NEG4[direction][move]:
            if board[completion] != EMPTY:
                continue
            board[completion] = player
            run = _run(board, completion, player, direction)
            if len(run) == 5 and move in run:
                signatures.add(tuple(cell for cell in run if cell != completion))
            board[completion] = EMPTY

    return len(signatures)


def _creates_five_or_overline(board: list[int], move: int, player: int) -> tuple[bool, bool]:
    five = False
    overline = False
    for direction in range(4):
        length = _line_len(board, move, player, direction)
        if length == 5:
            five = True
        elif length >= 6:
            overline = True
            break
    return five, overline


def count_threes_at(board: list[int], move: int, player: int) -> int:
    signatures: set[tuple[int, ...]] = set()

    for direction in range(4):
        for extension in POS4[direction][move] + NEG4[direction][move]:
            if board[extension] != EMPTY:
                continue
            board[extension] = player
            run = _run(board, extension, player, direction)
            if (
                len(run) == 4
                and move in run
                and _is_straight_four_run(board, run, *DIRECTIONS[direction], player)
            ):
                five, overline = _creates_five_or_overline(board, extension, player)
                if not five and not overline:
                    if count_fours_at(board, extension, player) < 2:
                        signatures.add(tuple(cell for cell in run if cell != extension))
            board[extension] = EMPTY

    return len(signatures)


# ---------------------------------------------------------------------------
# Move analysis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MoveAnalysis:
    move: int
    player: int
    legal: bool
    winning: bool
    forbidden: bool
    reasons: tuple[str, ...]
    win_line: tuple[int, ...] | None
    overline: bool
    fours: int
    threes: int

    @property
    def reason_text(self) -> str:
        return "、".join(FORBIDDEN_LABELS.get(reason, "禁手") for reason in self.reasons)


def analyze_move(board: list[int], move: int, player: int) -> MoveAnalysis:
    if not (0 <= move < CELLS) or board[move] != EMPTY:
        return MoveAnalysis(move, player, False, False, False, (), None, False, 0, 0)

    board[move] = player
    win_line = winning_line_for(board, move, player)

    if win_line is not None:
        result = MoveAnalysis(
            move, player, True, True, False, (), tuple(win_line), False, 0, 0
        )
    elif player == WHITE:
        result = MoveAnalysis(move, player, True, False, False, (), None, False, 0, 0)
    else:
        overline = _has_overline(board, move, player)
        fours = count_fours_at(board, move, player)
        threes = count_threes_at(board, move, player)
        reasons: list[str] = []
        if overline:
            reasons.append("overline")
        if fours >= 2:
            reasons.append("doubleFour")
        if threes >= 2:
            reasons.append("doubleThree")
        result = MoveAnalysis(
            move,
            player,
            not reasons,
            False,
            bool(reasons),
            tuple(reasons),
            None,
            overline,
            fours,
            threes,
        )

    board[move] = EMPTY
    return result


def _near_stones(
    board: list[int], move: int, player: int, direction: int, limit: int, need: int
) -> int:
    count = 0
    if limit == 4:
        rays = (POS4[direction][move], NEG4[direction][move])
    else:
        rays = (POS3[direction][move], NEG3[direction][move])
    for ray in rays:
        for index in ray:
            if board[index] == player:
                count += 1
                if count >= need:
                    return count
    return count


def _maybe_forbidden(board: list[int], move: int, player: int) -> bool:
    """Conservative gate used before the recursive four/three counting.

    A double-four needs at least one direction with three friendly stones in
    the four-cell neighbourhood; a double-three needs at least two directions
    with two friendly stones within three cells (a single direction can hold
    at most one three, verified exhaustively on an 11-cell window).
    """
    four_suspect = False
    three_directions = 0
    for direction in range(4):
        if not four_suspect and _near_stones(board, move, player, direction, 4, 3) >= 3:
            four_suspect = True
        if _near_stones(board, move, player, direction, 3, 2) >= 2:
            three_directions += 1
    if not four_suspect and three_directions < 2:
        return False
    if four_suspect and count_fours_at(board, move, player) >= 2:
        return True
    if three_directions >= 2 and count_threes_at(board, move, player) >= 2:
        return True
    return False


def is_legal_move(board: list[int], move: int, player: int) -> bool:
    if not (0 <= move < CELLS) or board[move] != EMPTY:
        return False
    if player == WHITE:
        return True

    board[move] = player
    try:
        five = False
        overline = False
        for direction in range(4):
            length = _line_len(board, move, player, direction)
            if length == 5:
                five = True
            elif length >= 6:
                overline = True
                break
        if five:
            return True
        if overline:
            return False
        return not _maybe_forbidden(board, move, player)
    finally:
        board[move] = EMPTY


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------


def get_candidates(board: list[int], radius: int = 2) -> list[int]:
    neighbors = NEIGHBORS.get(radius)
    seen = bytearray(CELLS)
    candidates: list[int] = []

    if neighbors is not None:
        stones = 0
        for move in range(CELLS):
            if board[move] == EMPTY:
                continue
            stones += 1
            for index in neighbors[move]:
                if board[index] == EMPTY and not seen[index]:
                    seen[index] = 1
                    candidates.append(index)
        if stones == 0:
            return list(CENTER_POINTS)
        return candidates

    stones = 0
    for move, value in enumerate(board):
        if value == EMPTY:
            continue
        stones += 1
        row = ROWS[move]
        col = COLS[move]
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                if dr == 0 and dc == 0:
                    continue
                r = row + dr
                c = col + dc
                if not in_bounds(r, c):
                    continue
                index = r * SIZE + c
                if board[index] == EMPTY and not seen[index]:
                    seen[index] = 1
                    candidates.append(index)

    if stones == 0:
        return list(CENTER_POINTS)
    return candidates


def immediate_winning_moves(
    board: list[int], player: int, pool=None
) -> list[int]:
    candidates = list(pool) if pool is not None else get_candidates(board)
    return [
        move
        for move in candidates
        if board[move] == EMPTY and _is_five(board, move, player)
    ]


def get_legal_moves(board: list[int], player: int, pool=None) -> list[int]:
    candidates = list(pool) if pool is not None else get_candidates(board)
    return [
        move
        for move in candidates
        if board[move] == EMPTY and is_legal_move(board, move, player)
    ]


def get_all_legal_moves(board: list[int], player: int) -> list[int]:
    return [
        move
        for move in range(CELLS)
        if board[move] == EMPTY and is_legal_move(board, move, player)
    ]


# ---------------------------------------------------------------------------
# Positional scoring
# ---------------------------------------------------------------------------


def _line_string_for(
    board: list[int], row: int, col: int, dr: int, dc: int, player: int
) -> str:
    direction = DIR_INDEX[(dr, dc)]
    move = row * SIZE + col
    chars = []
    for index in WINDOW[direction][move]:
        if index < 0:
            chars.append("2")
            continue
        value = board[index]
        chars.append("0" if value == EMPTY else "1" if value == player else "2")
    return "".join(chars)


def _classify_direction(line: str) -> str | None:
    for key, regex in PATTERN_REGEXES:
        for match in regex.finditer(line):
            if match.start() <= 5 < match.end():
                return key
    return None


def _shape_score(shapes: dict[str, int]) -> int:
    if shapes["five"] > 0:
        return WIN_SCORE

    score = 0
    if shapes["openFour"]:
        score += 7_000_000
    if shapes["four"]:
        score += 350_000 if shapes["four"] == 1 else 5_000_000
    if shapes["openThree"]:
        score += 80_000 if shapes["openThree"] == 1 else 1_700_000
    if shapes["four"] and shapes["openThree"]:
        score += 2_200_000
    score += shapes["three"] * 4_500
    score += shapes["openTwo"] * 650
    score += shapes["two"] * 55
    return score


def placement_score(board: list[int], move: int, player: int) -> int:
    board[move] = player
    shapes = {
        "five": 0,
        "openFour": 0,
        "four": 0,
        "openThree": 0,
        "three": 0,
        "openTwo": 0,
        "two": 0,
    }
    row = ROWS[move]
    col = COLS[move]
    for dr, dc in DIRECTIONS:
        line = _line_string_for(board, row, col, dr, dc, player)
        shape = _classify_direction(line)
        if shape:
            shapes[shape] += 1
    board[move] = EMPTY
    center_distance = max(abs(row - 6.5), abs(col - 6.5))
    return _shape_score(shapes) + max(0.0, 7 - center_distance) * 3


def rank_moves(board: list[int], player: int, limit: int, pool=None) -> list[int]:
    candidates = list(pool) if pool is not None else get_candidates(board)
    opponent = other(player)
    scored = []
    for move in candidates:
        attack = placement_score(board, move, player)
        defense = placement_score(board, move, opponent)
        scored.append((attack + defense * 0.88, move))
    scored.sort(reverse=True)

    if player == WHITE:
        return [move for _, move in scored[:limit]]

    legal: list[int] = []
    for _, move in scored:
        if len(legal) >= limit:
            break
        if is_legal_move(board, move, player):
            legal.append(move)
    return legal


def _quick_point_score(board: list[int], move: int, player: int) -> int:
    board[move] = player
    score = 0
    values = POINT_VALUE
    for direction in range(4):
        count = 1
        open_ends = 0

        for index in POS[direction][move]:
            value = board[index]
            if value != player:
                if value == EMPTY:
                    open_ends += 1
                break
            count += 1

        for index in NEG[direction][move]:
            value = board[index]
            if value != player:
                if value == EMPTY:
                    open_ends += 1
                break
            count += 1

        score += values[open_ends][count if count < 5 else 5]

    board[move] = EMPTY
    return score


def quick_rank_moves(board: list[int], player: int, limit: int, pool) -> list[int]:
    opponent = other(player)
    scored = []
    for move in pool:
        attack = _quick_point_score(board, move, player)
        defense = _quick_point_score(board, move, opponent)
        scored.append((attack + defense * 0.92, move))
    scored.sort(reverse=True)

    if player == WHITE:
        return [move for _, move in scored[:limit]]

    legal: list[int] = []
    check_limit = min(len(scored), limit * 4)
    for index in range(check_limit):
        move = scored[index][1]
        if is_legal_move(board, move, player):
            legal.append(move)
            if len(legal) >= limit:
                break
    return legal


# ---------------------------------------------------------------------------
# Board evaluation
# ---------------------------------------------------------------------------


def _score_stats(stats: list[int]) -> int:
    if stats[0] > 0:
        return WIN_SCORE
    score = 0
    score += stats[1] * 5_000_000
    score += stats[2] * 280_000
    score += stats[3] * 65_000
    score += stats[4] * 4_500
    score += stats[5] * 700
    score += stats[6] * 70
    if stats[2] >= 2:
        score += 3_600_000
    if stats[2] > 0 and stats[3] > 0:
        score += 1_800_000
    if stats[3] >= 2:
        score += 700_000
    return score


def evaluate_board(board: list[int], ai_player: int) -> int:
    human = other(ai_player)
    ai_stats = [0] * 7
    human_stats = [0] * 7
    b = board

    for line in LINES:
        i = 0
        length = len(line)
        while i < length:
            value = b[line[i]]
            if value == EMPTY:
                i += 1
                continue
            end = i + 1
            while end < length and b[line[end]] == value:
                end += 1
            before = b[line[i - 1]] if i > 0 else -1
            after = b[line[end]] if end < length else -1
            open_ends = (1 if before == EMPTY else 0) + (1 if after == EMPTY else 0)
            stats = ai_stats if value == ai_player else human_stats
            run_length = end - i
            if run_length >= 5:
                stats[0] += 1
            elif run_length == 4:
                if open_ends >= 2:
                    stats[1] += 1
                elif open_ends == 1:
                    stats[2] += 1
            elif run_length == 3:
                if open_ends >= 2:
                    stats[3] += 1
                elif open_ends == 1:
                    stats[4] += 1
            elif run_length == 2:
                if open_ends >= 2:
                    stats[5] += 1
                elif open_ends == 1:
                    stats[6] += 1
            i = end

    return _score_stats(ai_stats) - int(_score_stats(human_stats) * 1.08)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class _SearchContext:
    __slots__ = (
        "board",
        "neighbors",
        "ai",
        "deadline",
        "cancel",
        "stopped",
        "nodes",
        "hash",
        "table",
        "win_counts",
        "win_sets",
        "line_wins",
    )

    def __init__(self, board: list[int], ai_player: int, deadline: float, cancel=None):
        self.board = board
        self.ai = ai_player
        self.deadline = deadline
        self.cancel = cancel
        self.stopped = False
        self.nodes = 0
        counts = [0] * CELLS
        position_hash = 0
        for move in range(CELLS):
            value = board[move]
            if value != EMPTY:
                position_hash ^= ZOBRIST[move][value]
                for index in NEIGHBOR2[move]:
                    counts[index] += 1
        self.hash = position_hash
        self.neighbors = counts
        self.table: dict[int, tuple[int, int, float, int]] = {}

        # Incremental "winning points": empty cells that complete a five for a
        # player.  Only the four lines through a move can change, so play/undo
        # refresh eight line entries and the check itself is O(1).
        self.win_counts = (bytearray(CELLS), bytearray(CELLS))
        self.win_sets = (set(), set())
        self.line_wins = [[set() for _ in range(LINE_COUNT)] for _ in range(2)]
        for player in (BLACK, WHITE):
            index = player - 1
            cell_counts = self.win_counts[index]
            winning = self.win_sets[index]
            for line_id in range(LINE_COUNT):
                points = _line_win_points(board, LINES[line_id], player)
                if points:
                    self.line_wins[index][line_id] = points
                    for cell in points:
                        if not cell_counts[cell]:
                            winning.add(cell)
                        cell_counts[cell] += 1

    def _refresh_line(self, line_id: int, player: int) -> None:
        index = player - 1
        points = _line_win_points(self.board, LINES[line_id], player)
        previous = self.line_wins[index][line_id]
        if points == previous:
            return
        cell_counts = self.win_counts[index]
        winning = self.win_sets[index]
        for cell in previous - points:
            cell_counts[cell] -= 1
            if not cell_counts[cell]:
                winning.discard(cell)
        for cell in points - previous:
            if not cell_counts[cell]:
                winning.add(cell)
            cell_counts[cell] += 1
        self.line_wins[index][line_id] = points

    def _refresh_around(self, move: int) -> None:
        for direction in range(4):
            line_id = LINE_ID[direction][move]
            if line_id < 0:
                continue
            self._refresh_line(line_id, BLACK)
            self._refresh_line(line_id, WHITE)

    def play(self, move: int, player: int) -> None:
        self.board[move] = player
        self.hash ^= ZOBRIST[move][player]
        counts = self.neighbors
        for index in NEIGHBOR2[move]:
            counts[index] += 1
        self._refresh_around(move)

    def undo(self, move: int) -> None:
        self.hash ^= ZOBRIST[move][self.board[move]]
        self.board[move] = EMPTY
        counts = self.neighbors
        for index in NEIGHBOR2[move]:
            counts[index] -= 1
        self._refresh_around(move)


def _candidates_fast(board: list[int], counts: list[int]) -> list[int]:
    return [
        move
        for move in range(CELLS)
        if board[move] == EMPTY and counts[move]
    ]


def _width_for_depth(depth: int) -> int:
    if depth >= 4:
        return 8
    if depth == 3:
        return 7
    if depth == 2:
        return 6
    return 5


def _minimax(
    context: _SearchContext,
    turn: int,
    depth: int,
    alpha: float,
    beta: float,
    last_move: int,
    last_player: int,
    ply: int,
) -> float:
    board = context.board
    context.nodes += 1

    if last_move >= 0 and _is_five(board, last_move, last_player):
        return WIN_SCORE - ply if last_player == context.ai else ply - WIN_SCORE

    # O(1) check: does the side to move have a point that completes five?
    if context.win_sets[turn - 1]:
        return WIN_SCORE - ply if turn == context.ai else ply - WIN_SCORE

    if depth <= 0:
        return evaluate_board(board, context.ai)

    if context.deadline:
        if context.cancel is not None and context.cancel():
            context.stopped = True
            return evaluate_board(board, context.ai)
        if time.monotonic() > context.deadline:
            context.stopped = True
            return evaluate_board(board, context.ai)

    key = context.hash ^ (TURN_KEY if turn == BLACK else 0)
    entry = context.table.get(key)
    tt_move = -1
    if entry is not None:
        entry_depth, entry_flag, entry_value, entry_move = entry
        tt_move = entry_move
        if entry_depth >= depth:
            if entry_flag == TT_EXACT:
                return entry_value
            if entry_flag == TT_LOWER:
                if entry_value > alpha:
                    alpha = entry_value
            elif entry_value < beta:
                beta = entry_value
            if alpha >= beta:
                return entry_value

    candidates = _candidates_fast(board, context.neighbors)
    if not candidates:
        return 0

    opponent = other(turn)
    width = _width_for_depth(depth)
    opponent_wins = context.win_sets[opponent - 1]
    pool = opponent_wins if opponent_wins else candidates
    moves = quick_rank_moves(board, turn, width, pool)
    if not moves and pool is not candidates:
        moves = quick_rank_moves(board, turn, width, candidates)
    if not moves:
        legal = get_all_legal_moves(board, turn)
        if not legal:
            if turn == BLACK:
                return ply - WIN_SCORE if turn == context.ai else WIN_SCORE - ply
            return 0
        moves = legal[:width]

    if tt_move >= 0 and moves[0] != tt_move and tt_move in moves:
        moves.remove(tt_move)
        moves.insert(0, tt_move)

    alpha_orig = alpha
    beta_orig = beta
    best_move = moves[0]

    if turn == context.ai:
        best = -float("inf")
        for move in moves:
            context.play(move, turn)
            value = _minimax(
                context,
                opponent,
                depth - 1,
                alpha,
                beta,
                move,
                turn,
                ply + 1,
            )
            context.undo(move)
            if context.stopped:
                break
            if value > best:
                best = value
                best_move = move
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
    else:
        best = float("inf")
        for move in moves:
            context.play(move, turn)
            value = _minimax(
                context,
                context.ai,
                depth - 1,
                alpha,
                beta,
                move,
                turn,
                ply + 1,
            )
            context.undo(move)
            if context.stopped:
                break
            if value < best:
                best = value
                best_move = move
            if best < beta:
                beta = best
            if alpha >= beta:
                break

    if not context.stopped and -WIN_SCORE + 1000 < best < WIN_SCORE - 1000:
        if best <= alpha_orig:
            flag = TT_UPPER
        elif best >= beta_orig:
            flag = TT_LOWER
        else:
            flag = TT_EXACT
        context.table[key] = (depth, flag, best, best_move)
    return best


# ---------------------------------------------------------------------------
# AI players
# ---------------------------------------------------------------------------


def _opening_move(board: list[int]) -> int | None:
    if board_stone_count(board) == 0:
        return random.choice(CENTER_POINTS)
    return None


def _filter_legal_candidates(board: list[int], player: int, candidates: list[int]) -> list[int]:
    if player == WHITE:
        return candidates
    legal = [move for move in candidates if is_legal_move(board, move, player)]
    return legal if legal else get_all_legal_moves(board, player)


def _choose_easy(board: list[int], ai_player: int) -> int:
    opening = _opening_move(board)
    if opening is not None:
        return opening

    candidates = get_candidates(board)
    if not candidates:
        return -1

    wins = immediate_winning_moves(board, ai_player, candidates)
    if wins:
        return random.choice(wins)

    legal_candidates = _filter_legal_candidates(board, ai_player, candidates)
    if not legal_candidates:
        return -1

    blocks = [
        move
        for move in immediate_winning_moves(board, other(ai_player), candidates)
        if is_legal_move(board, move, ai_player)
    ]
    if blocks and random.random() < 0.58:
        return random.choice(blocks)

    if random.random() < 0.42:
        return random.choice(legal_candidates)

    ranked = rank_moves(board, ai_player, 10, legal_candidates)
    if not ranked:
        return legal_candidates[0]
    return random.choice(ranked[: min(4, len(ranked))])


def _choose_medium(board: list[int], ai_player: int) -> int:
    opening = _opening_move(board)
    if opening is not None:
        return opening

    candidates = get_candidates(board)
    if not candidates:
        return -1

    wins = immediate_winning_moves(board, ai_player, candidates)
    if wins:
        return random.choice(wins)

    legal_candidates = _filter_legal_candidates(board, ai_player, candidates)
    blocks = [
        move
        for move in immediate_winning_moves(board, other(ai_player), candidates)
        if is_legal_move(board, move, ai_player)
    ]
    if blocks:
        if len(blocks) == 1:
            return blocks[0]
        ranked = rank_moves(board, ai_player, 1, blocks)
        return ranked[0] if ranked else blocks[0]

    if not legal_candidates:
        return -1
    ranked = rank_moves(board, ai_player, 6, legal_candidates)
    if not ranked:
        return legal_candidates[0]
    return ranked[1] if random.random() < 0.14 and len(ranked) > 1 else ranked[0]


def _choose_hard(board: list[int], ai_player: int, cancel=None) -> int:
    opening = _opening_move(board)
    if opening is not None:
        return opening

    candidates = get_candidates(board)
    if not candidates:
        return -1

    legal_candidates = _filter_legal_candidates(board, ai_player, candidates)
    if not legal_candidates:
        return -1

    wins = immediate_winning_moves(board, ai_player, candidates)
    if wins:
        return random.choice(wins)

    human = other(ai_player)
    blocks = [
        move
        for move in immediate_winning_moves(board, human, candidates)
        if is_legal_move(board, move, ai_player)
    ]
    pool = blocks if blocks else legal_candidates
    root_moves = rank_moves(board, ai_player, HARD_ROOT_WIDTH, pool)
    if not root_moves:
        return legal_candidates[0]

    deadline = time.monotonic() + HARD_TIME_LIMIT
    context = _SearchContext(board, ai_player, deadline, cancel)
    ordered = list(root_moves)
    best_move = ordered[0]
    best_score = -float("inf")

    for depth in range(2, HARD_MAX_DEPTH + 1):
        context.stopped = False
        local_best = -float("inf")
        local_moves: list[int] = []
        scores: dict[int, float] = {}
        alpha = -float("inf")
        for move in ordered:
            if context.stopped:
                break
            context.play(move, ai_player)
            score = _minimax(
                context,
                human,
                depth - 1,
                alpha,
                float("inf"),
                move,
                ai_player,
                1,
            )
            context.undo(move)
            if context.stopped:
                break
            scores[move] = score
            if score > local_best:
                local_best = score
                local_moves = [move]
            elif score == local_best:
                local_moves.append(move)
            if score > alpha:
                alpha = score
        if context.stopped:
            break
        if local_moves:
            best_move = random.choice(local_moves)
            best_score = local_best
            ordered = sorted(
                ordered, key=lambda move: scores.get(move, -float("inf")), reverse=True
            )
        if best_score >= WIN_SCORE - 100:
            break

    return best_move


def choose_move(
    board: list[int], ai_player: int, difficulty: str = "medium", cancel=None
) -> int:
    level = difficulty if difficulty in DIFFICULTIES else "medium"
    if level == "easy":
        move = _choose_easy(board, ai_player)
    elif level == "hard":
        move = _choose_hard(board, ai_player, cancel)
    else:
        move = _choose_medium(board, ai_player)

    if (
        move < 0
        or move >= CELLS
        or board[move] != EMPTY
        or not is_legal_move(board, move, ai_player)
    ):
        fallback = get_all_legal_moves(board, ai_player)
        move = fallback[0] if fallback else -1
    return move
