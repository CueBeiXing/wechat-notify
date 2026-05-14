import argparse
import ctypes
import queue
import sys
import threading

import customtkinter as ctk
import keyboard

from src.config import app_state, logger, set_debug_mode
from src.core.ghost_mode import ghost_manager
from src.core.wechat_monitor import WeChatMonitor
from src.ui.notifications import check_queue
from src.ui.tray_icon import setup_tray

_mutex = None


def _ensure_single_instance():
    global _mutex
    _mutex = ctypes.windll.kernel32.CreateMutexW(
        None, False, "WeChatNotifyUI_UniqueLock"
    )
    return ctypes.windll.kernel32.GetLastError() != 183


def _start_hotkey_listener():
    logger.info("全局快捷键 Ctrl+Alt+E 已就绪")
    keyboard.add_hotkey('ctrl+alt+e', ghost_manager.toggle_visibility)
    keyboard.wait()


def main():
    parser = argparse.ArgumentParser(description="微信消息提醒")
    parser.add_argument("--debug", action="store_true", help="启用 DEBUG 日志")
    args = parser.parse_args()

    if args.debug:
        set_debug_mode()

    if not _ensure_single_instance():
        logger.error("已有实例在运行，退出")
        sys.exit(0)

    logger.info("=" * 40)
    logger.info("=== 微信消息提醒 启动 ===")
    logger.info("=" * 40)

    msg_queue = queue.Queue()
    monitor = WeChatMonitor(msg_queue)

    threading.Thread(target=setup_tray, daemon=True).start()
    threading.Thread(target=monitor.run, daemon=True).start()
    threading.Thread(target=_start_hotkey_listener, daemon=True).start()

    root = ctk.CTk()
    root.attributes("-alpha", 0)
    root.withdraw()
    root.after(200, check_queue, root, msg_queue)
    root.mainloop()

    app_state.is_running = False


if __name__ == "__main__":
    main()
