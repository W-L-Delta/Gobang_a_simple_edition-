"""Fixed-depth (no time limit) comparison of the two search cores."""

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


v1 = load("engine_v1")
v2 = load("engine_v2")


def build_position(engine, plies, seed):
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


def count_calls(module):
    calls = {"n": 0}
    original = module._minimax

    def wrapped(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    module._minimax = wrapped
    return calls, original


def run_v1(board, depth, ai, root_move):
    human = v1.other(ai)
    calls, original = count_calls(v1)
    t0 = time.perf_counter()
    board[root_move] = ai
    score = v1._minimax(
        board, human, depth, -float("inf"), float("inf"), root_move, ai, ai, 1, float("inf")
    )
    board[root_move] = v1.EMPTY
    elapsed = time.perf_counter() - t0
    v1._minimax = original
    return elapsed, calls["n"], score


def run_v2(board, depth, ai, root_move):
    human = v2.other(ai)
    calls, original = count_calls(v2)
    ctx = v2._SearchContext(board, ai, float("inf"))
    t0 = time.perf_counter()
    ctx.play(root_move, ai)
    score = v2._minimax(ctx, human, depth, -float("inf"), float("inf"), root_move, ai, 1)
    ctx.undo(root_move)
    elapsed = time.perf_counter() - t0
    v2._minimax = original
    return elapsed, calls["n"] - 1, score


def main() -> None:
    for plies in (8, 12):
        board = build_position(v1, plies, seed=77)
        empties = [m for m in range(v1.SIZE * v1.SIZE) if board[m] == v1.EMPTY]
        root_move = empties[len(empties) // 2]
        print(f"position plies={plies} stones={sum(1 for v in board if v)} root={root_move}")
        for depth in (3, 4):
            t1, n1, s1 = run_v1(board[:], depth, v1.BLACK, root_move)
            t2, n2, s2 = run_v2(board[:], depth, v2.BLACK, root_move)
            print(
                f"  depth={depth}: v1 {t1*1000:8.1f} ms / {n1:5d} nodes"
                f" | v2 {t2*1000:8.1f} ms / {n2:5d} nodes"
                f" | speedup {t1/t2:5.2f}x  scores {s1} vs {s2}"
            )


if __name__ == "__main__":
    main()
