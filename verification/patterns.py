"""Brute-force local patterns to understand per-direction four/three multiplicity."""

from __future__ import annotations

import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "五子棋桌面版")
sys.path.insert(0, APP)

import engine  # noqa: E402

B = engine.BLACK


def main() -> None:
    max_fours = 0
    max_threes = 0
    four_examples = []
    three_examples = []
    for bits in itertools.product((0, B), repeat=8):
        board = engine.create_board()
        row = 7
        center = row * engine.SIZE + 7
        for k, v in enumerate(bits):
            board[row * engine.SIZE + 3 + k] = v
        # move at col 7 -> index in bits: 7-3=4
        if bits[4] != 0:
            continue
        board[center] = B
        f = engine.count_fours_at(board, center, B)
        t = engine.count_threes_at(board, center, B)
        if f > max_fours:
            max_fours = f
            four_examples = [bits]
        elif f == max_fours and f >= 2 and len(four_examples) < 4:
            four_examples.append(bits)
        if t > max_threes:
            max_threes = t
            three_examples = [bits]
        elif t == max_threes and t >= 2 and len(three_examples) < 4:
            three_examples.append(bits)
    print("max fours from one horizontal line:", max_fours)
    for bits in four_examples[:4]:
        print("  ", "".join("#" if v else "." for v in bits))
    print("max threes from one horizontal line:", max_threes)
    for bits in three_examples[:4]:
        print("  ", "".join("#" if v else "." for v in bits))


if __name__ == "__main__":
    main()
