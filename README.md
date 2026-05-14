# 微信消息提醒

基于 Windows UI Automation 的微信消息弹窗工具，支持消息实时监控、未读角标、群聊发送者识别。

## 功能

- **消息弹窗** — 微信收到新消息时弹出通知卡片，显示联系人、内容、未读数和发送者
- **幽灵模式** — `Ctrl+Alt+E` 一键将微信窗口移出屏幕并隐藏任务栏图标，再次按下恢复
- **系统托盘** — 最小化到托盘运行，右键菜单可切换幽灵模式和退出
- **消息去重** — 同一消息不会重复弹窗，已读后自动停止提醒
- **群聊发送者识别** — 群聊中自动解析 `发送者: 消息内容` 格式

## 安装

```bash
pip install -r requirements.txt
```

## 运行

### 源码运行

```bash
pip install -r requirements.txt
python main.py
```

### 打包为 EXE

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=wechat.ico --name "WeChatNotify" \
    --add-data "wechat.ico;." \
    --hidden-import keyboard --hidden-import pystray --hidden-import PIL \
    --hidden-import uiautomation --hidden-import customtkinter main.py
```

打包后在 `dist/` 目录生成 `WeChatNotify.exe`，可独立运行，无需安装 Python。

> 打包后日志文件在 EXE 同目录下生成。

程序启动后自动最小化到系统托盘，微信收到新消息时右下角弹出通知。

## 发布

[Releases](https://github.com/CueBeiXing/wechat-notify/releases) 页面提供已打包的 EXE 文件，下载即可运行。

## 注意事项

### Qt 版微信（类名以 Qt5 开头）

Qt 版微信默认不向 Windows UI Automation 暴露控件树。启动时会自动执行环境修复：

1. **SPI_SETSCREENREADER** — 启用屏幕阅读器标志（会话级，立即生效）
2. **Narrator RunningState** — 修复 HKCU 注册表键

如果自动修复后仍无效，需以管理员身份执行以下命令并重启电脑：

```bash
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Accessibility" /v ForceUIAForQt /t REG_DWORD /d 1 /f
```

### 诊断工具

如果程序无法检测到微信消息，运行诊断脚本导出微信窗口的 UIA 控件树：

```bash
python tools/diagnose_wechat.py
```

生成的 `dump_wechat_ui.txt` 可用于排查控件类型兼容性问题。

## 目录结构

```
wechat-notify/
├── main.py                     # 入口：单实例锁、托盘、监控线程、快捷键
├── requirements.txt
├── wechat.ico                  # 托盘图标
├── src/
│   ├── config.py               # 共享常量、日志、窗口类名
│   ├── core/
│   │   ├── wechat_monitor.py   # 核心：UIA 监控、Cell 解析、消息处理
│   │   └── ghost_mode.py       # 幽灵模式：隐藏/恢复微信窗口
│   └── ui/
│       ├── notifications.py    # 弹窗：渐入动画、角标、多消息堆叠
│       └── tray_icon.py        # 系统托盘图标与菜单
└── tools/
    └── diagnose_wechat.py      # 诊断：导出微信 UIA 控件树
```

## 依赖

- `uiautomation` — Windows UI Automation 封装
- `customtkinter` — 现代化 Tkinter 组件库
- `pystray` — 系统托盘
- `keyboard` — 全局快捷键
- `Pillow` — 图标处理
- `pywin32` — Win32 API 封装

## 原理

通过 Windows UI Automation 接口读取微信聊天列表的控件树，定位 `ChatSessionCell` 控件获取会话信息（联系人、消息内容、未读数、发送者），状态比对去重后通过自定义弹窗展示。

## 致谢

- [wx4py](https://github.com/claw-codes/wx4py) — 环境修复方案、AutomationId 定位思路
- [uiautomation](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows) — Python UIA 封装库
