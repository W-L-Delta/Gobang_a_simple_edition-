"""Exhaustively verify per-direction multiplicity of 'three' on a 11-cell window."""

from __future__ import annotations

import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "五子棋桌面版")
sys.path.insert(0, APP)

import engine  # noqa: E402

B, W = engine.BLACK, engine.WHITE
CENTER = 7 * engine.SIZE + 7


def one_line(values):
    """values: 10 cells at cols 2..11 (center col 7 is empty)."""
    board = engine.create_board()
    row = 7
    for k, v in enumerate(values):
        board[row * engine.SIZE + 2 + k] = v
    board[CENTER] = B
    return board


def main() -> None:
    max_fours = 0
    max_threes = 0
    four_best = None
    three_best = None
    total = 0
    for values in itertools.product((0, B, W), repeat=10):
        # player stones / opponent stones / empty, center cell empty
        if values[5] != 0:
            continue
        board = one_line(values)
        total += 1
        f = engine.count_fours_at(board, CENTER, B)
        if f > max_fours:
            max_fours = f
            four_best = values
        t = engine.count_threes_at(board, CENTER, B)
        if t > max_threes:
            max_threes = t
            three_best = values
    print(f"patterns={total} max_fours_per_dir={max_fours} max_threes_per_dir={max_threes}")
    if four_best:
        print("fours:", "".join("#" if v else "." for v in four_best))
    if three_best:
        print("threes:", "".join("#" if v else "." for v in three_best))


if __name__ == "__main__":
    main()
