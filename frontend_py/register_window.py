# -*- coding: utf-8 -*-
"""注册窗口（模态）"""
import tkinter as tk
from tkinter import messagebox

BG = "#1a2a4a"
BTN = "#2a5db0"
FG = "#ffffff"
YELLOW = "#f1c40f"
ENTRY_BG = "#0e1c36"

FONT_TITLE = ("微软雅黑", 16, "bold")
FONT_LABEL = ("微软雅黑", 11)
FONT_BTN = ("微软雅黑", 11, "bold")


class RegisterWindow:
    def __init__(self, client):
        self.client = client
        self.root = tk.Toplevel()
        self.root.title("注册新账号")
        self.root.geometry("400x330")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.transient(self.root.master)
        self.root.grab_set()
        self._center()
        self._build()

    def _center(self):
        self.root.update_idletasks()
        w, h = 400, 330
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        tk.Label(self.root, text="注册新账号", bg=BG, fg=FG, font=FONT_TITLE).pack(pady=(25, 15))

        frm = tk.Frame(self.root, bg=BG)
        frm.pack(pady=5)

        self.ents = {}
        rows = [("账  号：", "user"),
                ("密  码：", "pwd"),
                ("确认密码：", "pwd2")]
        for i, (label, key) in enumerate(rows):
            tk.Label(frm, text=label, bg=BG, fg=FG, font=FONT_LABEL).grid(
                row=i, column=0, padx=10, pady=10, sticky="e")
            e = tk.Entry(frm, width=20, font=FONT_LABEL, bg=ENTRY_BG, fg=FG,
                        insertbackground=FG, relief="flat", show="*" if key != "user" else "")
            e.grid(row=i, column=1, padx=5, pady=10)
            self.ents[key] = e

        btnfrm = tk.Frame(self.root, bg=BG)
        btnfrm.pack(pady=15)
        tk.Button(btnfrm, text="注  册", width=11, font=FONT_BTN,
                  bg=BTN, fg=FG, relief="flat", command=self._do_register).grid(row=0, column=0, padx=10)
        tk.Button(btnfrm, text="取  消", width=11, font=FONT_BTN,
                  bg="#34495e", fg=FG, relief="flat", command=self.root.destroy).grid(row=0, column=1, padx=10)

        self.status = tk.Label(self.root, text="密码至少 6 位", bg=BG, fg=YELLOW, font=("微软雅黑", 9))
        self.status.pack(pady=5)

    def _do_register(self):
        u = self.ents["user"].get().strip()
        p1 = self.ents["pwd"].get().strip()
        p2 = self.ents["pwd2"].get().strip()
        if not u or not p1:
            messagebox.showwarning("提示", "请输入账号和密码", parent=self.root)
            return
        if p1 != p2:
            messagebox.showerror("错误", "两次输入的密码不一致", parent=self.root)
            return
        ok, msg = self.client.register(u, p1)
        if ok:
            messagebox.showinfo("成功", "注册成功，请返回登录", parent=self.root)
            self.root.destroy()
        else:
            messagebox.showerror("注册失败", msg, parent=self.root)
