import os
import sys
import logging
from logging.handlers import RotatingFileHandler


# -- 路径 --

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    LOG_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOG_DIR = BASE_DIR

ICON_PATH = os.path.join(BASE_DIR, "wechat.ico")
LOG_PATH = os.path.join(LOG_DIR, "wechat_notify.log")


# -- 日志（1MB x 3 轮转） --

_file_handler = RotatingFileHandler(
    LOG_PATH, encoding='utf-8', maxBytes=1 * 1024 * 1024, backupCount=3
)
_file_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s'
))
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s'
))

logger = logging.getLogger("WeChatNotify")
logger.setLevel(logging.INFO)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)


def set_debug_mode():
    """命令行 --debug 触发，输出 DEBUG 级别日志。"""
    logger.setLevel(logging.DEBUG)
    for h in logger.handlers:
        h.setLevel(logging.DEBUG)
    logger.debug("DEBUG 模式已启用")


# -- 微信窗口标识 --

WECHAT_WINDOW_CLASSES = [
    "mmui::MainWindow",
    "Qt51514QWindowIcon",
]
WECHAT_PROCESS_NAMES = {"wechat.exe", "weixin.exe"}
QT_CLASS_PREFIX = "Qt5"


# -- 微信 UIA 控件标识 --

SESSION_LIST_ID = "session_list"
SESSION_CELL_CLASSES = ["mmui::ChatSessionCell", "mmui::SessionCell"]
CHAT_VIEW_CLASSES = ["mmui::ChatMasterView", "mmui::ChatListView"]


# -- 监控参数 --

POLL_INTERVAL = 1.0


# -- 通知参数 --

MAX_MSG_LEN = 180
NOTIFY_SECONDS = 3


# -- 全局状态 --

class AppState:
    is_running = True


app_state = AppState()
