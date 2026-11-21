"""Fuzz the incremental search context against full recomputation."""

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


v2 = load("engine_v2")


def fresh_win_sets(board):
    out = []
    for player in (v2.BLACK, v2.WHITE):
        out.append(
            set(
                move
                for move in range(v2.CELLS)
                if board[move] == v2.EMPTY and v2._is_five(board, move, player)
            )
        )
    return out


def check(board, ctx, tag):
    expected = fresh_win_sets(board)
    for index in (0, 1):
        if ctx.win_sets[index] != expected[index]:
            print(f"MISMATCH {tag} player={index+1}")
            print("  got", sorted(ctx.win_sets[index]))
            print("  exp", sorted(expected[index]))
            return False
    # neighbour counts must match a fresh context
    fresh = v2._SearchContext(board[:], v2.BLACK, float("inf"))
    if list(ctx.neighbors) != list(fresh.neighbors):
        print(f"MISMATCH {tag} neighbours")
        return False
    if ctx.hash != fresh.hash:
        print(f"MISMATCH {tag} hash")
        return False
    return True


def main() -> int:
    rng = random.Random(4242)
    failures = 0
    for trial in range(60):
        board = v2.create_board()
        player = v2.BLACK
        for _ in range(rng.randrange(0, 40)):
            empties = [m for m in range(v2.CELLS) if board[m] == v2.EMPTY]
            move = rng.choice(empties)
            board[move] = player
            player = v2.other(player)
        ctx = v2._SearchContext(board[:], v2.BLACK, float("inf"))
        if not check(board, ctx, f"init{trial}"):
            failures += 1
            break
        stack = []
        for step in range(80):
            empties = [m for m in range(v2.CELLS) if board[m] == v2.EMPTY]
            if not empties:
                break
            if stack and rng.random() < 0.35:
                move = stack.pop()
                ctx.undo(move)
                board[move] = v2.EMPTY
                player = v2.other(player)
            else:
                move = rng.choice(empties)
                ctx.play(move, player)
                board[move] = player
                stack.append(move)
                player = v2.other(player)
            if not check(board, ctx, f"trial{trial} step{step}"):
                failures += 1
                break
        if failures:
            break
    print(f"failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
