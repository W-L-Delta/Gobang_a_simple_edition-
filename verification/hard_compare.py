"""Hard-mode comparison at the real 1.15 s budget (node counts)."""

from __future__ import annotations

import importlib.util
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "五子棋桌面版")
sys.path.insert(0, APP)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


old = load("engine_v1", os.path.join(APP, "engine_v1_backup.py"))
new = load("engine_new", os.path.join(APP, "engine.py"))


def build(engine, plies, seed):
    rng = random.Random(seed)
    board = engine.create_board()
    player = engine.BLACK
    for _ in range(plies):
        legal = [
            m
            for m in engine.get_candidates(board, 2)
            if engine.is_legal_move(board, m, player)
        ]
        board[rng.choice(legal)] = player
        player = engine.other(player)
    return board


def count(engine):
    calls = {"n": 0}
    original = engine._minimax

    def wrapped(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    engine._minimax = wrapped
    return calls, original


def main() -> None:
    for plies in (12, 20):
        board = build(old, plies, seed=52)
        for label, engine in (("old", old), ("new", new)):
            calls, original = count(engine)
            t0 = time.perf_counter()
            move = engine.choose_move(board, engine.WHITE, "hard")
            elapsed = time.perf_counter() - t0
            engine._minimax = original
            print(f"plies={plies} {label}: {elapsed*1000:7.0f} ms  nodes={calls['n']:5d}  move={move}")

    # How deep does ID get when given enough time?
    board = build(new, 12, seed=52)
    new.HARD_TIME_LIMIT = 600.0
    for depth in (5, 6, 7):
        new.HARD_MAX_DEPTH = depth
        t0 = time.perf_counter()
        move = new.choose_move(board, new.WHITE, "hard")
        print(
            f"ID root+{depth-1}: {(time.perf_counter()-t0)*1000:7.0f} ms  move={move}"
        )
    new.HARD_MAX_DEPTH = 8
    new.HARD_TIME_LIMIT = 1.15


if __name__ == "__main__":
    main()
