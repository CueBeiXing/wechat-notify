"""幽灵模式：隐藏/恢复微信窗口，Ctrl+Alt+E 切换。"""
import ctypes
import time
from ctypes import wintypes

import uiautomation as auto

from src.config import (
    logger, WECHAT_WINDOW_CLASSES, WECHAT_PROCESS_NAMES, QT_CLASS_PREFIX,
)

GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
SWP_FLAGS = 0x0001 | 0x0004 | 0x0020  # NOSIZE | NOZORDER | FRAMECHANGED


class GhostMode:
    """微信窗口显隐控制。"""

    def __init__(self):
        self._hidden = False
        self._last_toggle = 0
        self._saved_x = None
        self._saved_y = None

    def _find_window(self):
        for cls_name in WECHAT_WINDOW_CLASSES:
            try:
                wnd = auto.WindowControl(ClassName=cls_name)
                if wnd.Exists(0.15):
                    if cls_name.startswith(QT_CLASS_PREFIX):
                        hwnd = wnd.NativeWindowHandle
                        if not hwnd:
                            hwnd = ctypes.windll.user32.FindWindowW(cls_name, None)
                        if hwnd:
                            auto.ControlFromHandle(hwnd)
                    return wnd
            except Exception:
                continue
        try:
            for wnd in auto.GetRootControl().GetChildren():
                try:
                    if (wnd.ProcessName or "").lower() in WECHAT_PROCESS_NAMES:
                        return wnd
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def toggle_visibility(self, icon=None, item=None):
        now = time.time()
        if now - self._last_toggle < 0.5:
            return
        self._last_toggle = now

        try:
            wechat = self._find_window()
            if not wechat or not wechat.Exists(0.2):
                return

            hwnd = wechat.NativeWindowHandle
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

            if not self._hidden:
                rect = wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                self._saved_x, self._saved_y = rect.left, rect.top

                ctypes.windll.user32.ShowWindow(hwnd, 9)
                ex = (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
                ctypes.windll.user32.SetWindowPos(
                    hwnd, 0, -20000, -20000, 0, 0, SWP_FLAGS
                )
                self._hidden = True
                logger.info("幽灵模式: 微信已隐藏")
            else:
                ex = (ex | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
                x = self._saved_x if self._saved_x is not None else 200
                y = self._saved_y if self._saved_y is not None else 200
                ctypes.windll.user32.SetWindowPos(
                    hwnd, 0, x, y, 0, 0, SWP_FLAGS
                )
                ctypes.windll.user32.ShowWindow(hwnd, 9)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                self._hidden = False
                logger.info("幽灵模式: 微信已恢复")
        except Exception as e:
            logger.error(f"幽灵模式失败: {e}", exc_info=True)


ghost_manager = GhostMode()
