"""A/B the two quick point score implementations."""

from __future__ import annotations

import importlib.util
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v2 = load("engine_v2")

NEXT = v2.NEXT
PREV = v2.PREV
POS = v2.POS
NEG = v2.NEG
BASE = v2.BASE_POINT_SCORE
MULT = v2.OPEN_MULTIPLIER
VALUES = v2.POINT_VALUE


def old_score(board, move, player):
    board[move] = player
    score = 0
    for direction in range(4):
        count = 1
        open_ends = 0
        index = NEXT[direction][move]
        while index >= 0 and board[index] == player:
            count += 1
            index = NEXT[direction][index]
        if index >= 0 and board[index] == v2.EMPTY:
            open_ends += 1
        index = PREV[direction][move]
        while index >= 0 and board[index] == player:
            count += 1
            index = PREV[direction][index]
        if index >= 0 and board[index] == v2.EMPTY:
            open_ends += 1
        score += int(BASE[count if count < 5 else 5] * MULT[open_ends])
    board[move] = v2.EMPTY
    return score


def new_score(board, move, player):
    board[move] = player
    score = 0
    values = VALUES
    for direction in range(4):
        count = 1
        open_ends = 0
        for index in POS[direction][move]:
            value = board[index]
            if value != player:
                if value == v2.EMPTY:
                    open_ends += 1
                break
            count += 1
        for index in NEG[direction][move]:
            value = board[index]
            if value != player:
                if value == v2.EMPTY:
                    open_ends += 1
                break
            count += 1
        score += values[open_ends][count if count < 5 else 5]
    board[move] = v2.EMPTY
    return score


def main() -> None:
    rng = random.Random(11)
    board = v2.create_board()
    player = v2.BLACK
    for _ in range(30):
        empties = [m for m in range(v2.CELLS) if board[m] == v2.EMPTY]
        board[rng.choice(empties)] = player
        player = v2.other(player)
    empties = [m for m in range(v2.CELLS) if board[m] == v2.EMPTY]

    for name, fn in (("old", old_score), ("new", new_score)):
        best = 1e9
        for _ in range(5):
            t0 = time.perf_counter()
            total = 0
            for _ in range(200):
                for move in empties:
                    total += fn(board, move, v2.BLACK)
            best = min(best, time.perf_counter() - t0)
        print(f"{name}: {best * 1e6 / (200 * len(empties)):.2f} us/call (checksum {total})")


if __name__ == "__main__":
    main()
