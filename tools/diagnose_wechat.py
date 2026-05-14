"""微信 UIA 树诊断工具
用法：python tools/diagnose_wechat.py
输出：dump_wechat_ui.txt
"""
import pythoncom
import uiautomation as auto
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import WECHAT_WINDOW_CLASSES, WECHAT_PROCESS_NAMES

OUTPUT = "dump_wechat_ui.txt"


def dump_tree(control, file, depth=0, max_depth=5):
    if depth > max_depth:
        return
    indent = "  " * depth
    try:
        name = (control.Name or "")[:80]
        cls = control.ClassName or ""
        ctype = control.ControlTypeName or ""
        children = control.GetChildren()
        file.write(f"{indent}|- {ctype} cls=\"{cls}\" name=\"{name}\" children={len(children)}\n")
        for child in children:
            dump_tree(child, file, depth + 1, max_depth)
    except Exception as e:
        file.write(f"{indent}|- [ERR: {e}]\n")


def main():
    pythoncom.CoInitialize()
    print("查找微信窗口...")

    wechat = None
    # 按类名
    for cls_name in WECHAT_WINDOW_CLASSES:
        wnd = auto.WindowControl(ClassName=cls_name)
        if wnd.Exists(0.3):
            wechat = wnd
            print(f"  找到: ClassName={cls_name}")
            break
    # 按进程名
    if not wechat:
        for wnd in auto.GetRootControl().GetChildren():
            try:
                if wnd.ProcessName and wnd.ProcessName.lower() in WECHAT_PROCESS_NAMES:
                    wechat = wnd
                    print(f"  找到: 进程名匹配, ClassName={wnd.ClassName}")
                    break
            except Exception:
                continue

    if not wechat:
        print("未找到微信窗口，请确认微信已运行")
        pythoncom.CoUninitialize()
        return

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"ClassName: {wechat.ClassName}\n")
        f.write(f"Name: {wechat.Name}\n")
        try:
            f.write(f"ProcessName: {wechat.ProcessName}\n")
        except Exception:
            f.write("ProcessName: (N/A)\n")
        f.write("=" * 60 + "\n\n")
        dump_tree(wechat, f)

    print(f"已导出 → {OUTPUT}")
    pythoncom.CoUninitialize()


if __name__ == "__main__":
    main()
