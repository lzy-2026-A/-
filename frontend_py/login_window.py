# -*- coding: utf-8 -*-
"""登录窗口"""
import tkinter as tk
from tkinter import messagebox

from register_window import RegisterWindow
from win_util import disable_close_button

BG = "#1a2a4a"
PANEL = "#243b66"
BTN = "#2a5db0"
BTN_RED = "#c0392b"
FG = "#ffffff"
YELLOW = "#f1c40f"
ENTRY_BG = "#0e1c36"

FONT_TITLE = ("微软雅黑", 20, "bold")
FONT_LABEL = ("微软雅黑", 12)
FONT_BTN = ("微软雅黑", 11, "bold")


class LoginWindow:
    def __init__(self, client):
        self.client = client
        self.root = tk.Tk()
        self.root.title("火车站广播调度系统 - 登录")
        self.root.geometry("420x360")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self._center()
        self.logged_in = False
        self._build()
        # 禁用标题栏关闭按钮
        self.root.after(100, lambda: disable_close_button(self.root))

    def _center(self):
        self.root.update_idletasks()
        w, h = 420, 360
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        tk.Label(self.root, text="火车站广播调度系统", bg=BG, fg=FG,
                 font=FONT_TITLE).pack(pady=(35, 5))
        tk.Label(self.root, text="旅客服务系统智能管理广播平台", bg=BG, fg=YELLOW,
                 font=("微软雅黑", 10)).pack(pady=(0, 25))

        frm = tk.Frame(self.root, bg=BG)
        frm.pack(pady=5)

        tk.Label(frm, text="账  号：", bg=BG, fg=FG, font=FONT_LABEL).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.ent_user = tk.Entry(frm, width=22, font=FONT_LABEL, bg=ENTRY_BG, fg=FG,
                                 insertbackground=FG, relief="flat")
        self.ent_user.grid(row=0, column=1, padx=5, pady=10)

        tk.Label(frm, text="密  码：", bg=BG, fg=FG, font=FONT_LABEL).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.ent_pwd = tk.Entry(frm, width=22, font=FONT_LABEL, bg=ENTRY_BG, fg=FG,
                                insertbackground=FG, relief="flat", show="*")
        self.ent_pwd.grid(row=1, column=1, padx=5, pady=10)
        self.ent_pwd.bind("<Return>", lambda e: self._do_login())

        btnfrm = tk.Frame(self.root, bg=BG)
        btnfrm.pack(pady=20)
        tk.Button(btnfrm, text="登  录", width=12, height=1, font=FONT_BTN,
                  bg=BTN, fg=FG, relief="flat", command=self._do_login).grid(row=0, column=0, padx=12)
        tk.Button(btnfrm, text="注  册", width=12, height=1, font=FONT_BTN,
                  bg="#34495e", fg=FG, relief="flat", command=self._open_register).grid(row=0, column=1, padx=12)

        self.status = tk.Label(self.root, text="", bg=BG, fg=YELLOW, font=("微软雅黑", 9))
        self.status.pack(pady=5)

    def _do_login(self):
        u = self.ent_user.get().strip()
        p = self.ent_pwd.get().strip()
        if not u or not p:
            messagebox.showwarning("提示", "请输入账号和密码")
            return
        self.status.config(text="正在登录...")
        self.root.update()
        if not self.client.connected:
            ok, msg = self.client.connect()
            if not ok:
                self.status.config(text=msg)
                messagebox.showerror("错误", msg)
                return
        ok, msg = self.client.login(u, p)
        if ok:
            self.logged_in = True
            self.status.config(text="登录成功")
            self.root.after(300, self.root.destroy)
        else:
            self.status.config(text="")
            messagebox.showerror("登录失败", msg)

    def _open_register(self):
        if not self.client.connected:
            ok, msg = self.client.connect()
            if not ok:
                messagebox.showerror("错误", msg)
                return
        RegisterWindow(self.client)

    def run(self):
        self.client.connect()
        self.root.mainloop()
        return self.logged_in
