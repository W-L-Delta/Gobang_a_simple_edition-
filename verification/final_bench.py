"""Final before/after benchmark for the deployed engine."""

from __future__ import annotations

import importlib.util
import os
import random
import statistics
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


def bench(fn, repeat):
    times = []
    result = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    return statistics.median(times), min(times), result


def fixed_depth(engine, board, ai, depth, root_move, is_old):
    human = engine.other(ai)
    board[root_move] = ai
    if is_old:
        t0 = time.perf_counter()
        score = engine._minimax(
            board, human, depth, -float("inf"), float("inf"), root_move, ai, ai, 1, float("inf")
        )
        elapsed = time.perf_counter() - t0
    else:
        ctx = engine._SearchContext(board, ai, float("inf"))
        t0 = time.perf_counter()
        score = engine._minimax(ctx, human, depth, -float("inf"), float("inf"), root_move, ai, 1)
        elapsed = time.perf_counter() - t0
    board[root_move] = engine.EMPTY
    return elapsed, score


def main() -> None:
    board = build(old, 14, seed=7)
    empties = [m for m in range(old.SIZE * old.SIZE) if board[m] == old.EMPTY]
    print(f"position: 14 stones, {len(empties)} empty points\n")

    rows = []
    for label, fn_old, fn_new in (
        ("get_candidates", lambda: old.get_candidates(board), lambda: new.get_candidates(board)),
        (
            "is_legal_move x% d (black)" % len(empties),
            lambda: [old.is_legal_move(board, m, old.BLACK) for m in empties],
            lambda: [new.is_legal_move(board, m, new.BLACK) for m in empties],
        ),
        ("evaluate_board", lambda: old.evaluate_board(board, old.BLACK), lambda: new.evaluate_board(board, new.BLACK)),
    ):
        t_old, _, _ = bench(fn_old, 5)
        t_new, _, _ = bench(fn_new, 5)
        rows.append((label, t_old * 1e6, t_new * 1e6, t_old / t_new))

    for label, t_old, t_new, ratio in rows:
        print(f"{label:28s} {t_old:10.1f} us -> {t_new:9.1f} us   {ratio:5.2f}x")

    # Quick point score over many points.
    def quick(e, player):
        total = 0
        for m in empties:
            total += e._quick_point_score(board, m, player)
        return total

    t_old, _, _ = bench(lambda: quick(old, old.BLACK), 5)
    t_new, _, _ = bench(lambda: quick(new, new.BLACK), 5)
    print(
        f"{'quick_point_score x%d' % len(empties):28s} {t_old*1e6:10.1f} us -> {t_new*1e6:9.1f} us   {t_old/t_new:5.2f}x"
    )

    # Fixed depth 4, same root move.
    root = empties[len(empties) // 2]
    old_best = min(fixed_depth(old, board[:], old.BLACK, 4, root, True)[0] for _ in range(3))
    new_best = min(fixed_depth(new, board[:], new.BLACK, 4, root, False)[0] for _ in range(3))
    _, s_old = fixed_depth(old, board[:], old.BLACK, 4, root, True)
    _, s_new = fixed_depth(new, board[:], new.BLACK, 4, root, False)
    print(
        f"{'fixed depth-4 search':28s} {old_best*1000:10.1f} ms -> {new_best*1000:9.1f} ms   {old_best/new_best:5.2f}x"
        f"   scores {s_old} / {s_new}"
    )

    # AI timings, medium (hard is capped at 1.15 s by design).
    for level in ("medium",):
        for plies in (8, 14, 20):
            b = build(old, plies, seed=40 + plies)
            t_old, _, m_old = bench(lambda: old.choose_move(b, old.WHITE, level), 3)
            t_new, _, m_new = bench(lambda: new.choose_move(b, new.WHITE, level), 3)
            print(
                f"{level+' plies='+str(plies):28s} {t_old*1000:10.1f} ms -> {t_new*1000:9.1f} ms   {t_old/t_new:5.2f}x"
                f"   moves {m_old}/{m_new}"
            )


if __name__ == "__main__":
    main()
