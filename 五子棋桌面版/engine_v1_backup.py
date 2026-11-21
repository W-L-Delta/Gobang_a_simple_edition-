"""14x14 Gomoku / Renju rules and AI engine for the desktop app."""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Iterable

SIZE = 14
EMPTY = 0
BLACK = 1
WHITE = 2
WIN_SCORE = 1_000_000_000
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))
HARD_SEARCH_DEPTH = 4
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


def other(player: int) -> int:
    return WHITE if player == BLACK else BLACK


def create_board() -> list[int]:
    return [EMPTY] * (SIZE * SIZE)


def row_of(move: int) -> int:
    return move // SIZE


def col_of(move: int) -> int:
    return move % SIZE


def in_bounds(row: int, col: int) -> bool:
    return 0 <= row < SIZE and 0 <= col < SIZE


def board_stone_count(board: list[int]) -> int:
    return sum(1 for value in board if value != EMPTY)


def is_board_full(board: list[int]) -> bool:
    return all(value != EMPTY for value in board)


def _build_run_at(board: list[int], move: int, player: int, dr: int, dc: int) -> list[int]:
    row = row_of(move)
    col = col_of(move)
    run = [move]

    for step in range(1, SIZE):
        r = row + dr * step
        c = col + dc * step
        if not in_bounds(r, c) or board[r * SIZE + c] != player:
            break
        run.append(r * SIZE + c)

    for step in range(1, SIZE):
        r = row - dr * step
        c = col - dc * step
        if not in_bounds(r, c) or board[r * SIZE + c] != player:
            break
        run.insert(0, r * SIZE + c)

    return run


def get_runs_at(board: list[int], move: int, player: int) -> list[list[int]]:
    return [_build_run_at(board, move, player, dr, dc) for dr, dc in DIRECTIONS]


def winning_line_for(board: list[int], move: int, player: int) -> list[int] | None:
    if not (0 <= move < SIZE * SIZE) or board[move] != player:
        return None

    best: list[int] | None = None
    for run in get_runs_at(board, move, player):
        is_win = len(run) == 5 if player == BLACK else len(run) >= 5
        if is_win and (best is None or len(run) > len(best)):
            best = run
    return best


def check_win(board: list[int], last_move: int, player: int) -> list[int] | None:
    return winning_line_for(board, last_move, player)


def would_win_at(board: list[int], move: int, player: int) -> bool:
    was_empty = board[move] == EMPTY
    if not was_empty and board[move] != player:
        return False
    if was_empty:
        board[move] = player
    win = winning_line_for(board, move, player) is not None
    if was_empty:
        board[move] = EMPTY
    return win


def _is_straight_four_run(
    board: list[int], run: list[int], dr: int, dc: int, player: int
) -> bool:
    if len(run) != 4:
        return False

    first = run[0]
    last = run[-1]
    before_row = row_of(first) - dr
    before_col = col_of(first) - dc
    after_row = row_of(last) + dr
    after_col = col_of(last) + dc

    if not in_bounds(before_row, before_col) or not in_bounds(after_row, after_col):
        return False
    if board[before_row * SIZE + before_col] != EMPTY:
        return False
    if board[after_row * SIZE + after_col] != EMPTY:
        return False

    before_two_row = before_row - dr
    before_two_col = before_col - dc
    after_two_row = after_row + dr
    after_two_col = after_col + dc
    if (
        in_bounds(before_two_row, before_two_col)
        and board[before_two_row * SIZE + before_two_col] == player
    ):
        return False
    if (
        in_bounds(after_two_row, after_two_col)
        and board[after_two_row * SIZE + after_two_col] == player
    ):
        return False
    return True


def count_fours_at(board: list[int], move: int, player: int) -> int:
    signatures: set[tuple[int, ...]] = set()
    row = row_of(move)
    col = col_of(move)

    for dr, dc in DIRECTIONS:
        for step in range(-4, 5):
            if step == 0:
                continue
            r = row + dr * step
            c = col + dc * step
            if not in_bounds(r, c):
                continue
            completion = r * SIZE + c
            if board[completion] != EMPTY:
                continue

            board[completion] = player
            run = _build_run_at(board, completion, player, dr, dc)
            if len(run) == 5 and move in run:
                four = tuple(sorted(cell for cell in run if cell != completion))
                signatures.add(four)
            board[completion] = EMPTY

    return len(signatures)


def count_threes_at(board: list[int], move: int, player: int) -> int:
    signatures: set[tuple[int, ...]] = set()
    row = row_of(move)
    col = col_of(move)

    for dr, dc in DIRECTIONS:
        for step in range(-4, 5):
            if step == 0:
                continue
            r = row + dr * step
            c = col + dc * step
            if not in_bounds(r, c):
                continue
            extension = r * SIZE + c
            if board[extension] != EMPTY:
                continue

            board[extension] = player
            run = _build_run_at(board, extension, player, dr, dc)
            if (
                len(run) == 4
                and move in run
                and _is_straight_four_run(board, run, dr, dc, player)
            ):
                runs_at_extension = get_runs_at(board, extension, player)
                creates_five = any(len(item) == 5 for item in runs_at_extension)
                creates_overline = any(len(item) >= 6 for item in runs_at_extension)
                creates_double_four = count_fours_at(board, extension, player) >= 2
                if not creates_five and not creates_overline and not creates_double_four:
                    three = tuple(sorted(cell for cell in run if cell != extension))
                    signatures.add(three)
            board[extension] = EMPTY

    return len(signatures)


def has_overline_at(board: list[int], move: int, player: int) -> bool:
    return any(len(run) >= 6 for run in get_runs_at(board, move, player))


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
    if not (0 <= move < SIZE * SIZE) or board[move] != EMPTY:
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
        overline = has_overline_at(board, move, player)
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


def is_legal_move(board: list[int], move: int, player: int) -> bool:
    if not (0 <= move < SIZE * SIZE) or board[move] != EMPTY:
        return False
    if player == WHITE:
        return True

    board[move] = player
    if winning_line_for(board, move, player) is not None:
        board[move] = EMPTY
        return True
    if has_overline_at(board, move, player):
        board[move] = EMPTY
        return False
    if count_fours_at(board, move, player) >= 2:
        board[move] = EMPTY
        return False
    legal = count_threes_at(board, move, player) < 2
    board[move] = EMPTY
    return legal


def get_candidates(board: list[int], radius: int = 2) -> list[int]:
    seen = bytearray(SIZE * SIZE)
    candidates: list[int] = []
    stones = 0

    for move, value in enumerate(board):
        if value == EMPTY:
            continue
        stones += 1
        row = row_of(move)
        col = col_of(move)
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
    board: list[int], player: int, pool: Iterable[int] | None = None
) -> list[int]:
    candidates = list(pool) if pool is not None else get_candidates(board)
    return [move for move in candidates if board[move] == EMPTY and would_win_at(board, move, player)]


def get_legal_moves(
    board: list[int], player: int, pool: Iterable[int] | None = None
) -> list[int]:
    candidates = list(pool) if pool is not None else get_candidates(board)
    return [
        move
        for move in candidates
        if board[move] == EMPTY and is_legal_move(board, move, player)
    ]


def get_all_legal_moves(board: list[int], player: int) -> list[int]:
    return [
        move
        for move in range(SIZE * SIZE)
        if board[move] == EMPTY and is_legal_move(board, move, player)
    ]


def _line_string_for(board: list[int], row: int, col: int, dr: int, dc: int, player: int) -> str:
    chars: list[str] = []
    for step in range(-5, 6):
        r = row + dr * step
        c = col + dc * step
        if not in_bounds(r, c):
            chars.append("2")
            continue
        value = board[r * SIZE + c]
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
    row = row_of(move)
    col = col_of(move)
    for dr, dc in DIRECTIONS:
        line = _line_string_for(board, row, col, dr, dc, player)
        shape = _classify_direction(line)
        if shape:
            shapes[shape] += 1
    board[move] = EMPTY
    center_distance = max(abs(row - 6.5), abs(col - 6.5))
    return _shape_score(shapes) + max(0.0, 7 - center_distance) * 3


def rank_moves(
    board: list[int], player: int, limit: int, pool: Iterable[int] | None = None
) -> list[int]:
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
    row = row_of(move)
    col = col_of(move)
    score = 0

    for dr, dc in DIRECTIONS:
        count = 1
        open_ends = 0
        for sign in (-1, 1):
            step = 1
            while step < SIZE:
                r = row + dr * step * sign
                c = col + dc * step * sign
                if not in_bounds(r, c) or board[r * SIZE + c] != player:
                    break
                count += 1
                step += 1
            r = row + dr * step * sign
            c = col + dc * step * sign
            if in_bounds(r, c) and board[r * SIZE + c] == EMPTY:
                open_ends += 1

        base = (0, 1, 12, 160, 6_000, 1_000_000)[min(count, 5)]
        multiplier = 2.2 if open_ends == 2 else 1.0 if open_ends == 1 else 0.12
        score += int(base * multiplier)

    board[move] = EMPTY
    return score


def quick_rank_moves(
    board: list[int], player: int, limit: int, pool: Iterable[int]
) -> list[int]:
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
    for i in range(check_limit):
        move = scored[i][1]
        if is_legal_move(board, move, player):
            legal.append(move)
            if len(legal) >= limit:
                break
    return legal


def _build_lines() -> list[list[int]]:
    lines: list[list[int]] = []

    def add(cells: list[int]) -> None:
        if len(cells) >= 5:
            lines.append(cells)

    for r in range(SIZE):
        add([r * SIZE + c for c in range(SIZE)])
    for c in range(SIZE):
        add([r * SIZE + c for r in range(SIZE)])
    for c in range(SIZE):
        cells = []
        r, cc = 0, c
        while r < SIZE and cc < SIZE:
            cells.append(r * SIZE + cc)
            r += 1
            cc += 1
        add(cells)
    for r in range(1, SIZE):
        cells = []
        rr, c = r, 0
        while rr < SIZE and c < SIZE:
            cells.append(rr * SIZE + c)
            rr += 1
            c += 1
        add(cells)
    for c in range(SIZE):
        cells = []
        r, cc = 0, c
        while r < SIZE and cc >= 0:
            cells.append(r * SIZE + cc)
            r += 1
            cc -= 1
        add(cells)
    for r in range(1, SIZE):
        cells = []
        rr, c = r, SIZE - 1
        while rr < SIZE and c >= 0:
            cells.append(rr * SIZE + c)
            rr += 1
            c -= 1
        add(cells)
    return lines


LINES = _build_lines()


def _add_run(stats: list[int], length: int, open_ends: int) -> None:
    # indices: five, openFour, four, openThree, three, openTwo, two
    if length >= 5:
        stats[0] += 1
    elif length == 4:
        if open_ends >= 2:
            stats[1] += 1
        elif open_ends == 1:
            stats[2] += 1
    elif length == 3:
        if open_ends >= 2:
            stats[3] += 1
        elif open_ends == 1:
            stats[4] += 1
    elif length == 2:
        if open_ends >= 2:
            stats[5] += 1
        elif open_ends == 1:
            stats[6] += 1


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

    for line in LINES:
        i = 0
        length = len(line)
        while i < length:
            value = board[line[i]]
            if value == EMPTY:
                i += 1
                continue
            end = i + 1
            while end < length and board[line[end]] == value:
                end += 1
            before = board[line[i - 1]] if i > 0 else -1
            after = board[line[end]] if end < length else -1
            open_ends = (1 if before == EMPTY else 0) + (1 if after == EMPTY else 0)
            _add_run(ai_stats if value == ai_player else human_stats, end - i, open_ends)
            i = end

    return _score_stats(ai_stats) - int(_score_stats(human_stats) * 1.08)


def _width_for_depth(depth: int) -> int:
    if depth >= 4:
        return 8
    if depth == 3:
        return 7
    if depth == 2:
        return 6
    return 5


def _minimax(
    board: list[int],
    turn: int,
    depth: int,
    alpha: float,
    beta: float,
    last_move: int,
    last_player: int,
    ai_player: int,
    ply: int,
    deadline: float,
) -> float:
    if last_move >= 0 and last_player and would_win_at(board, last_move, last_player):
        return WIN_SCORE - ply if last_player == ai_player else -WIN_SCORE + ply
    if time.monotonic() > deadline:
        return evaluate_board(board, ai_player)

    candidates = get_candidates(board)
    if not candidates:
        return 0

    my_wins = immediate_winning_moves(board, turn, candidates)
    if my_wins:
        return WIN_SCORE - ply if turn == ai_player else -WIN_SCORE + ply

    if depth <= 0:
        return evaluate_board(board, ai_player)

    opponent = other(turn)
    opponent_wins = immediate_winning_moves(board, opponent, candidates)
    pool = opponent_wins if opponent_wins else candidates
    width = _width_for_depth(depth)
    moves = quick_rank_moves(board, turn, width, pool)
    if not moves and pool is not candidates:
        moves = quick_rank_moves(board, turn, width, candidates)
    if not moves:
        legal = get_all_legal_moves(board, turn)
        if not legal:
            if turn == BLACK:
                return -WIN_SCORE + ply if turn == ai_player else WIN_SCORE - ply
            return 0
        moves = legal[:width]

    if turn == ai_player:
        best = -float("inf")
        for move in moves:
            board[move] = turn
            value = _minimax(
                board, opponent, depth - 1, alpha, beta, move, turn, ai_player, ply + 1, deadline
            )
            board[move] = EMPTY
            if value > best:
                best = value
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best

    best = float("inf")
    for move in moves:
        board[move] = turn
        value = _minimax(
            board, ai_player, depth - 1, alpha, beta, move, turn, ai_player, ply + 1, deadline
        )
        board[move] = EMPTY
        if value < best:
            best = value
        if best < beta:
            beta = best
        if alpha >= beta:
            break
    return best


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


def _choose_hard(board: list[int], ai_player: int) -> int:
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
    best_score = -float("inf")
    best_moves: list[int] = []

    for move in root_moves:
        if time.monotonic() > deadline and best_moves:
            break
        board[move] = ai_player
        score = _minimax(
            board,
            human,
            HARD_SEARCH_DEPTH,
            -float("inf"),
            float("inf"),
            move,
            ai_player,
            ai_player,
            1,
            deadline,
        )
        board[move] = EMPTY

        if score > best_score:
            best_score = score
            best_moves = [move]
        elif score == best_score:
            best_moves.append(move)

    return random.choice(best_moves if best_moves else root_moves)


def choose_move(board: list[int], ai_player: int, difficulty: str = "medium") -> int:
    level = difficulty if difficulty in DIFFICULTIES else "medium"
    if level == "easy":
        move = _choose_easy(board, ai_player)
    elif level == "hard":
        move = _choose_hard(board, ai_player)
    else:
        move = _choose_medium(board, ai_player)

    if (
        move < 0
        or move >= SIZE * SIZE
        or board[move] != EMPTY
        or not is_legal_move(board, move, ai_player)
    ):
        fallback = get_all_legal_moves(board, ai_player)
        move = fallback[0] if fallback else -1
    return move
