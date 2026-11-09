# -*- coding: utf-8 -*-
"""
火车站广播调度系统 - 主程序入口
流程：登录窗口 -> 主控制台；退出登录回登录，关闭系统退出程序
运行：python main.py   （先确保后端 train_broadcast_backend.exe 已启动）
"""
import sys
import tkinter as tk
from tkinter import messagebox

from client import BackendClient
from login_window import LoginWindow
from main_window import MainWindow


def main():
    client = BackendClient()

    while True:
        login = LoginWindow(client)
        logged_in = login.run()
        if not logged_in:
            # 登录窗口被关闭（未登录成功），退出程序
            client.close()
            break

        # 进入主控制台
        win = MainWindow(client)
        win.run()

        # 主窗口关闭后：
        #  - 点"关闭系统"：后端会断开，client.connected 变为 False -> 退出程序
        #  - 点"退出登录"：连接仍在 -> 循环回登录窗口
        if not client.connected:
            break

    print("程序已退出")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("程序错误", f"发生未处理错误：\n{e}")
            root.destroy()
        except Exception:
            pass
        print("ERROR:", e)
        sys.exit(1)
