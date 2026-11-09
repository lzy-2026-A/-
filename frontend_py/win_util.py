# -*- coding: utf-8 -*-
"""Windows 窗口工具：禁用标题栏关闭按钮"""
import ctypes
import tkinter as tk

MF_BYCOMMAND = 0x0000
MF_GRAYED = 0x0001
SC_CLOSE = 0xF060


def disable_close_button(win):
    """灰掉（禁用）窗口标题栏右上角的关闭按钮 X，点了无反应。
    win 可为 tk.Tk 或 tk.Toplevel。"""
    win.update_idletasks()
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        if not hwnd:
            hwnd = win.winfo_id()
        hmenu = ctypes.windll.user32.GetSystemMenu(hwnd, False)
        if hmenu:
            ctypes.windll.user32.EnableMenuItem(
                hmenu, SC_CLOSE, MF_BYCOMMAND | MF_GRAYED)
            ctypes.windll.user32.DrawMenuBar(hwnd)
    except Exception:
        # 非 Windows 或失败时退化为仅拦截点击
        win.protocol("WM_DELETE_WINDOW", lambda: None)
