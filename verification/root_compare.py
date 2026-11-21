"""Compare full root evaluations (fixed depth) across many positions."""

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
        if not legal:
            break
        board[rng.choice(legal)] = player
        player = engine.other(player)
    return board


def root_scores(engine, board, ai, depth, root_moves):
    human = engine.other(ai)
    out = {}
    for move in root_moves:
        board[move] = ai
        if engine is v1:
            score = engine._minimax(
                board, human, depth, -float("inf"), float("inf"), move, ai, ai, 1, float("inf")
            )
        else:
            ctx = engine._SearchContext(board, ai, float("inf"))
            score = engine._minimax(
                ctx, human, depth, -float("inf"), float("inf"), move, ai, 1
            )
        board[move] = engine.EMPTY
        out[move] = score
    return out


def main() -> None:
    mismatches = 0
    total = 0
    for seed in range(12):
        plies = 6 + seed
        board = build_position(v1, plies, seed=300 + seed)
        ai = v1.BLACK if seed % 2 == 0 else v1.WHITE
        root_moves = v1.rank_moves(board, ai, 10)
        if not root_moves:
            continue
        s1 = root_scores(v1, board[:], ai, 3, root_moves)
        s2 = root_scores(v2, board[:], ai, 3, root_moves)
        total += len(root_moves)
        for move in root_moves:
            if s1[move] != s2[move]:
                mismatches += 1
                if mismatches <= 10:
                    print(f"seed={seed} move={move} v1={s1[move]} v2={s2[move]}")
    print(f"root evaluations={total} mismatches={mismatches}")


if __name__ == "__main__":
    main()
