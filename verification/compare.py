"""Differential test: engine_v1 (original) vs engine_v2 (optimized)."""

from __future__ import annotations

import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v1 = load("engine_v1")
v2 = load("engine_v2")


def random_stones(rng, count):
    board = v1.create_board()
    cells = list(range(v1.SIZE * v1.SIZE))
    rng.shuffle(cells)
    for i, move in enumerate(cells[:count]):
        board[move] = v1.BLACK if i % 2 == 0 else v1.WHITE
    return board


def main() -> int:
    rng = random.Random(99)
    problems = 0
    checked = 0

    for trial in range(220):
        stone_count = rng.choice([4, 8, 12, 18, 24, 30, 40, 60])
        board = random_stones(rng, stone_count)

        for move in range(v1.SIZE * v1.SIZE):
            for player in (v1.BLACK, v1.WHITE):
                if board[move] != v1.EMPTY:
                    continue
                a1 = v1.analyze_move(board, move, player)
                a2 = v2.analyze_move(board, move, player)
                checked += 1
                if (a1.legal, a1.winning, a1.forbidden, a1.reasons, a1.overline, a1.fours, a1.threes) != (
                    a2.legal,
                    a2.winning,
                    a2.forbidden,
                    a2.reasons,
                    a2.overline,
                    a2.fours,
                    a2.threes,
                ):
                    problems += 1
                    if problems <= 10:
                        print(
                            "ANALYZE mismatch",
                            move,
                            player,
                            (a1.legal, a1.winning, a1.reasons, a1.fours, a1.threes),
                            (a2.legal, a2.winning, a2.reasons, a2.fours, a2.threes),
                        )
                if v1.is_legal_move(board, move, player) != v2.is_legal_move(board, move, player):
                    problems += 1
                    if problems <= 10:
                        print("LEGAL mismatch", move, player)

            if board[move] != v1.EMPTY:
                player = board[move]
                r1 = v1.winning_line_for(board, move, player)
                r2 = v2.winning_line_for(board, move, player)
                if r1 != r2:
                    problems += 1
                    if problems <= 10:
                        print("WINLINE mismatch", move, r1, r2)
                if v1.would_win_at(board, move, player) != v2.would_win_at(board, move, player):
                    problems += 1

        if trial % 20 == 0:
            e1 = v1.evaluate_board(board, v1.BLACK)
            e2 = v2.evaluate_board(board, v2.BLACK)
            if e1 != e2:
                problems += 1
                print("EVAL mismatch", e1, e2)
            c1 = v1.get_candidates(board)
            c2 = v2.get_candidates(board)
            if c1 != c2:
                problems += 1
                print("CANDIDATES mismatch", len(c1), len(c2))

        # spot-check placement score on a few empty cells
        empties = [m for m in range(v1.SIZE * v1.SIZE) if board[m] == v1.EMPTY]
        rng.shuffle(empties)
        for move in empties[:3]:
            for player in (v1.BLACK, v1.WHITE):
                s1 = v1.placement_score(board, move, player)
                s2 = v2.placement_score(board, move, player)
                if s1 != s2:
                    problems += 1
                    if problems <= 10:
                        print("SCORE mismatch", move, s1, s2)
                q1 = v1._quick_point_score(board, move, player)
                q2 = v2._quick_point_score(board, move, player)
                if q1 != q2:
                    problems += 1
                    if problems <= 10:
                        print("QUICK mismatch", move, q1, q2)

    print(f"checked_cells={checked} problems={problems}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
