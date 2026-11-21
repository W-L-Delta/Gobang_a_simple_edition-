"""Self-play match: optimized engine vs original engine (both hard)."""

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

TIME_LIMIT = 0.25


def play(black_engine, white_engine, seed):
    random.seed(seed)
    board = v1.create_board()
    player = v1.BLACK
    moves = 0
    while moves < v1.SIZE * v1.SIZE:
        engine = black_engine if player == v1.BLACK else white_engine
        move = engine.choose_move(board[:], player, "hard")
        if move < 0 or move >= v1.SIZE * v1.SIZE or board[move] != v1.EMPTY:
            return 0, moves, f"bad move {move}"
        if not v1.is_legal_move(board, move, player):
            return 0, moves, f"illegal move {move} for {player}"
        board[move] = player
        moves += 1
        if v1.check_win(board, move, player):
            return player, moves, "win"
        player = v1.other(player)
    return 0, moves, "draw"


def main() -> None:
    v1.HARD_TIME_LIMIT = TIME_LIMIT
    v2.HARD_TIME_LIMIT = TIME_LIMIT
    wins = {"v2": 0, "v1": 0, "draw": 0}
    started = time.perf_counter()
    for game in range(8):
        v2_black = game % 2 == 0
        if v2_black:
            result, moves, note = play(v2, v1, 500 + game)
            winner = "v2" if result == v1.BLACK else "v1" if result == v1.WHITE else "draw"
        else:
            result, moves, note = play(v1, v2, 500 + game)
            winner = "v1" if result == v1.BLACK else "v2" if result == v1.WHITE else "draw"
        wins[winner] += 1
        print(
            f"game {game}: v2={'BLACK' if v2_black else 'WHITE'} -> {winner}"
            f" ({moves} moves, {note})"
        )
    print(f"score v2-v1: {wins['v2']} - {wins['v1']} (draws {wins['draw']})")
    print(f"elapsed {time.perf_counter()-started:.1f}s")


if __name__ == "__main__":
    main()
