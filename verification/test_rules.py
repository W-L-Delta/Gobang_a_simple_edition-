"""Rule-level test table for the current engine (baseline)."""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "五子棋桌面版")
sys.path.insert(0, APP)

import engine  # noqa: E402

B, W, E = engine.BLACK, engine.WHITE, engine.EMPTY


def board_from(black, white):
    b = engine.create_board()
    for r, c in black:
        b[r * engine.SIZE + c] = B
    for r, c in white:
        b[r * engine.SIZE + c] = W
    return b


def check(name, got, want):
    ok = got == want
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: got={got!r} want={want!r}")
    return ok


def main() -> int:
    failures = 0

    # --- win detection -----------------------------------------------------
    # 1. five completed in the middle (stones on both sides of the new one)
    b = board_from([(7, 3), (7, 4), (7, 6), (7, 7)], [])
    b[7 * 14 + 5] = B
    line = engine.check_win(b, 7 * 14 + 5, B)
    failures += not check("black five in the middle", line is not None and len(line) == 5, True)
    failures += not check("win_line covers both sides", sorted(engine.col_of(m) for m in line), [3, 4, 5, 6, 7])

    # 2. vertical
    b = board_from([(3, 7), (4, 7), (5, 7), (6, 7)], [])
    b[7 * 14 + 7] = B
    failures += not check("black five vertical", engine.check_win(b, 7 * 14 + 7, B) is not None, True)

    # 3. diagonal
    b = board_from([(0, 0), (1, 1), (2, 2), (3, 3)], [])
    b[4 * 14 + 4] = B
    failures += not check("black five diagonal", engine.check_win(b, 4 * 14 + 4, B) is not None, True)

    # 4. anti-diagonal
    b = board_from([(0, 9), (1, 8), (2, 7), (3, 6)], [])
    b[4 * 14 + 5] = B
    failures += not check("black five anti-diagonal", engine.check_win(b, 4 * 14 + 5, B) is not None, True)

    # 5. edge / corner
    b = board_from([(0, 1), (0, 2), (0, 3), (0, 4)], [])
    b[0] = B
    failures += not check("black five on top edge", engine.check_win(b, 0, B) is not None, True)

    # 6. black overline is not a win but is forbidden
    b = board_from([(7, 1), (7, 2), (7, 3), (7, 4), (7, 5)], [])
    a = engine.analyze_move(b, 7 * 14 + 6, B)
    failures += not check("black overline: forbidden", (a.legal, a.forbidden, a.reasons), (False, True, ("overline",)))
    failures += not check("black overline: not winning", a.winning, False)

    # 7. white overline wins
    b = board_from([], [(7, 1), (7, 2), (7, 3), (7, 4), (7, 5)])
    b[7 * 14 + 6] = W
    failures += not check("white overline wins", engine.check_win(b, 7 * 14 + 6, W) is not None, True)
    failures += not check("white overline length", len(engine.check_win(b, 7 * 14 + 6, W)), 6)

    # 8. white double-three is allowed
    b = board_from([], [(7, 4), (7, 5), (5, 6), (6, 6)])
    a = engine.analyze_move(b, 7 * 14 + 6, W)
    failures += not check("white has no forbidden", (a.legal, a.forbidden), (True, False))

    # 9. black exact five with no other shape
    b = board_from([(7, 3), (7, 4), (7, 5), (7, 6)], [])
    a = engine.analyze_move(b, 7 * 14 + 7, B)
    failures += not check("black five is legal+win", (a.legal, a.winning, a.forbidden), (True, True, False))

    # 10. double four is forbidden
    b = board_from(
        [(7, 4), (7, 5), (7, 6), (4, 7), (5, 7), (6, 7)],
        [],
    )
    a = engine.analyze_move(b, 7 * 14 + 7, B)
    failures += not check("double four banned", (a.legal, a.fours), (False, 2))
    print("     double-four probe:", a.legal, a.reasons, "fours=", a.fours, "threes=", a.threes)

    # 11. double three is forbidden
    b = board_from([(7, 4), (7, 5), (5, 6), (6, 6)], [])
    a = engine.analyze_move(b, 7 * 14 + 6, B)
    failures += not check("double three banned", (a.legal, a.threes), (False, 2))
    print("     double-three probe:", a.legal, a.reasons, "fours=", a.fours, "threes=", a.threes)

    # 12. five priority over double four
    b = board_from(
        [(7, 3), (7, 4), (7, 5), (7, 7), (4, 6), (5, 6), (6, 6), (4, 3), (5, 4), (6, 5)],
        [],
    )
    a = engine.analyze_move(b, 7 * 14 + 6, B)
    failures += not check(
        "five beats double four", (a.legal, a.winning, a.reasons), (True, True, ())
    )
    print("     five-priority probe:", a.legal, a.winning, a.reasons, "fours=", a.fours)

    # 13. full board is a draw
    b = [B] * (14 * 14)
    failures += not check("full board", engine.is_board_full(b), True)

    # 14. check_win on an empty last move
    failures += not check("check_win rejects empty cell", engine.check_win(engine.create_board(), 0, B), None)

    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
