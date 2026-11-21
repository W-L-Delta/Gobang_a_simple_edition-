"""Headless-ish smoke test for the Tk app (no manual clicking)."""

from __future__ import annotations

import os
import sys
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "五子棋桌面版")
sys.path.insert(0, APP)

import main  # noqa: E402


def pump(root, seconds=0.2):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


def main_test() -> None:
    root = tk.Tk()
    root.withdraw()
    app = main.GomokuApp(root)
    pump(root, 0.4)

    if app.setup_dialog and app.setup_dialog.winfo_exists():
        app.setup_dialog.destroy()
        app.setup_dialog = None
        pump(root, 0.1)

    # Local mode: alternate clicks, then undo.
    app.start_new_game(True, "medium", "local")
    pump(root)
    for _ in range(8):
        empties = [m for m in range(196) if app.board[m] == 0]
        app.on_board_click(empties[len(empties) // 2])
        pump(root, 0.05)
    print("local: phase", app.phase, "history", len(app.history))
    app.undo_move()
    pump(root)
    print("local undo: phase", app.phase, "history", len(app.history))

    # PVE: player black, wait for the AI reply.
    app.start_new_game(True, "medium", "pve")
    pump(root)
    app.on_board_click(7 * 14 + 7)
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        pump(root, 0.05)
        if len(app.history) >= 2 and app.phase != "ai":
            break
    print("pve: phase", app.phase, "history", len(app.history), "current", app.current)

    # Cancel a hard search and restart to exercise the cancellation path.
    app.start_new_game(False, "hard", "pve")
    pump(root, 0.4)
    print("hard ai start: phase", app.phase)
    app.start_new_game(True, "easy", "pve")
    pump(root, 0.3)
    print("after restart: phase", app.phase, "history", len(app.history))

    app.on_close()


if __name__ == "__main__":
    main_test()
