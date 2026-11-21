"""Desktop Gomoku / Renju game (Tkinter + Pillow).

A standalone, non-HTML version of the 14x14 Gomoku game with three AI levels,
rock-paper-scissors for the first move, and black forbidden moves.
"""

from __future__ import annotations

import ctypes
import math
import os
import queue
import random
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable

from PIL import Image, ImageDraw, ImageFilter, ImageTk

import engine


APP_NAME = "五子棋 · 十四路有禁手"
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Palette and typography
# ---------------------------------------------------------------------------

BG = "#0a110d"
BG_DEEP = "#070c09"
PANEL = "#141f19"
PANEL_LIGHT = "#1a2820"
PANEL_DARK = "#0d1611"
CARD = "#101a14"
CARD_ACTIVE = "#1a2a20"
BORDER = "#2a3b2f"
BORDER_GOLD = "#6f5a36"
TEXT = "#f3ecdd"
MUTED = "#a3afa6"
MUTED_DIM = "#77857c"
GOLD = "#e6be7b"
GOLD_BRIGHT = "#f4d79e"
GOLD_DARK = "#a8783d"
RED = "#d77b67"
RED_DARK = "#8f3f2e"
WOOD_FRAME = "#533c24"

RPS = {
    "rock": {"label": "石头", "icon": "✊", "beats": "scissors"},
    "scissors": {"label": "剪刀", "icon": "✌", "beats": "paper"},
    "paper": {"label": "布", "icon": "✋", "beats": "rock"},
}


def resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", APP_DIR)
    return os.path.join(base, relative)


def _pick_font(root: tk.Misc, candidates: list[str], fallback: str) -> str:
    families = set(tkfont.families(root))
    for name in candidates:
        if name in families:
            return name
    return fallback


def _mix(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _rounded_rect_points(x1: float, y1: float, x2: float, y2: float, r: float):
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]


def draw_round_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    fill: str | None,
    outline: str | None = None,
    width: int = 1,
    tags: str | tuple[str, ...] | None = None,
):
    return canvas.create_polygon(
        _rounded_rect_points(x1, y1, x2, y2, radius),
        smooth=True,
        splinesteps=24,
        fill=fill or "",
        outline=outline or "",
        width=width,
        tags=tags,
    )


class FlatButton(tk.Button):
    """A flat, modern-looking button with hover and disabled states."""

    VARIANTS = {
        "primary": {
            "bg": GOLD,
            "fg": "#211407",
            "active": GOLD_BRIGHT,
            "hover": "#f1cf92",
            "disabled_bg": "#3a3328",
            "disabled_fg": "#7b7468",
            "border": GOLD_BRIGHT,
        },
        "secondary": {
            "bg": "#1a2820",
            "fg": TEXT,
            "active": "#223529",
            "hover": "#223529",
            "disabled_bg": "#151e18",
            "disabled_fg": "#5d695f",
            "border": BORDER,
        },
        "ghost": {
            "bg": PANEL,
            "fg": MUTED,
            "active": "#1b2921",
            "hover": "#1b2921",
            "disabled_bg": PANEL,
            "disabled_fg": "#4f5b52",
            "border": BORDER,
        },
        "danger": {
            "bg": "#5b3027",
            "fg": "#f1c9bf",
            "active": "#6d3a2f",
            "hover": "#6d3a2f",
            "disabled_bg": "#2a1c18",
            "disabled_fg": "#735c55",
            "border": "#7b4235",
        },
    }

    def __init__(
        self,
        master,
        text: str,
        command: Callable[[], None] | None = None,
        variant: str = "primary",
        width: int | None = None,
        font: tkfont.Font | None = None,
        padx: int = 18,
        pady: int = 10,
        **kwargs,
    ):
        self._variant = self.VARIANTS.get(variant, self.VARIANTS["primary"])
        self._hovered = False
        super().__init__(
            master,
            text=text,
            command=command,
            font=font,
            bg=self._variant["bg"],
            fg=self._variant["fg"],
            activebackground=self._variant["active"],
            activeforeground=self._variant["fg"],
            disabledforeground=self._variant["disabled_fg"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self._variant["border"],
            highlightcolor=self._variant["border"],
            cursor="hand2",
            padx=padx,
            pady=pady,
            width=width,
            **kwargs,
        )
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, _event=None):
        self._hovered = True
        if self["state"] != "disabled":
            self.configure(bg=self._variant["hover"])

    def _on_leave(self, _event=None):
        self._hovered = False
        if self["state"] != "disabled":
            self.configure(bg=self._variant["bg"])

    def set_enabled(self, enabled: bool) -> None:
        self.configure(
            state="normal" if enabled else "disabled",
            bg=self._variant["bg"] if enabled else self._variant["disabled_bg"],
            cursor="hand2" if enabled else "arrow",
        )


class ModeToggle(tk.Button):
    def __init__(
        self,
        master,
        mode: str,
        text: str,
        command: Callable[[str], None],
        font: tkfont.Font,
    ):
        super().__init__(
            master,
            text=text,
            command=lambda: command(mode),
            bg=CARD,
            fg=MUTED,
            activebackground=CARD_ACTIVE,
            activeforeground=GOLD_BRIGHT,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER_GOLD,
            cursor="hand2",
            font=font,
            padx=16,
            pady=7,
        )
        self.mode = mode
        self._selected = False

    def set_selected(self, selected: bool):
        self._selected = selected
        self.configure(
            bg=CARD_ACTIVE if selected else CARD,
            fg=GOLD_BRIGHT if selected else MUTED,
            highlightbackground=BORDER_GOLD if selected else BORDER,
            activebackground=CARD_ACTIVE,
        )


class DifficultyCard(tk.Frame):
    def __init__(
        self,
        master,
        level: str,
        marker: str,
        title: str,
        tagline: str,
        description: str,
        command: Callable[[str], None],
        fonts: dict[str, tkfont.Font],
    ):
        super().__init__(
            master,
            bg=CARD,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=GOLD,
            cursor="hand2",
            padx=13,
            pady=10,
        )
        self.level = level
        self.command = command
        self._selected = False
        self._widgets: list[tk.Widget] = []

        self.marker = tk.Label(
            self, text=marker, bg=CARD, fg=GOLD, font=fonts["small"], anchor="w"
        )
        self.marker.pack(fill="x")
        self.title = tk.Label(
            self, text=title, bg=CARD, fg=TEXT, font=fonts["serif_17"], anchor="w"
        )
        self.title.pack(fill="x", pady=(1, 0))
        self.tagline = tk.Label(
            self, text=tagline, bg=CARD, fg=GOLD, font=fonts["tiny"], anchor="w"
        )
        self.tagline.pack(fill="x")
        self.description = tk.Label(
            self,
            text=description,
            bg=CARD,
            fg=MUTED_DIM,
            font=fonts["tiny"],
            anchor="w",
            justify="left",
            wraplength=180,
        )
        self.description.pack(fill="x", pady=(5, 0))
        self._widgets = [self, self.marker, self.title, self.tagline, self.description]

        for widget in self._widgets:
            widget.bind("<Button-1>", self._click)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)

    def _click(self, _event=None):
        self.command(self.level)

    def _enter(self, _event=None):
        if not self._selected:
            self._paint(CARD_ACTIVE)

    def _leave(self, _event=None):
        if not self._selected:
            self._paint(CARD)

    def _paint(self, bg: str):
        self.configure(bg=bg)
        for widget in self._widgets[1:]:
            widget.configure(bg=bg)

    def set_selected(self, selected: bool):
        self._selected = selected
        self.configure(
            bg=CARD_ACTIVE if selected else CARD,
            highlightbackground=BORDER_GOLD if selected else BORDER,
        )
        for widget in self._widgets[1:]:
            widget.configure(bg=CARD_ACTIVE if selected else CARD)


class HandSlot(tk.Frame):
    def __init__(self, master, owner: str, fonts: dict[str, tkfont.Font], ai: bool = False):
        super().__init__(
            master,
            bg=PANEL_DARK,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=12,
            pady=8,
        )
        self._selected = False
        self._ai = ai
        self.owner = tk.Label(
            self, text=owner, bg=PANEL_DARK, fg=MUTED_DIM, font=fonts["tiny"]
        )
        self.owner.pack()
        self.icon = tk.Label(
            self,
            text="?",
            bg=PANEL_DARK,
            fg=GOLD if ai else TEXT,
            font=fonts["emoji_30"],
            width=2,
            height=1,
        )
        self.icon.pack(pady=(2, 0))

    def set_icon(self, text: str):
        self.icon.configure(text=text)

    def set_owner(self, text: str):
        self.owner.configure(text=text)

    def set_highlight(self, on: bool):
        self._selected = on
        if on:
            self.configure(highlightbackground=BORDER_GOLD)
            self.owner.configure(fg=GOLD)
        else:
            self.configure(highlightbackground=BORDER)
            self.owner.configure(fg=MUTED_DIM)


class ModalBase(tk.Toplevel):
    """Borderless, centered modal window with a custom close button."""

    def __init__(
        self,
        app: "GomokuApp",
        width: int,
        height: int,
        allow_cancel: bool = True,
        close_command: Callable[[], None] | None = None,
    ):
        super().__init__(app.root)
        self.app = app
        self.allow_cancel = allow_cancel
        self._close_command = close_command
        self.overrideredirect(True)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app.root)
        self.attributes("-topmost", False)
        self._width = width
        self._height = height
        self._center()
        self.outer = tk.Frame(
            self,
            bg=BG,
            highlightthickness=1,
            highlightbackground=BORDER_GOLD,
            padx=0,
            pady=0,
        )
        self.outer.pack(fill="both", expand=True)
        self.close_button = tk.Button(
            self.outer,
            text="✕",
            command=self.cancel,
            bg=BG,
            fg=MUTED,
            activebackground=PANEL_LIGHT,
            activeforeground=GOLD_BRIGHT,
            relief="flat",
            bd=0,
            font=app.fonts["ui_12"],
            width=2,
            cursor="hand2",
            highlightthickness=0,
        )
        self.close_button.place(relx=1.0, x=-14, y=12, anchor="ne")
        self.bind("<Escape>", lambda _event: self.cancel())
        self.after(30, self._activate)

    def _center(self):
        root = self.app.root
        root.update_idletasks()
        x = root.winfo_rootx() + max(0, (root.winfo_width() - self._width) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - self._height) // 2)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(8, min(x, screen_w - self._width - 8))
        y = max(8, min(y, screen_h - self._height - 40))
        self.geometry(f"{self._width}x{self._height}+{x}+{y}")

    def _activate(self):
        try:
            self._center()
            self.lift()
            self.focus_force()
            self.grab_set()
        except tk.TclError:
            pass

    def set_modal_height(self, height: int):
        if self._height == height:
            return
        self._height = height
        if self.winfo_ismapped():
            self._center()

    def cancel(self):
        if self._close_command:
            self._close_command()
        elif self.allow_cancel:
            self.destroy()
        else:
            self.app.root.destroy()

    def destroy(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        super().destroy()


class SetupDialog(ModalBase):
    def __init__(
        self,
        app: "GomokuApp",
        difficulty: str,
        allow_cancel: bool,
        mode: str = "pve",
    ):
        super().__init__(app, 710, 730, allow_cancel=allow_cancel)
        self.difficulty = difficulty
        self.mode = mode if mode in ("pve", "local") else "pve"
        self.pending_first: bool | None = None
        self.rps_token = 0
        self.rps_locked = False
        self._build()
        self._sync_difficulty()
        self._sync_mode()

    def _build(self):
        fonts = self.app.fonts
        content = tk.Frame(self.outer, bg=BG)
        content.pack(fill="both", expand=True, padx=34, pady=(25, 28))
        content.columnconfigure(0, weight=1)

        header = tk.Frame(content, bg=BG)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(
            header, text="NEW MATCH", bg=BG, fg=GOLD, font=fonts["kicker"]
        ).pack(anchor="w")
        tk.Label(
            header, text="落子之前", bg=BG, fg=TEXT, font=fonts["serif_30"]
        ).pack(anchor="w", pady=(3, 1))
        tk.Label(
            header,
            text="选择模式，开始这一局。",
            bg=BG,
            fg=MUTED,
            font=fonts["ui_11"],
        ).pack(anchor="w")

        banner = tk.Frame(
            content,
            bg="#160f0c",
            highlightthickness=1,
            highlightbackground="#513128",
            padx=11,
            pady=8,
        )
        banner.grid(row=1, column=0, sticky="ew", pady=(15, 17))
        tk.Label(
            banner,
            text="禁",
            bg="#2b1712",
            fg="#e7b0a2",
            font=fonts["serif_11"],
            width=2,
            height=1,
        ).pack(side="left", padx=(0, 9))
        tk.Label(
            banner,
            text="黑棋禁手：三三 · 四四 · 长连",
            bg="#160f0c",
            fg="#c6b8a6",
            font=fonts["ui_10"],
        ).pack(side="left")
        tk.Label(
            banner,
            text="白棋无禁手",
            bg="#160f0c",
            fg=MUTED_DIM,
            font=fonts["tiny"],
        ).pack(side="right")

        mode_bar = tk.Frame(content, bg=BG)
        mode_bar.grid(row=2, column=0, sticky="ew", pady=(0, 3))
        tk.Label(
            mode_bar, text="模式", bg=BG, fg=MUTED_DIM, font=fonts["tiny"]
        ).pack(side="left", padx=(0, 10))
        self.mode_buttons: dict[str, ModeToggle] = {}
        for key, label in (("pve", "人机对弈"), ("local", "双人同屏")):
            button = ModeToggle(
                mode_bar, key, label, self._choose_mode, fonts["ui_10"]
            )
            button.pack(side="left", padx=(0, 7))
            self.mode_buttons[key] = button
        tk.Label(
            mode_bar,
            text="双人模式：玩家交替执黑执白",
            bg=BG,
            fg=MUTED_DIM,
            font=fonts["tiny"],
        ).pack(side="right")

        self.difficulty_section = tk.Frame(content, bg=BG)
        self.difficulty_section.grid(row=3, column=0, sticky="ew", pady=(15, 0))
        tk.Label(
            self.difficulty_section,
            text="01  选择难度",
            bg=BG,
            fg=MUTED,
            font=fonts["ui_9"],
        ).pack(anchor="w", pady=(0, 8))
        self.difficulty_row = tk.Frame(self.difficulty_section, bg=BG)
        self.difficulty_row.pack(fill="x")
        self.cards: dict[str, DifficultyCard] = {}
        card_data = [
            ("easy", "○", "简单", "轻松热身", "落子随性，偶尔漏看杀招。"),
            ("medium", "◐", "中等", "认真对弈", "会攻会守，识别常见陷阱。"),
            ("hard", "●", "困难", "步步紧逼", "预判数步，擅长双重威胁。"),
        ]
        for index, (level, marker, title, tagline, desc) in enumerate(card_data):
            card = DifficultyCard(
                self.difficulty_row,
                level,
                marker,
                title,
                tagline,
                desc,
                self._choose_difficulty,
                fonts,
            )
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 7, 0))
            self.difficulty_row.columnconfigure(index, weight=1, uniform="diff")
            self.cards[level] = card

        section2 = tk.Frame(content, bg=BG)
        section2.grid(row=4, column=0, sticky="ew", pady=(17, 0))
        self.rps_section_label = tk.Label(
            section2, text="02  猜拳定先手", bg=BG, fg=MUTED, font=fonts["ui_9"]
        )
        self.rps_section_label.pack(anchor="w", pady=(0, 8))

        self.rps_panel = tk.Frame(
            section2,
            bg=PANEL_DARK,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=18,
            pady=13,
        )
        self.rps_panel.pack(fill="x")

        self.hands = tk.Frame(self.rps_panel, bg=PANEL_DARK)
        self.hands.pack()
        self.player_hand = HandSlot(self.hands, "你", fonts)
        self.player_hand.grid(row=0, column=0, padx=8)
        tk.Label(
            self.hands, text="VS", bg=PANEL_DARK, fg=GOLD_DARK, font=fonts["serif_11"]
        ).grid(row=0, column=1, padx=14)
        self.ai_hand = HandSlot(self.hands, "弈者", fonts, ai=True)
        self.ai_hand.grid(row=0, column=2, padx=8)

        self.rps_hint = tk.Label(
            self.rps_panel,
            text="选一个手势 · 赢家执黑先行",
            bg=PANEL_DARK,
            fg=MUTED,
            font=fonts["ui_10"],
            height=2,
        )
        self.rps_hint.pack(fill="x", pady=(7, 4))

        self.gesture_row = tk.Frame(self.rps_panel, bg=PANEL_DARK)
        self.gesture_row.pack(fill="x")
        self.gesture_buttons: dict[str, FlatButton] = {}
        for index, (key, item) in enumerate(RPS.items()):
            button = FlatButton(
                self.gesture_row,
                text=f"{item['icon']}   {item['label']}",
                command=lambda k=key: self._play_rps(k),
                variant="secondary",
                font=fonts["ui_12"],
                pady=10,
            )
            button.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 7, 0))
            self.gesture_row.columnconfigure(index, weight=1)
            self.gesture_buttons[key] = button

        self.local_info = tk.Label(
            self.rps_panel,
            text=(
                "黑棋先行 · 双方轮流落子\n"
                "黑棋禁手仍然生效，白棋长连算胜"
            ),
            bg=PANEL_DARK,
            fg=MUTED,
            font=fonts["ui_10"],
            justify="center",
            height=4,
        )
        self.local_info.pack_forget()

        self.start_button = FlatButton(
            self.rps_panel,
            text="开始对局",
            command=self._start,
            variant="primary",
            font=fonts["ui_12"],
            pady=12,
        )
        self.start_button.pack(fill="x", pady=(11, 0))
        self.start_button.pack_forget()

    def _choose_mode(self, mode: str):
        if mode == self.mode:
            return
        self.mode = mode
        self._sync_mode()

    def _sync_mode(self):
        local = self.mode == "local"
        self.set_modal_height(500 if local else 730)
        for key, button in self.mode_buttons.items():
            button.set_selected(key == self.mode)
        self.rps_token += 1
        self.rps_locked = False
        self.pending_first = None
        for button in self.gesture_buttons.values():
            button.set_enabled(True)

        if local:
            self.difficulty_section.grid_remove()
            self.rps_section_label.configure(text="01  双人对局")
            self.hands.pack_forget()
            self.rps_hint.pack_forget()
            self.gesture_row.pack_forget()
            self.start_button.pack_forget()
            self.local_info.pack(fill="x", pady=(5, 2))
            self.start_button.configure(text="开始双人对局")
            self.start_button.pack(fill="x", pady=(7, 0))
        else:
            self.difficulty_section.grid()
            self.rps_section_label.configure(text="02  猜拳定先手")
            self.local_info.pack_forget()
            self.start_button.pack_forget()
            self.hands.pack_forget()
            self.rps_hint.pack_forget()
            self.gesture_row.pack_forget()
            self.hands.pack()
            self.rps_hint.pack(fill="x", pady=(7, 4))
            self.gesture_row.pack(fill="x")
            self.player_hand.set_icon("?")
            self.ai_hand.set_icon("?")
            self.player_hand.set_highlight(False)
            self.ai_hand.set_highlight(False)
            self.rps_hint.configure(
                text="选一个手势 · 赢家执黑先行", fg=MUTED
            )
            self.start_button.configure(text="开始对局")

    def _choose_difficulty(self, level: str):
        self.difficulty = level
        self._sync_difficulty()

    def _sync_difficulty(self):
        for level, card in self.cards.items():
            card.set_selected(level == self.difficulty)

    def _play_rps(self, player_gesture: str):
        if self.mode != "pve" or self.rps_locked or self.pending_first is not None:
            return
        self.rps_locked = True
        for button in self.gesture_buttons.values():
            button.set_enabled(False)
        self.player_hand.set_icon(RPS[player_gesture]["icon"])
        self.ai_hand.set_icon("?")
        self.player_hand.set_highlight(False)
        self.ai_hand.set_highlight(False)
        self.rps_hint.configure(text="出拳中…", fg=MUTED)
        token = self.rps_token

        def reveal():
            if token != self.rps_token or not self.winfo_exists():
                return
            ai_gesture = random.choice(list(RPS))
            self.ai_hand.set_icon(RPS[ai_gesture]["icon"])
            if player_gesture == ai_gesture:
                self.rps_locked = False
                self.rps_hint.configure(
                    text=f"平局！你们都出了{RPS[player_gesture]['label']}，再猜一次",
                    fg=GOLD,
                )
                for button in self.gesture_buttons.values():
                    button.set_enabled(True)
                return

            player_wins = RPS[player_gesture]["beats"] == ai_gesture
            self.pending_first = player_wins
            if player_wins:
                self.player_hand.set_highlight(True)
                self.rps_hint.configure(
                    text=(
                        f"你出{RPS[player_gesture]['label']}，弈者出{RPS[ai_gesture]['label']}"
                        " —— 你赢了，执黑先行"
                    ),
                    fg=GOLD_BRIGHT,
                )
                self.start_button.configure(text="我执黑 · 开始对局")
            else:
                self.ai_hand.set_highlight(True)
                self.rps_hint.configure(
                    text=(
                        f"你出{RPS[player_gesture]['label']}，弈者出{RPS[ai_gesture]['label']}"
                        " —— 弈者执黑先行"
                    ),
                    fg="#dc9c8d",
                )
                self.start_button.configure(text="弈者执黑 · 开始对局")
            self.gesture_row.pack_forget()
            self.start_button.pack(fill="x", pady=(11, 0))

        self.after(470, reveal)

    def _start(self):
        if self.mode == "local":
            player_first = True
            mode = "local"
        else:
            if self.pending_first is None:
                return
            player_first = self.pending_first
            mode = "pve"
        difficulty = self.difficulty
        self.destroy()
        self.app.start_new_game(
            player_first=player_first, difficulty=difficulty, mode=mode
        )


class ResultDialog(ModalBase):
    def __init__(self, app: "GomokuApp", winner: int, reason: str | None = None):
        super().__init__(app, 420, 272, allow_cancel=True)
        self.winner = winner
        self.reason = reason
        self._build()

    def _build(self):
        fonts = self.app.fonts
        local = self.app.mode == "local"
        draw = self.winner == 0
        overline = bool(self.app.win_line and len(self.app.win_line) > 5)

        if draw:
            kicker = "DRAW"
            title = "平局"
            text = "棋盘已满，势均力敌。"
        elif local:
            black_wins = self.winner == engine.BLACK
            kicker = "BLACK WINS" if black_wins else "WHITE WINS"
            title = "黑胜" if black_wins else "白胜"
            if self.reason == "noLegal":
                text = "黑棋已无合法落点，本局结束。"
            elif overline:
                text = "白棋以长连取胜。"
            else:
                text = "黑棋连成五子。" if black_wins else "白棋连成五子。"
        else:
            win = self.winner == self.app.player_color
            kicker = "VICTORY" if win else "DEFEAT"
            title = "你赢了" if win else "弈者获胜"
            if overline:
                text = "长连取胜，漂亮的一局。" if win else "弈者以长连取胜，再来一局？"
            else:
                text = "五子连珠，漂亮的一局。" if win else "这一局棋差一着，调整思路再来。"

        body = tk.Frame(self.outer, bg=BG)
        body.pack(fill="both", expand=True, padx=30, pady=26)
        tk.Label(body, text=kicker, bg=BG, fg=GOLD, font=fonts["kicker"]).pack()
        color = GOLD_BRIGHT if draw or local or title == "你赢了" else "#d8d0c0"
        tk.Label(body, text=title, bg=BG, fg=color, font=fonts["serif_30"]).pack(
            pady=(5, 7)
        )
        tk.Label(
            body,
            text=text,
            bg=BG,
            fg=MUTED,
            font=fonts["ui_11"],
            wraplength=330,
            justify="center",
        ).pack()
        actions = tk.Frame(body, bg=BG)
        actions.pack(pady=(22, 0))
        FlatButton(
            actions,
            text="再来一局",
            command=self._rematch,
            variant="primary",
            font=fonts["ui_11"],
            pady=9,
        ).pack(side="left", padx=(0, 8))
        FlatButton(
            actions,
            text="看看棋盘",
            command=self.destroy,
            variant="ghost",
            font=fonts["ui_11"],
            pady=9,
        ).pack(side="left")

    def _rematch(self):
        self.destroy()
        self.app.open_setup()


class RulesDialog(ModalBase):
    def __init__(self, app: "GomokuApp"):
        super().__init__(app, 590, 480, allow_cancel=True)
        fonts = app.fonts
        body = tk.Frame(self.outer, bg=BG)
        body.pack(fill="both", expand=True, padx=32, pady=28)
        tk.Label(body, text="HOW TO PLAY", bg=BG, fg=GOLD, font=fonts["kicker"]).pack(
            anchor="w"
        )
        tk.Label(
            body, text="五子连珠 · 有禁手", bg=BG, fg=TEXT, font=fonts["serif_27"]
        ).pack(anchor="w", pady=(4, 16))

        items = [
            ("01", "棋盘为 14 × 14，黑棋先行，双方轮流落子。"),
            ("02", "黑棋必须恰好连成五子才能获胜；白棋连成五子或长连均获胜。"),
            ("03", "黑棋禁止三三、四四、长连。若黑棋一手同时成五并形成禁手，五最大，判黑胜。"),
            ("04", "人机模式先与 AI 猜拳，赢家执黑；双人同屏模式由玩家轮流执黑执白，黑棋先行。"),
            ("05", "简单、中等、困难三档 AI，均遵守禁手规则。困难模式会搜索后续变化。"),
        ]
        list_frame = tk.Frame(
            body,
            bg=PANEL_DARK,
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        list_frame.pack(fill="x")
        for index, (number, text) in enumerate(items):
            row = tk.Frame(list_frame, bg=PANEL_DARK)
            row.pack(fill="x", padx=14, pady=9)
            tk.Label(
                row, text=number, bg=PANEL_DARK, fg=GOLD_DARK, font=fonts["serif_10"], width=3
            ).pack(side="left", anchor="n")
            tk.Label(
                row,
                text=text,
                bg=PANEL_DARK,
                fg=MUTED,
                font=fonts["ui_10"],
                wraplength=470,
                justify="left",
                anchor="w",
            ).pack(side="left", fill="x", expand=True)
            if index < len(items) - 1:
                tk.Frame(list_frame, bg=BORDER, height=1).pack(fill="x", padx=14)

        FlatButton(
            body,
            text="明白了",
            command=self.destroy,
            variant="primary",
            font=fonts["ui_11"],
            pady=11,
        ).pack(fill="x", pady=(20, 0))


# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------


class BoardView:
    SHADOW = 15

    def __init__(self, canvas: tk.Canvas, app: "GomokuApp"):
        self.canvas = canvas
        self.app = app
        self.board_photo: ImageTk.PhotoImage | None = None
        self.board_size_key: tuple[int, int, int] | None = None
        self.stone_photos: dict[tuple[int, int], ImageTk.PhotoImage] = {}
        self.hover_move: int | None = None
        self.forbidden_move: int | None = None
        self._forbidden_job: str | None = None
        self._resize_job: str | None = None
        self.metrics: dict[str, float] | None = None
        self._stone_refs: list[ImageTk.PhotoImage] = []
        canvas.bind("<Configure>", self._on_configure)
        canvas.bind("<Motion>", self._on_motion)
        canvas.bind("<Leave>", self._on_leave)
        canvas.bind("<Button-1>", self._on_click)

    def _on_configure(self, _event=None):
        if self._resize_job:
            self.canvas.after_cancel(self._resize_job)
        self._resize_job = self.canvas.after(90, self.redraw)

    def _compute_metrics(self) -> dict[str, float] | None:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width < 220 or height < 220:
            return None
        outer = int(min(width, height) * 0.92)
        outer = max(260, outer)
        shadow = max(10, int(outer * 0.023))
        frame = max(4, int(outer * 0.014))
        wood = outer - 2 * frame
        pad = wood * 0.038
        step = (wood - 2 * pad) / (engine.SIZE - 1)
        total = outer + 2 * shadow
        x0 = (width - total) / 2
        y0 = (height - total) / 2
        grid_x = x0 + shadow + frame + pad
        grid_y = y0 + shadow + frame + pad
        return {
            "outer": outer,
            "shadow": shadow,
            "frame": frame,
            "wood": wood,
            "pad": pad,
            "step": step,
            "total": total,
            "x0": x0,
            "y0": y0,
            "grid_x": grid_x,
            "grid_y": grid_y,
            "stone": step * 0.84,
        }

    def _build_board_photo(self, m: dict[str, float]) -> ImageTk.PhotoImage:
        outer = int(m["outer"])
        shadow = int(m["shadow"])
        frame = int(m["frame"])
        wood = int(m["wood"])
        step = m["step"]
        total = int(m["total"])
        scale = 2
        W = total * scale
        img = Image.new("RGBA", (W, W), (0, 0, 0, 0))

        # Soft shadow behind the board.
        shadow_layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        ds = ImageDraw.Draw(shadow_layer)
        sx = (shadow + 3) * scale
        sy = (shadow + 6) * scale
        ex = (shadow + outer + 3) * scale
        ey = (shadow + outer + 6) * scale
        radius = int(outer * 0.035 * scale)
        ds.rounded_rectangle([sx, sy, ex, ey], radius=radius, fill=(0, 0, 0, 145))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(7 * scale))
        img.alpha_composite(shadow_layer)

        draw = ImageDraw.Draw(img)
        # Outer frame.
        fx1 = shadow * scale
        fy1 = shadow * scale
        fx2 = (shadow + outer) * scale
        fy2 = (shadow + outer) * scale
        draw.rounded_rectangle(
            [fx1, fy1, fx2, fy2],
            radius=radius,
            fill=WOOD_FRAME,
            outline=(95, 71, 43, 255),
            width=max(1, 2 * scale),
        )

        # Wood texture.
        wood_x = (shadow + frame) * scale
        wood_y = (shadow + frame) * scale
        wood_size = wood * scale
        small = Image.new("RGB", (120, 120))
        pix = small.load()
        for y in range(120):
            for x in range(120):
                t = (x * 0.32 + y * 0.68) / 119
                base = _mix((228, 190, 135), (187, 137, 74), t)
                light = max(0.0, 1.0 - math.hypot((x - 33) / 110, (y - 20) / 90))
                grain = math.sin(x * 1.9 + y * 0.12) * 2.5
                pix[x, y] = tuple(
                    max(0, min(255, int(value + light * 14 + grain)))
                    for value in base
                )
        wood_img = small.resize((wood_size, wood_size), Image.Resampling.BICUBIC).convert(
            "RGBA"
        )
        mask = Image.new("L", (wood_size, wood_size), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle(
            [0, 0, wood_size - 1, wood_size - 1],
            radius=max(2, int(outer * 0.028 * scale)),
            fill=255,
        )
        wood_img.putalpha(mask)
        img.alpha_composite(wood_img, (wood_x, wood_y))

        # Grid only: no extra decorative lines or star points.
        d = ImageDraw.Draw(img)
        grid_start_x = wood_x + m["pad"] * scale
        grid_start_y = wood_y + m["pad"] * scale
        grid_end_x = grid_start_x + step * (engine.SIZE - 1) * scale
        grid_end_y = grid_start_y + step * (engine.SIZE - 1) * scale
        line_color = (72, 45, 15, 180)
        line_width = max(1, int(1.0 * scale))
        for i in range(engine.SIZE):
            p = grid_start_x + i * step * scale
            q = grid_start_y + i * step * scale
            d.line([(p, grid_start_y), (p, grid_end_y)], fill=line_color, width=line_width)
            d.line([(grid_start_x, q), (grid_end_x, q)], fill=line_color, width=line_width)

        # Inner rim.
        draw.rounded_rectangle(
            [fx1 + scale, fy1 + scale, fx2 - scale, fy2 - scale],
            radius=radius,
            outline=(242, 210, 155, 60),
            width=max(1, scale),
        )

        final = img.resize((total, total), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(final)

    def _build_stone_photo(self, diameter: int, player: int) -> ImageTk.PhotoImage:
        scale = 3
        core = max(8, int(diameter * scale))
        pad = max(2, int(core * 0.10))
        total = core + 2 * pad
        img = Image.new("RGBA", (total, total), (0, 0, 0, 0))

        shadow = Image.new("RGBA", (total, total), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse(
            [pad + 2 * scale, pad + 3 * scale, pad + core + 2 * scale, pad + core + 3 * scale],
            fill=(0, 0, 0, 90),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(2 * scale))
        img.alpha_composite(shadow)

        if player == engine.BLACK:
            light = (110, 110, 110)
            dark = (3, 3, 3)
            rim = (130, 130, 130, 70)
        else:
            light = (255, 254, 248)
            dark = (188, 179, 162)
            rim = (120, 101, 70, 55)

        pixels = Image.new("RGBA", (core, core), (0, 0, 0, 0))
        px = pixels.load()
        c = (core - 1) / 2
        radius = core / 2 - 0.5
        for y in range(core):
            for x in range(core):
                dx = (x - c) / radius
                dy = (y - c) / radius
                distance = math.hypot(dx + 0.28, dy + 0.34)
                if math.hypot(dx, dy) > 1.0:
                    continue
                t = min(1.0, distance / 1.35)
                color = _mix(light, dark, t)
                if player == engine.BLACK:
                    alpha = 255
                else:
                    alpha = 255
                px[x, y] = (*color, alpha)
        mask = Image.new("L", (core, core), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse([0, 0, core - 1, core - 1], fill=255)
        # Pixel loop already alpha-clipped; mask keeps the edge smooth.
        pixels.putalpha(mask)
        img.alpha_composite(pixels, (pad, pad))
        d = ImageDraw.Draw(img)
        d.ellipse(
            [pad, pad, pad + core - 1, pad + core - 1],
            outline=rim,
            width=max(1, scale),
        )
        return ImageTk.PhotoImage(
            img.resize((total // scale, total // scale), Image.Resampling.LANCZOS)
        )

    def _ensure_assets(self, m: dict[str, float]):
        key = (int(m["outer"]), int(m["step"] * 100))
        if self.board_size_key != key:
            self.board_photo = self._build_board_photo(m)
            self.board_size_key = key
        diameter = max(16, int(round(m["stone"])))
        for player in (engine.BLACK, engine.WHITE):
            if (diameter, player) not in self.stone_photos:
                self.stone_photos[(diameter, player)] = self._build_stone_photo(
                    diameter, player
                )

    def redraw(self):
        self._resize_job = None
        m = self._compute_metrics()
        if not m:
            return
        self.metrics = m
        self._ensure_assets(m)
        canvas = self.canvas
        canvas.delete("all")
        self._stone_refs.clear()
        canvas.create_image(m["x0"], m["y0"], image=self.board_photo, anchor="nw")

        board = self.app.board
        diameter = int(round(m["stone"]))
        for entry in self.app.history:
            move = entry["move"]
            row, col = engine.row_of(move), engine.col_of(move)
            cx = m["grid_x"] + col * m["step"]
            cy = m["grid_y"] + row * m["step"]
            photo = self.stone_photos[(diameter, entry["player"])]
            self._stone_refs.append(photo)
            canvas.create_image(cx, cy, image=photo, anchor="center")

        if self.app.win_line:
            self._draw_win(m)
        else:
            for entry in self.app.history:
                if entry["move"] == self.app.last_move:
                    self._draw_last_marker(m, entry["player"])
                    break

        if self.forbidden_move is not None:
            self._draw_forbidden(m)
        self._draw_hover(m)

    def _draw_last_marker(self, m: dict[str, float], player: int):
        move = self.app.last_move
        if move < 0:
            return
        cx = m["grid_x"] + engine.col_of(move) * m["step"]
        cy = m["grid_y"] + engine.row_of(move) * m["step"]
        r = max(2.0, m["stone"] * 0.075)
        color = GOLD_BRIGHT if player == engine.BLACK else "#6f4e28"
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")

    def _draw_win(self, m: dict[str, float]):
        line = self.app.win_line
        if not line:
            return
        points = []
        for move in line:
            points.extend(
                [
                    m["grid_x"] + engine.col_of(move) * m["step"],
                    m["grid_y"] + engine.row_of(move) * m["step"],
                ]
            )
        self.canvas.create_line(
            *points,
            fill="#b47d32",
            width=max(4, int(m["step"] * 0.11)),
            capstyle="round",
        )
        self.canvas.create_line(
            *points,
            fill=GOLD_BRIGHT,
            width=max(2, int(m["step"] * 0.035)),
            capstyle="round",
        )
        for move in line:
            cx = m["grid_x"] + engine.col_of(move) * m["step"]
            cy = m["grid_y"] + engine.row_of(move) * m["step"]
            r = m["stone"] * 0.53
            self.canvas.create_oval(
                cx - r,
                cy - r,
                cx + r,
                cy + r,
                outline=GOLD_BRIGHT,
                width=2,
            )

    def _draw_forbidden(self, m: dict[str, float]):
        move = self.forbidden_move
        if move is None:
            return
        cx = m["grid_x"] + engine.col_of(move) * m["step"]
        cy = m["grid_y"] + engine.row_of(move) * m["step"]
        r = m["step"] * 0.46
        self.canvas.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill="#7d2c20",
            stipple="gray50",
            outline="#d06a55",
            width=2,
            tags="forbidden",
        )
        d = r * 0.45
        self.canvas.create_line(
            cx - d,
            cy - d,
            cx + d,
            cy + d,
            fill="#ffd0c2",
            width=2,
            tags="forbidden",
        )
        self.canvas.create_line(
            cx - d,
            cy + d,
            cx + d,
            cy - d,
            fill="#ffd0c2",
            width=2,
            tags="forbidden",
        )

    def _draw_hover(self, m: dict[str, float] | None = None):
        self.canvas.delete("hover")
        if self.hover_move is None:
            return
        if not self.app.player_can_play():
            return
        if self.app.board[self.hover_move] != engine.EMPTY:
            return
        if m is None:
            m = self.metrics
        if not m:
            return
        cx = m["grid_x"] + engine.col_of(self.hover_move) * m["step"]
        cy = m["grid_y"] + engine.row_of(self.hover_move) * m["step"]
        r = m["stone"] * 0.46
        color = "#111111" if self.app.ghost_player() == engine.BLACK else "#f3eee2"
        self.canvas.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill=color,
            stipple="gray25",
            outline="",
            tags="hover",
        )

    def set_hover(self, move: int | None):
        if self.hover_move == move:
            return
        self.hover_move = move
        self._draw_hover()

    def _hit_test(self, x: float, y: float) -> int | None:
        m = self.metrics
        if not m:
            return None
        col = round((x - m["grid_x"]) / m["step"])
        row = round((y - m["grid_y"]) / m["step"])
        if not (0 <= row < engine.SIZE and 0 <= col < engine.SIZE):
            return None
        cx = m["grid_x"] + col * m["step"]
        cy = m["grid_y"] + row * m["step"]
        if math.hypot(x - cx, y - cy) > m["step"] * 0.62:
            return None
        return row * engine.SIZE + col

    def _on_motion(self, event):
        move = self._hit_test(event.x, event.y)
        self.set_hover(move)

    def _on_leave(self, _event=None):
        self.set_hover(None)

    def _on_click(self, event):
        move = self._hit_test(event.x, event.y)
        if move is not None:
            self.app.on_board_click(move)

    def flash_forbidden(self, move: int):
        self.forbidden_move = move
        if self._forbidden_job:
            self.canvas.after_cancel(self._forbidden_job)
        self.redraw()
        self._forbidden_job = self.canvas.after(900, self._clear_forbidden)

    def _clear_forbidden(self):
        self._forbidden_job = None
        self.forbidden_move = None
        self.redraw()


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------


class GomokuApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.configure(bg=BG)
        self.root.minsize(1000, 700)
        self._set_icon()

        self._init_fonts()
        self._init_state()
        self._build_layout()
        self._bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(180, self.open_setup)

    def _set_icon(self):
        icon_path = resource_path(os.path.join("assets", "gomoku.ico"))
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(default=icon_path)
            except tk.TclError:
                pass

    def _init_fonts(self):
        ui = _pick_font(
            self.root,
            ["Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI"],
            "TkDefaultFont",
        )
        serif = _pick_font(
            self.root,
            ["SimSun", "STSong", "Songti SC", "Noto Serif CJK SC", "Georgia"],
            "TkDefaultFont",
        )
        emoji = _pick_font(
            self.root, ["Segoe UI Emoji", "Segoe UI Symbol", "Segoe UI"], ui
        )
        self.fonts = {
            "ui_18": tkfont.Font(root=self.root, family=ui, size=18),
            "ui_12": tkfont.Font(root=self.root, family=ui, size=12, weight="bold"),
            "ui_11": tkfont.Font(root=self.root, family=ui, size=11),
            "ui_10": tkfont.Font(root=self.root, family=ui, size=10),
            "ui_9": tkfont.Font(root=self.root, family=ui, size=9),
            "small": tkfont.Font(root=self.root, family=ui, size=9),
            "tiny": tkfont.Font(root=self.root, family=ui, size=8),
            "kicker": tkfont.Font(root=self.root, family=ui, size=8, weight="bold"),
            "serif_30": tkfont.Font(root=self.root, family=serif, size=30),
            "serif_27": tkfont.Font(root=self.root, family=serif, size=27),
            "serif_17": tkfont.Font(root=self.root, family=serif, size=17),
            "serif_11": tkfont.Font(root=self.root, family=serif, size=11),
            "serif_10": tkfont.Font(root=self.root, family=serif, size=10),
            "emoji_30": tkfont.Font(root=self.root, family=emoji, size=30),
            "emoji_20": tkfont.Font(root=self.root, family=emoji, size=20),
        }

    def _init_state(self):
        self.board = engine.create_board()
        self.history: list[dict[str, int]] = []
        self.player_color = engine.BLACK
        self.ai_color = engine.WHITE
        self.current = engine.BLACK
        self.phase = "idle"
        self.winner = 0
        self.win_line: list[int] | None = None
        self.last_move = -1
        self.difficulty = "medium"
        self.mode = "pve"
        self.game_started = False
        self.game_token = 0
        self.ai_thread: threading.Thread | None = None
        self.ai_queue: queue.Queue | None = None
        self.ai_cancel = threading.Event()
        self.ai_poll_job: str | None = None
        self.thinking_job: str | None = None
        self.thinking_phase = 0
        self.temp_status_job: str | None = None
        self.result_dialog: ResultDialog | None = None
        self.setup_dialog: SetupDialog | None = None
        self.rules_dialog: RulesDialog | None = None

    def _build_layout(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        header = tk.Frame(self.root, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(18, 8))
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left")
        seal = tk.Canvas(brand, width=46, height=46, bg=BG, highlightthickness=0)
        seal.pack(side="left", padx=(0, 13))
        draw_round_rect(seal, 1, 1, 45, 45, 12, "#202a20", "#6f5a36", 1)
        seal.create_text(
            23,
            24,
            text="五",
            fill=GOLD_BRIGHT,
            font=self.fonts["serif_17"],
        )
        brand_copy = tk.Frame(brand, bg=BG)
        brand_copy.pack(side="left")
        tk.Label(
            brand_copy, text="五子棋", bg=BG, fg=TEXT, font=self.fonts["serif_17"]
        ).pack(anchor="w")
        tk.Label(
            brand_copy,
            text="GOMOKU · 14 × 14 · 禁手",
            bg=BG,
            fg=MUTED_DIM,
            font=self.fonts["kicker"],
        ).pack(anchor="w", pady=(2, 0))

        FlatButton(
            header,
            text="玩法说明",
            command=self.open_rules,
            variant="ghost",
            font=self.fonts["ui_9"],
            pady=7,
            padx=13,
        ).pack(side="right")

        main = tk.Frame(self.root, bg=BG)
        main.grid(row=1, column=0, sticky="nsew", padx=30)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, minsize=314, weight=0)
        main.grid_rowconfigure(0, weight=1)

        board_column = tk.Frame(main, bg=BG)
        board_column.grid(row=0, column=0, sticky="nsew", padx=(0, 26))
        board_column.grid_rowconfigure(0, weight=1)
        board_column.grid_columnconfigure(0, weight=1)

        self.board_canvas = tk.Canvas(
            board_column,
            bg=BG,
            highlightthickness=0,
            bd=0,
        )
        self.board_canvas.grid(row=0, column=0, sticky="nsew")
        self.board_view = BoardView(self.board_canvas, self)

        status = tk.Frame(board_column, bg=BG, height=36)
        status.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        status.grid_propagate(False)
        self.status_dot = tk.Canvas(status, width=18, height=18, bg=BG, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 8))
        self.status_label = tk.Label(
            status,
            text="准备开局",
            bg=BG,
            fg=MUTED,
            font=self.fonts["ui_10"],
        )
        self.status_label.pack(side="left")
        self.thinking_label = tk.Label(
            status, text="", bg=BG, fg=GOLD_DARK, font=self.fonts["ui_10"]
        )
        self.thinking_label.pack(side="left", padx=(4, 0))

        self._build_sidebar(main)

        footer = tk.Frame(self.root, bg=BG)
        footer.grid(row=2, column=0, sticky="ew", padx=30, pady=(4, 15))
        tk.Label(
            footer,
            text="十四路棋盘  ·  黑棋禁手  ·  白棋长连算胜",
            bg=BG,
            fg=MUTED_DIM,
            font=self.fonts["tiny"],
        ).pack()

        self.update_ui()
        self.board_view.redraw()

    def _build_sidebar(self, parent: tk.Frame):
        sidebar = tk.Frame(parent, bg=BG, width=314)
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.grid_propagate(False)

        match_panel = tk.Frame(
            sidebar,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=16,
            pady=15,
        )
        match_panel.pack(fill="x")

        heading = tk.Frame(match_panel, bg=PANEL)
        heading.pack(fill="x")
        tk.Label(
            heading, text="本局对弈", bg=PANEL, fg=MUTED, font=self.fonts["tiny"]
        ).pack(side="left")
        self.difficulty_pill = tk.Label(
            heading,
            text="中等",
            bg="#2b2418",
            fg=GOLD_BRIGHT,
            font=self.fonts["tiny"],
            padx=8,
            pady=3,
        )
        self.difficulty_pill.pack(side="right")

        self.human_card = self._build_player_card(
            match_panel, "你", "human", is_ai=False
        )
        self.human_card.pack(fill="x", pady=(13, 4))
        vs = tk.Frame(match_panel, bg=PANEL)
        vs.pack(fill="x", padx=8)
        tk.Frame(vs, bg=BORDER, height=1).pack(side="left", fill="x", expand=True)
        tk.Label(
            vs, text="VS", bg=PANEL, fg=MUTED_DIM, font=self.fonts["tiny"]
        ).pack(side="left", padx=8)
        tk.Frame(vs, bg=BORDER, height=1).pack(side="left", fill="x", expand=True)
        self.ai_card = self._build_player_card(
            match_panel, "弈者", "ai", is_ai=True
        )
        self.ai_card.pack(fill="x", pady=(4, 0))

        stats = tk.Frame(
            match_panel,
            bg="#0c1510",
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        stats.pack(fill="x", pady=(14, 0))
        stats.grid_columnconfigure(0, weight=1)
        stats.grid_columnconfigure(1, weight=1)
        stat1 = tk.Frame(stats, bg="#0c1510", padx=10, pady=8)
        stat1.grid(row=0, column=0, sticky="ew")
        tk.Label(stat1, text="手数", bg="#0c1510", fg=MUTED_DIM, font=self.fonts["tiny"]).pack(anchor="w")
        self.move_count_label = tk.Label(
            stat1, text="0", bg="#0c1510", fg=TEXT, font=self.fonts["serif_17"]
        )
        self.move_count_label.pack(anchor="w")
        stat2 = tk.Frame(stats, bg="#0c1510", padx=10, pady=8)
        stat2.grid(row=0, column=1, sticky="ew")
        tk.Label(stat2, text="状态", bg="#0c1510", fg=MUTED_DIM, font=self.fonts["tiny"]).pack(anchor="w")
        self.match_state_label = tk.Label(
            stat2, text="待开局", bg="#0c1510", fg=TEXT, font=self.fonts["serif_17"]
        )
        self.match_state_label.pack(anchor="w")

        actions = tk.Frame(sidebar, bg=BG)
        actions.pack(fill="x", pady=(11, 0))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        self.undo_button = FlatButton(
            actions,
            text="悔棋",
            command=self.undo_move,
            variant="secondary",
            font=self.fonts["ui_10"],
            pady=10,
        )
        self.undo_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.restart_button = FlatButton(
            actions,
            text="重新猜拳",
            command=self.open_setup,
            variant="primary",
            font=self.fonts["ui_10"],
            pady=10,
        )
        self.restart_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        tip = tk.Frame(
            sidebar,
            bg=PANEL,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=16,
            pady=14,
        )
        tip.pack(fill="x", pady=(12, 0))
        tk.Label(
            tip, text="连成五子", bg=PANEL, fg=TEXT, font=self.fonts["serif_17"]
        ).pack(anchor="w")
        tk.Label(
            tip,
            text="黑棋需恰好连成五子；白棋五子或长连均获胜。",
            bg=PANEL,
            fg=MUTED,
            font=self.fonts["tiny"],
            wraplength=265,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))
        tk.Label(
            tip,
            text="困难模式会预判数步，小心冲四与双重威胁。",
            bg=PANEL,
            fg=MUTED_DIM,
            font=self.fonts["tiny"],
            wraplength=265,
            justify="left",
        ).pack(anchor="w", pady=(5, 0))
        tk.Frame(tip, bg=BORDER, height=1).pack(fill="x", pady=(9, 7))
        tk.Label(
            tip,
            text="黑棋禁手：三三 · 四四 · 长连",
            bg=PANEL,
            fg="#c8a79a",
            font=self.fonts["tiny"],
        ).pack(anchor="w")

        self.mode_note_label = tk.Label(
            sidebar,
            text="✊  每局由猜拳决定谁执黑先行",
            bg=BG,
            fg=MUTED_DIM,
            font=self.fonts["tiny"],
        )
        self.mode_note_label.pack(pady=(11, 0))

    def _build_player_card(self, parent: tk.Frame, name: str, key: str, is_ai: bool):
        card = tk.Frame(
            parent,
            bg=CARD,
            highlightthickness=1,
            highlightbackground=BORDER,
            padx=9,
            pady=8,
        )
        avatar = tk.Canvas(card, width=38, height=38, bg=CARD, highlightthickness=0)
        avatar.pack(side="left", padx=(0, 10))
        copy = tk.Frame(card, bg=CARD)
        copy.pack(side="left")
        name_label = tk.Label(
            copy, text=name, bg=CARD, fg=TEXT, font=self.fonts["ui_11"]
        )
        name_label.pack(anchor="w")
        color_label = tk.Label(
            copy,
            text="执白" if is_ai else "执黑",
            bg=CARD,
            fg=MUTED_DIM,
            font=self.fonts["tiny"],
        )
        color_label.pack(anchor="w", pady=(2, 0))
        turn_pill = tk.Label(
            card,
            text="思考中" if is_ai else "落子中",
            bg="#2b2418",
            fg=GOLD,
            font=self.fonts["tiny"],
            padx=7,
            pady=2,
        )
        # Stored and packed only when this side is active.
        if key == "human":
            self.human_avatar = avatar
            self.human_copy = copy
            self.human_color_label = color_label
            self.human_turn_pill = turn_pill
            self.human_name_label = name_label
        else:
            self.ai_avatar = avatar
            self.ai_copy = copy
            self.ai_color_label = color_label
            self.ai_turn_pill = turn_pill
            self.ai_name_label = name_label
        self._draw_avatar(avatar, "你" if not is_ai else "AI", is_ai, active=False)
        return card

    def _draw_avatar(
        self,
        canvas: tk.Canvas,
        text: str,
        is_ai: bool,
        active: bool,
        local: bool = False,
        black_side: bool = False,
    ):
        canvas.delete("all")
        bg = CARD_ACTIVE if active else CARD
        canvas.configure(bg=bg)
        if local:
            if black_side:
                fill, outline, fg = "#151515", "#9f895f", "#f3ecdd"
            else:
                fill, outline, fg = "#f0eadc", "#b9a98d", "#2a1c0c"
        elif is_ai:
            fill, outline, fg = "#b98643", "#efd199", "#2a1c0c"
        else:
            fill, outline, fg = "#2d4034", "#536658", "#f2e6d1"
        canvas.create_oval(2, 2, 36, 36, fill=fill, outline=outline, width=1)
        canvas.create_text(
            19,
            20,
            text=text,
            fill=fg,
            font=self.fonts["serif_10"] if is_ai else self.fonts["serif_11"],
        )

    def _bind_keys(self):
        self.root.bind("<Control-z>", lambda _event: self.undo_move())
        self.root.bind("<F2>", lambda _event: self.open_setup())
        self.root.bind("<Escape>", self._escape)

    def _escape(self, _event=None):
        if self.setup_dialog and self.setup_dialog.winfo_exists():
            self.setup_dialog.cancel()
        elif self.rules_dialog and self.rules_dialog.winfo_exists():
            self.rules_dialog.cancel()
        elif self.result_dialog and self.result_dialog.winfo_exists():
            self.result_dialog.destroy()

    # ------------------------------------------------------------------
    # Game flow
    # ------------------------------------------------------------------

    def open_setup(self):
        if self.phase == "ai":
            return
        if self.result_dialog and self.result_dialog.winfo_exists():
            self.result_dialog.destroy()
            self.result_dialog = None
        if self.setup_dialog and self.setup_dialog.winfo_exists():
            self.setup_dialog.lift()
            return
        allow_cancel = self.game_started
        self.setup_dialog = SetupDialog(
            self, self.difficulty, allow_cancel, mode=self.mode
        )

    def open_rules(self):
        if self.rules_dialog and self.rules_dialog.winfo_exists():
            self.rules_dialog.lift()
            return
        self.rules_dialog = RulesDialog(self)

    def start_new_game(self, player_first: bool, difficulty: str, mode: str = "pve"):
        self.game_token += 1
        self.ai_cancel.set()
        self._cancel_thinking()
        if self.result_dialog and self.result_dialog.winfo_exists():
            self.result_dialog.destroy()
        self.result_dialog = None
        self.mode = mode if mode in ("pve", "local") else "pve"
        self.difficulty = difficulty
        if self.mode == "local":
            self.player_color = engine.BLACK
            self.ai_color = engine.WHITE
        else:
            self.player_color = engine.BLACK if player_first else engine.WHITE
            self.ai_color = engine.other(self.player_color)
        self.board = engine.create_board()
        self.history = []
        self.current = engine.BLACK
        self.phase = "playing"
        self.winner = 0
        self.win_line = None
        self.last_move = -1
        self.game_started = True
        self._clear_temp_status()
        self.update_ui()
        self.board_view.redraw()
        if self.mode == "pve" and self.current == self.ai_color:
            self.root.after(260, self.schedule_ai)

    def player_can_play(self) -> bool:
        if not self.game_started or self.phase != "playing":
            return False
        if self.mode == "local":
            return True
        return self.current == self.player_color

    def ghost_player(self) -> int:
        return self.current if self.mode == "local" else self.player_color

    def on_board_click(self, move: int):
        if not self.player_can_play():
            return
        if self.board[move] != engine.EMPTY:
            return
        actor = self.current if self.mode == "local" else self.player_color
        analysis = engine.analyze_move(self.board, move, actor)
        if not analysis.legal:
            if analysis.forbidden:
                labels = analysis.reason_text or "禁手"
                self.show_temp_status(f"{labels}禁手 · 黑棋不能落在这里", 2100)
                self.board_view.flash_forbidden(move)
            return

        self._clear_temp_status()
        self._place_move(move, actor)
        if (
            self.mode == "pve"
            and self.phase == "playing"
            and self.current == self.ai_color
        ):
            self.schedule_ai()

    def _place_move(self, move: int, player: int):
        if not (0 <= move < engine.SIZE * engine.SIZE):
            return False
        if self.board[move] != engine.EMPTY:
            return False
        if player == engine.BLACK and not engine.is_legal_move(self.board, move, player):
            return False

        self.board[move] = player
        self.last_move = move
        self.history.append(
            {
                "move": move,
                "row": engine.row_of(move),
                "col": engine.col_of(move),
                "player": player,
            }
        )
        self.board_view.redraw()

        win_line = engine.check_win(self.board, move, player)
        if win_line:
            self._end_game(player, list(win_line))
            return True
        if engine.is_board_full(self.board):
            self._end_game(0, None)
            return True

        self.current = engine.other(player)
        self.phase = "playing"
        self.update_ui()
        return True

    def _end_game(self, winner: int, win_line: list[int] | None):
        self.phase = "over"
        self.winner = winner
        self.win_line = win_line
        self.game_token += 1
        self.ai_cancel.set()
        self._cancel_thinking()
        self.update_ui()
        self.board_view.redraw()
        self.root.after(700, self._show_result)

    def _show_result(self):
        if self.phase != "over":
            return
        if self.setup_dialog and self.setup_dialog.winfo_exists():
            return
        if self.result_dialog and self.result_dialog.winfo_exists():
            return
        self.result_dialog = ResultDialog(self, self.winner)

    def schedule_ai(self):
        if self.mode != "pve":
            return
        if not self.game_started or self.phase != "playing":
            return
        if self.current != self.ai_color:
            return
        self.phase = "ai"
        self.update_ui()
        token = self.game_token
        board_copy = self.board[:]
        ai_color = self.ai_color
        difficulty = self.difficulty
        started = time.monotonic()
        self.ai_cancel.set()
        cancel = threading.Event()
        self.ai_cancel = cancel
        result_queue: queue.Queue = queue.Queue()
        self.ai_queue = result_queue

        def worker():
            try:
                move = engine.choose_move(
                    board_copy, ai_color, difficulty, cancel=cancel.is_set
                )
            except Exception:
                move = -1
            result_queue.put((token, move, time.monotonic()))

        self.ai_thread = threading.Thread(target=worker, daemon=True)
        self.ai_thread.start()
        self.ai_poll_job = self.root.after(
            40, self._poll_ai, result_queue, token, started
        )

    def _poll_ai(self, result_queue: queue.Queue, token: int, started: float):
        self.ai_poll_job = None
        if token != self.game_token or self.phase != "ai":
            return
        try:
            _, move, finished = result_queue.get_nowait()
        except queue.Empty:
            self.ai_poll_job = self.root.after(
                40, self._poll_ai, result_queue, token, started
            )
            return

        delay = max(0, int((0.48 - (finished - started)) * 1000))
        if delay:
            self.root.after(delay, lambda: self._finish_ai(token, move))
        else:
            self._finish_ai(token, move)

    def _finish_ai(self, token: int, move: int):
        if token != self.game_token or self.phase != "ai":
            return
        if move < 0 or move >= engine.SIZE * engine.SIZE or self.board[move] != engine.EMPTY:
            move = -1
        if move >= 0 and not engine.is_legal_move(self.board, move, self.ai_color):
            move = -1
        if move < 0:
            legal = engine.get_all_legal_moves(self.board, self.ai_color)
            move = legal[0] if legal else -1

        if move < 0:
            if engine.is_board_full(self.board):
                self._end_game(0, None)
            elif self.ai_color == engine.BLACK:
                self._end_game(self.player_color, None)
            return

        self._place_move(move, self.ai_color)

    def undo_move(self):
        if self.mode == "local":
            if not self.game_started or self.phase != "playing" or not self.history:
                return
            self.game_token += 1
            self.ai_cancel.set()
            last = self.history.pop()
            self.board[last["move"]] = engine.EMPTY
            self.current = last["player"]
            self.last_move = self.history[-1]["move"] if self.history else -1
            self.winner = 0
            self.win_line = None
            self._clear_temp_status()
            self.update_ui()
            self.board_view.redraw()
            self.show_temp_status("已悔棋，重新落子", 1500)
            return

        if not self.player_can_play():
            return
        last_player_index = -1
        for index in range(len(self.history) - 1, -1, -1):
            if self.history[index]["player"] == self.player_color:
                last_player_index = index
                break
        if last_player_index < 0:
            return

        self.game_token += 1
        self.ai_cancel.set()
        removed = self.history[last_player_index:]
        self.history = self.history[:last_player_index]
        for entry in removed:
            self.board[entry["move"]] = engine.EMPTY
        self.last_move = self.history[-1]["move"] if self.history else -1
        self.current = self.player_color
        self.phase = "playing"
        self.winner = 0
        self.win_line = None
        self._clear_temp_status()
        self.update_ui()
        self.board_view.redraw()
        self.show_temp_status("已悔棋，重新想想", 1600)

    def on_close(self):
        self.game_token += 1
        self.ai_cancel.set()
        self._cancel_thinking()
        self.root.destroy()

    # ------------------------------------------------------------------
    # UI state
    # ------------------------------------------------------------------

    def update_ui(self):
        local = self.mode == "local"
        over = self.phase == "over"
        if local:
            player_turn = (
                self.game_started
                and self.phase == "playing"
                and self.current == engine.BLACK
            )
            ai_turn = (
                self.game_started
                and self.phase == "playing"
                and self.current == engine.WHITE
            )
        else:
            player_turn = (
                self.game_started
                and self.phase == "playing"
                and self.current == self.player_color
            )
            ai_turn = self.game_started and self.phase == "ai"

        human_winner = over and self.winner == (
            engine.BLACK if local else self.player_color
        )
        ai_winner = over and self.winner == (
            engine.WHITE if local else self.ai_color
        )

        if not self.game_started:
            self.human_name_label.configure(text="你")
            self.ai_name_label.configure(text="弈者")
            self.human_color_label.configure(text="执黑")
            self.ai_color_label.configure(text="执白")
        elif local:
            self.human_name_label.configure(text="黑方")
            self.ai_name_label.configure(text="白方")
            self.human_color_label.configure(text="黑棋 · 禁手")
            self.ai_color_label.configure(text="白棋")
        else:
            self.human_name_label.configure(text="你")
            self.ai_name_label.configure(text="弈者")
            self.human_color_label.configure(
                text="执黑 · 禁手" if self.player_color == engine.BLACK else "执白"
            )
            self.ai_color_label.configure(
                text="执黑 · 禁手" if self.ai_color == engine.BLACK else "执白"
            )

        self.difficulty_pill.configure(
            text="双人" if local else engine.DIFFICULTIES[self.difficulty]["label"]
        )
        self.move_count_label.configure(text=str(len(self.history)))
        if over:
            state_text = "已结束"
        elif self.game_started:
            state_text = "进行中"
        else:
            state_text = "待开局"
        self.match_state_label.configure(text=state_text)

        self._update_player_card(self.human_card, player_turn, human_winner, False)
        self._update_player_card(self.ai_card, ai_turn, ai_winner, True)
        human_avatar_text = "黑" if local else "你"
        ai_avatar_text = "白" if local else "AI"
        self._draw_avatar(
            self.human_avatar,
            human_avatar_text,
            False,
            player_turn,
            local=local,
            black_side=True,
        )
        self._draw_avatar(
            self.ai_avatar,
            ai_avatar_text,
            True,
            ai_turn,
            local=local,
            black_side=False,
        )
        self.human_turn_pill.configure(text="落子中")
        self.ai_turn_pill.configure(text="落子中" if local else "思考中")
        self._update_turn_pill(self.human_turn_pill, player_turn)
        self._update_turn_pill(self.ai_turn_pill, ai_turn)

        if local:
            can_undo = (
                self.game_started and self.phase == "playing" and bool(self.history)
            )
        else:
            can_undo = player_turn and any(
                entry["player"] == self.player_color for entry in self.history
            )
        self.undo_button.set_enabled(can_undo)
        self.restart_button.set_enabled(not ai_turn)
        self.mode_note_label.configure(
            text=(
                "双人同屏 · 黑棋先行 · 双方轮流落子"
                if local
                else "✊  每局由猜拳决定谁执黑先行"
            )
        )
        self._update_status(over)

    def _update_player_card(self, card: tk.Frame, active: bool, winner: bool, is_ai: bool):
        bg = CARD_ACTIVE if active else CARD
        border = BORDER_GOLD if active or winner else BORDER
        card.configure(bg=bg, highlightbackground=border)
        pills = (self.human_turn_pill, self.ai_turn_pill)
        for child in card.winfo_children():
            if child in pills:
                continue
            child.configure(bg=bg)
            for sub in child.winfo_children():
                sub.configure(bg=bg)

    def _update_turn_pill(self, pill: tk.Label, active: bool):
        if active:
            pill.pack(side="right", padx=(6, 0))
        else:
            pill.pack_forget()

    def _update_status(self, over: bool | None = None):
        self._cancel_thinking()
        self.status_dot.delete("all")
        if over is None:
            over = self.phase == "over"
        if over:
            if self.winner == 0:
                self.status_dot.create_oval(3, 3, 15, 15, outline=MUTED_DIM, width=1)
                text = "平局"
            else:
                color = "#111" if self.winner == engine.BLACK else "#eee8da"
                outline = "#c0a77b" if self.winner == engine.BLACK else "#8b7a5d"
                self.status_dot.create_oval(
                    2, 2, 16, 16, fill=color, outline=outline, width=2
                )
                if self.mode == "local":
                    text = "黑胜" if self.winner == engine.BLACK else "白胜"
                else:
                    text = "你赢了" if self.winner == self.player_color else "弈者获胜"
            self.status_label.configure(text=text, fg=MUTED)
            self.thinking_label.configure(text="")
            return

        if not self.game_started:
            self.status_dot.create_oval(3, 3, 15, 15, outline=MUTED_DIM, width=1)
            self.status_label.configure(text="准备开局", fg=MUTED)
            self.thinking_label.configure(text="")
            return

        color = "#111111" if self.current == engine.BLACK else "#f2ede1"
        outline = "#c0a77b" if self.current == engine.BLACK else "#8b7a5d"
        self.status_dot.create_oval(2, 2, 16, 16, fill=color, outline=outline, width=2)
        if self.mode == "local":
            self.status_label.configure(
                text="轮到黑方落子" if self.current == engine.BLACK else "轮到白方落子",
                fg=MUTED,
            )
            self.thinking_label.configure(text="")
        elif self.phase == "ai":
            self.status_label.configure(text="弈者正在思考", fg=MUTED)
            self.thinking_label.configure(text="", fg=GOLD_DARK)
            self.thinking_phase = 0
            self._tick_thinking()
        elif self.current == self.player_color:
            self.status_label.configure(text="轮到你落子", fg=MUTED)
            self.thinking_label.configure(text="")
        else:
            self.status_label.configure(text="等待落子", fg=MUTED)
            self.thinking_label.configure(text="")

    def _tick_thinking(self):
        if self.phase != "ai":
            self.thinking_job = None
            return
        self.thinking_phase = (self.thinking_phase + 1) % 4
        self.thinking_label.configure(text="·" * self.thinking_phase)
        self.thinking_job = self.root.after(360, self._tick_thinking)

    def _cancel_thinking(self):
        if self.thinking_job:
            try:
                self.root.after_cancel(self.thinking_job)
            except tk.TclError:
                pass
            self.thinking_job = None

    def show_temp_status(self, text: str, duration: int = 1800):
        self._cancel_temp_status()
        self.status_label.configure(text=text, fg="#d8a293")
        self.thinking_label.configure(text="")
        self.temp_status_job = self.root.after(duration, self._clear_temp_status)

    def _clear_temp_status(self):
        if self.temp_status_job:
            try:
                self.root.after_cancel(self.temp_status_job)
            except tk.TclError:
                pass
            self.temp_status_job = None
        if self.game_started:
            self._update_status(self.phase == "over")

    def _cancel_temp_status(self):
        if self.temp_status_job:
            try:
                self.root.after_cancel(self.temp_status_job)
            except tk.TclError:
                pass
            self.temp_status_job = None


def _center_main_window(root: tk.Tk, width: int, height: int):
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    width = min(width, max(960, screen_w - 80))
    height = min(height, max(680, screen_h - 80))
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")


def _enable_dark_titlebar(root: tk.Tk):
    if sys.platform != "win32":
        return
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
            )
    except Exception:
        pass


def main():
    root = tk.Tk()
    root.title(APP_NAME)
    _center_main_window(root, 1240, 860)
    app = GomokuApp(root)
    _enable_dark_titlebar(root)
    root.mainloop()


if __name__ == "__main__":
    main()
