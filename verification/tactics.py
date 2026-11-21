"""Tactical sanity tests for the AI (win / block / legality)."""

from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "五子棋桌面版")
sys.path.insert(0, HERE)


def load(name, path=None):
    spec = importlib.util.spec_from_file_location(name, path or os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v2 = load("engine_v2")
B, W = v2.BLACK, v2.WHITE


def board_from(black, white):
    board = v2.create_board()
    for r, c in black:
        board[r * v2.SIZE + c] = B
    for r, c in white:
        board[r * v2.SIZE + c] = W
    return board


def idx(r, c):
    return r * v2.SIZE + c


def test_win(level):
    board = board_from([(2, 2), (9, 9)], [(7, 4), (7, 5), (7, 6), (7, 7)])
    move = v2.choose_move(board, W, level)
    ok = move in (idx(7, 3), idx(7, 8))
    print(f"[{'PASS' if ok else 'FAIL'}] {level}: complete own four -> {move}")
    return ok


def test_block(level):
    board = board_from([(7, 4), (7, 5), (7, 6), (7, 7)], [(7, 3), (2, 2)])
    move = v2.choose_move(board, W, level)
    ok = move == idx(7, 8)
    print(f"[{'PASS' if ok else 'FAIL'}] {level}: block black four -> {move}")
    return ok


def test_black_five(level):
    board = board_from([(7, 4), (7, 5), (7, 6), (7, 7), (2, 2)], [(9, 9)])
    move = v2.choose_move(board, B, level)
    ok = move in (idx(7, 3), idx(7, 8))
    print(f"[{'PASS' if ok else 'FAIL'}] {level}: black completes five -> {move}")
    return ok


def test_legality(level):
    board = board_from([(7, 4), (7, 5), (5, 6), (6, 6), (2, 2)], [(3, 3), (9, 9)])
    move = v2.choose_move(board, B, level)
    ok = move >= 0 and v2.is_legal_move(board, move, B) and board[move] == v2.EMPTY
    print(f"[{'PASS' if ok else 'FAIL'}] {level}: black move is legal -> {move}")
    return ok


def main() -> int:
    failures = 0
    for level in ("easy", "medium", "hard"):
        for fn in (test_win, test_block, test_black_five, test_legality):
            if not fn(level):
                failures += 1
    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
