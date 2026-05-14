"""消息弹窗：渐入动画、槽位管理、多消息堆叠。"""
import queue
import winsound

import customtkinter as ctk

from src.config import app_state, MAX_MSG_LEN, NOTIFY_SECONDS

_active = {}  # slot -> toplevel


def _cleanup():
    for k in list(_active):
        if not _active[k].winfo_exists():
            del _active[k]


def _find_slot():
    _cleanup()
    slot = 0
    while slot in _active:
        slot += 1
    return slot


def _fade_in(top, step=0.06, delay=12):
    current = top.attributes("-alpha")
    if current >= 0.92:
        return
    top.attributes("-alpha", min(current + step, 0.92))
    if top.attributes("-alpha") < 0.92:
        top.after(delay, lambda: _fade_in(top, step, delay))


def show_banner(root, name, msg, sender=None, unread=0, stay_sec=NOTIFY_SECONDS):
    slot = _find_slot()

    winsound.PlaySound(
        "SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC
    )

    top = ctk.CTkToplevel(root)
    top.overrideredirect(True)
    top.attributes("-topmost", True)
    top.attributes("-toolwindow", True)

    transparent = "#010101"
    top.configure(fg_color=transparent)
    top.attributes("-transparentcolor", transparent)
    top.attributes("-alpha", 0.0)

    w, h = 340, 90
    x = top.winfo_screenwidth() - w - 16
    y = 60 + slot * (h + 8)
    top.geometry(f"{w}x{h}+{x}+{y}")
    _active[slot] = top

    # 卡片
    frame = ctk.CTkFrame(
        top, width=w, height=h,
        corner_radius=12, fg_color="#1a1a1a",
        bg_color=transparent, border_width=1, border_color="#333333",
    )
    frame.place(x=0, y=0)

    # 绿色指示条
    ctk.CTkFrame(
        frame, width=3, height=52, corner_radius=2, fg_color="#07C160",
    ).place(x=10, y=19)

    # 联系人
    ctk.CTkLabel(
        frame, text=name[:28],
        font=("Microsoft YaHei UI", 12, "bold"),
        text_color="#ffffff", anchor="w",
    ).place(x=22, y=12)

    # 未读角标
    if unread > 1:
        badge = ctk.CTkFrame(
            frame, width=28, height=18,
            corner_radius=9, fg_color="#E81123",
        )
        badge.place(x=w - 42, y=13)
        ctk.CTkLabel(
            badge, text=str(unread),
            font=("Microsoft YaHei UI", 9, "bold"), text_color="#ffffff",
        ).place(relx=0.5, rely=0.5, anchor="center")

    # 发送者
    if sender:
        ctk.CTkLabel(
            frame, text=f"{sender}:",
            font=("Microsoft YaHei UI", 10),
            text_color="#07C160", anchor="w",
        ).place(x=22, y=34)

    # 消息正文
    prefix = f"[{unread}条] " if unread > 1 else ""
    display_msg = f"{prefix}{msg}"[:MAX_MSG_LEN]
    cx = 28 + (len(sender) * 10 if sender else 0) if sender else 22
    cy = 34 if sender else 42
    ctk.CTkLabel(
        frame, text=display_msg,
        font=("Microsoft YaHei UI", 12),
        text_color="#b0b0b0", justify="left", wraplength=290, anchor="w",
    ).place(x=cx, y=cy)

    # 关闭按钮
    ctk.CTkButton(
        frame, text="×", width=20, height=20,
        corner_radius=10, fg_color="#1a1a1a", hover_color="#444444",
        text_color="#666666", font=("Microsoft YaHei UI", 13),
        command=top.destroy,
    ).place(x=w - 26, y=4)

    top.after(10, lambda: _fade_in(top))
    top.after(int(stay_sec * 1000), top.destroy)


def check_queue(root, msg_queue):
    if not app_state.is_running:
        root.destroy()
        return

    batch = []
    try:
        while True:
            batch.append(msg_queue.get_nowait())
    except queue.Empty:
        pass

    for data in batch:
        show_banner(
            root,
            name=data["name"],
            msg=data["msg"],
            sender=data.get("sender"),
            unread=data.get("unread", 0),
        )

    root.after(200, check_queue, root, msg_queue)
