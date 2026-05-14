"""微信消息监控核心：UIA 控件树采集 → Cell 解析 → 去重 → 入队。"""
import ctypes
import re
import time
import winreg

import pythoncom
import uiautomation as auto

from src.config import (
    app_state, logger,
    POLL_INTERVAL,
    WECHAT_WINDOW_CLASSES, WECHAT_PROCESS_NAMES, QT_CLASS_PREFIX,
    SESSION_LIST_ID, SESSION_CELL_CLASSES, CHAT_VIEW_CLASSES,
)

_UNREAD_RE = re.compile(r'^\[(\d+)条\]$')
_TIME_RE = re.compile(
    r'^\d{1,2}:\d{2}$|^\d{2}/\d{2}$|^\d{1,2}月\d{1,2}日$|^昨天$|^前天$|^星期.$'
)
_SKIP_KEYWORDS = {
    '已置顶', '消息免打扰', '撤销', '公众号',
    '服务号', '被拉黑', '接收文章', '群聊',
}


class WeChatMonitor:
    """微信消息监控器。"""

    def __init__(self, msg_queue):
        self._queue = msg_queue
        self._state = {}          # name -> "msg|unread"
        self._found_once = False
        self._uia_root = None     # Qt 唤醒引用（防 COM GC）
        self._qt_warned = False
        self._force_uia = self._check_force_uia_for_qt()

        need_restart, tips = self.fix_environment()
        if need_restart:
            logger.warning(
                "环境修复已应用，建议重启微信:\n"
                + "\n".join(f"  - {t}" for t in tips)
            )

    # ================================================================
    # 环境修复
    # ================================================================

    @staticmethod
    def _ensure_screen_reader():
        """启用 SPI_SETSCREENREADER，Qt 应用检测到此标志后暴露 UIA 树。"""
        SPI_GET = 0x0046
        SPI_SET = 0x0047
        SPIF_UPDATE = 0x01
        SPIF_CHANGE = 0x02

        pv = ctypes.wintypes.BOOL()
        ctypes.windll.user32.SystemParametersInfoW(SPI_GET, 0, ctypes.byref(pv), 0)
        if pv.value:
            return False

        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SET, 1, 0, SPIF_UPDATE | SPIF_CHANGE
        )
        return True

    @staticmethod
    def _fix_narrator_registry():
        """修复 HKCU Narrator RunningState 键。"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Narrator\NoRoam",
                0, winreg.KEY_READ | winreg.KEY_WRITE,
            )
            try:
                val, _ = winreg.QueryValueEx(key, "RunningState")
                if val == 0:
                    winreg.SetValueEx(key, "RunningState", 0, winreg.REG_DWORD, 1)
                    winreg.CloseKey(key)
                    return True
            except FileNotFoundError:
                winreg.SetValueEx(key, "RunningState", 0, winreg.REG_DWORD, 1)
                winreg.CloseKey(key)
                return True
            winreg.CloseKey(key)
        except Exception:
            pass
        return False

    @staticmethod
    def _check_force_uia_for_qt():
        """检查 HKLM ForceUIAForQt 注册表键。"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Accessibility"
            )
            try:
                val, _ = winreg.QueryValueEx(key, "ForceUIAForQt")
                return val == 1
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False

    @classmethod
    def fix_environment(cls):
        """执行全部环境修复。返回 (need_restart, messages)。"""
        msgs = []
        restart = False

        if cls._ensure_screen_reader():
            msgs.append("SPI_SETSCREENREADER 已启用")
            restart = True
        if cls._fix_narrator_registry():
            msgs.append("Narrator RunningState 已修复")
            restart = True
        if not cls._check_force_uia_for_qt():
            msgs.append(
                "缺少 ForceUIAForQt，以管理员运行:\n"
                '  reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
                '\\Explorer\\Accessibility" /v ForceUIAForQt /t REG_DWORD /d 1 /f'
            )
            restart = True

        return restart, msgs

    # ================================================================
    # 窗口查找
    # ================================================================

    def _find_window(self):
        """4 层回退查找微信主窗口。"""
        # 1) 类名直查
        for cls_name in WECHAT_WINDOW_CLASSES:
            try:
                wnd = auto.WindowControl(ClassName=cls_name)
                if wnd.Exists(0.15):
                    if not self._found_once:
                        logger.info(f"找到微信窗口: {cls_name}")
                        self._found_once = True
                    self._wake_qt(wnd)
                    return wnd
            except Exception:
                time.sleep(0.5)
                continue

        # 2) 桌面根节点深度搜索
        try:
            root = auto.GetRootControl()
            for cls_name in WECHAT_WINDOW_CLASSES:
                wnd = root.Control(searchDepth=5, ClassName=cls_name)
                if wnd and wnd.Exists(0.1):
                    logger.info(f"深度搜索: {cls_name}")
                    self._wake_qt(wnd)
                    return wnd
        except Exception:
            pass

        # 3) 进程名枚举
        try:
            for wnd in auto.GetRootControl().GetChildren():
                try:
                    name = (wnd.ProcessName or "").lower()
                    if name in WECHAT_PROCESS_NAMES:
                        logger.info(f"进程名匹配: {wnd.ClassName}")
                        return wnd
                except Exception:
                    continue
        except Exception:
            pass

        # 4) 标题模糊匹配
        try:
            wnd = auto.WindowControl(
                searchDepth=1,
                Compare=lambda c, n: n and "微信" in n,
            )
            if wnd.Exists(0.15):
                logger.info(f"标题匹配: {wnd.Name}")
                return wnd
        except Exception:
            pass

        return None

    def _wake_qt(self, wechat_window):
        """Qt 版微信：ControlFromHandle 强制激活 UIA 辅助功能。"""
        cls = wechat_window.ClassName or ""
        if not cls.startswith(QT_CLASS_PREFIX):
            return
        try:
            hwnd = wechat_window.NativeWindowHandle
            if not hwnd:
                hwnd = ctypes.windll.user32.FindWindowW(cls, None)
            if hwnd:
                self._uia_root = auto.ControlFromHandle(hwnd)
                if not self._qt_warned:
                    logger.info(f"Qt UIA 唤醒成功 hwnd={hwnd}")
                    self._qt_warned = True
        except Exception:
            pass

    # ================================================================
    # 容器定位
    # ================================================================

    def _find_container(self, wechat):
        """定位会话列表容器。"""
        try:
            ctrl = wechat.ListControl(AutomationId=SESSION_LIST_ID)
            if ctrl.Exists(0.3):
                return ctrl
        except Exception:
            pass
        for cls_name in CHAT_VIEW_CLASSES:
            try:
                ctrl = wechat.GroupControl(ClassName=cls_name)
                if ctrl.Exists(0.15):
                    return ctrl
            except Exception:
                continue
        return wechat

    # ================================================================
    # Cell 解析
    # ================================================================

    @staticmethod
    def _is_time_text(text):
        return bool(_TIME_RE.match(text.strip()))

    def _parse_cell(self, cell_name):
        """解析 ChatSessionCell.Name → {name, msg, sender, time, unread}。"""
        lines = [l.strip() for l in cell_name.splitlines() if l.strip()]
        lines = [l for l in lines if not any(k in l for k in _SKIP_KEYWORDS)]
        if len(lines) < 2:
            return None

        session_name = lines[0]

        time_str = None
        for l in reversed(lines):
            if self._is_time_text(l):
                time_str = l
                break

        message_line = None
        for l in lines[1:]:
            if l == time_str:
                continue
            message_line = l
            break
        if not message_line:
            return None

        unread = 0
        m = _UNREAD_RE.match(message_line)
        if m:
            unread = int(m.group(1))
            message_line = None
            for l in lines[1:]:
                if l == time_str or _UNREAD_RE.match(l):
                    continue
                message_line = l
                break
        if not message_line:
            return None

        sender = None
        content = message_line
        if ':' in message_line:
            parts = message_line.split(':', 1)
            sender = parts[0].strip().strip('"')
            content = parts[1].strip()

        return {
            "name": session_name,
            "msg": content,
            "sender": sender,
            "time": time_str,
            "unread": unread,
        }

    # ================================================================
    # 数据采集
    # ================================================================

    def _collect_cells(self, container):
        """遍历 UIA 树，按 ChatSessionCell/ListItem 控件类型收集。"""
        cells = {}

        def walk(c):
            for cell_cls in SESSION_CELL_CLASSES:
                if cell_cls in (c.ClassName or ""):
                    name = (c.Name or "").strip()
                    if name:
                        cells[name] = c
                    return
            if (c.ControlTypeName or "") == "ListItemControl":
                name = (c.Name or "").strip()
                if name:
                    cells[name] = c
                return
            for child in c.GetChildren():
                walk(child)

        walk(container)

        results = []
        for cell in cells.values():
            data = self._parse_cell(cell.Name)
            if data:
                results.append(data)
        return results

    # ================================================================
    # 消息处理
    # ================================================================

    def _process(self, results):
        """去重 + 未读过滤 + 入队。"""
        for data in results:
            unread = data.get("unread", 0)
            msg = data.get("msg")
            if unread <= 0 or not msg:
                continue

            name = data["name"]
            key = f"{msg}|{unread}"
            if self._state.get(name) == key:
                continue

            self._state[name] = key
            sender = data.get("sender")
            prefix = f"[{unread}条] " if unread > 1 else ""
            display = f"{prefix}{sender}: {msg}" if sender else f"{prefix}{msg}"

            logger.info(
                f"新消息 -> {name}"
                f"{' | ' + sender if sender else ''}"
                f" | {display}"
            )
            self._queue.put({
                "name": name, "msg": msg,
                "sender": sender, "unread": unread,
            })

    # ================================================================
    # 警告
    # ================================================================

    def _warn_not_found(self):
        tips = [
            "未检测到微信窗口:",
            "  1) 微信 (WeChat.exe) 已启动并登录",
            "  2) 微信版本 >= 3.9",
        ]
        if not self._force_uia:
            tips.append(
                "  3) [Qt版] 需要 ForceUIAForQt:\n"
                '     reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
                '\\Explorer\\Accessibility" /v ForceUIAForQt /t REG_DWORD /d 1 /f\n'
                "     执行后重启电脑"
            )
        else:
            tips.append("  3) UIA 服务正常")
        logger.warning("\n".join(tips))

    def _warn_qt_empty(self):
        if not self._force_uia and not self._qt_warned:
            logger.warning(
                "Qt 微信控件树为空！若无效请以管理员执行:\n"
                '  reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
                '\\Explorer\\Accessibility" /v ForceUIAForQt /t REG_DWORD /d 1 /f\n'
                "  然后重启电脑"
            )
            self._qt_warned = True

    # ================================================================
    # 主循环
    # ================================================================

    def run(self):
        logger.info("微信消息监控已启动")
        auto.SetGlobalSearchTimeout(10)
        pythoncom.CoInitialize()

        cycle = 0
        while app_state.is_running:
            cycle += 1
            try:
                wechat = self._find_window()
                if not wechat:
                    if not self._found_once:
                        self._warn_not_found()
                    time.sleep(POLL_INTERVAL)
                    continue

                container = self._find_container(wechat)
                results = self._collect_cells(container)

                if cycle == 1:
                    logger.info(f"[首次扫描] {len(results)} 条会话")
                    for r in results:
                        s = r.get("sender")
                        p = f"[{r['unread']}条] " if r.get("unread") else ""
                        line = f"  {r['name']} | {s}: {p}{r['msg']}" if s \
                            else f"  {r['name']} | {p}{r['msg']}"
                        logger.info(line)
                    if (len(results) == 0
                            and (wechat.ClassName or "").startswith(QT_CLASS_PREFIX)):
                        self._warn_qt_empty()

                self._process(results)

            except Exception as e:
                logger.error(f"监控异常: {e}", exc_info=True)

            time.sleep(POLL_INTERVAL)

        pythoncom.CoUninitialize()
        logger.info("监控已停止")
