"""系统托盘图标与菜单。"""
import os
import subprocess

import pystray
from PIL import Image, ImageDraw

from src.config import ICON_PATH, LOG_PATH, app_state
from src.core.ghost_mode import ghost_manager


def _exit(icon_obj):
    app_state.is_running = False
    icon_obj.stop()


def _open_log():
    try:
        os.startfile(LOG_PATH)
    except Exception:
        subprocess.Popen(["notepad.exe", LOG_PATH])


def _default_icon():
    img = Image.new('RGB', (64, 64), color=(25, 130, 250))
    draw = ImageDraw.Draw(img)
    draw.ellipse((10, 10, 54, 54), fill=(25, 130, 250), outline='white', width=2)
    return img


def setup_tray():
    try:
        if os.path.exists(ICON_PATH):
            base = Image.open(ICON_PATH).convert("RGBA").resize((64, 64))
        else:
            base = _default_icon()
    except Exception:
        base = _default_icon()

    menu = pystray.Menu(
        pystray.MenuItem("幽灵模式 (Ctrl+Alt+E)", ghost_manager.toggle_visibility),
        pystray.MenuItem("查看日志", _open_log),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", _exit),
    )
    icon = pystray.Icon("WeChatNotify", base, "微信消息提醒", menu)
    icon.run()
