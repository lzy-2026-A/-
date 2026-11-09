# -*- coding: utf-8 -*-
"""主控制台窗口（对应易语言 主工控窗口.e）"""
import tkinter as tk
from tkinter import ttk, messagebox
from win_util import disable_close_button

# 优化后的配色方案 - 更协调的深色主题
BG = "#1e293b"           # 深蓝灰背景
PANEL = "#334155"        # 面板背景
BTN = "#3b82f6"          # 主按钮蓝
BTN_HOVER = "#2563eb"    # 按钮悬停
BTN_GRAY = "#475569"     # 次要按钮
BTN_RED = "#dc2626"      # 危险操作红
FG = "#f1f5f9"           # 主文字白
FG_SECONDARY = "#cbd5e1" # 次要文字
YELLOW = "#fbbf24"       # 强调黄
GREEN = "#22c55e"        # 成功绿
RED = "#ef4444"          # 错误红
ENTRY_BG = "#0f172a"     # 输入框背景
BORDER = "#475569"       # 边框色

FONT_TITLE = ("微软雅黑", 12, "bold")
FONT_BODY = ("微软雅黑", 10)
FONT_BTN = ("微软雅黑", 10, "bold")
FONT_SMALL = ("微软雅黑", 9)

# 状态 / 广播类型 中英文映射
STATUS_ZH2EN = {
    "计划中": "Scheduled", "检票中": "Boarding", "晚点": "Delayed",
    "已发车": "Departed", "已到达": "Arrived", "取消": "Cancelled",
}
STATUS_EN2ZH = {v: k for k, v in STATUS_ZH2EN.items()}
BTYPE_ZH2EN = {
    "检票广播": "BoardingAnnouncement",
    "晚点广播": "DelayAnnouncement",
    "安全提醒": "SafetyReminder",
    "紧急通知": "EmergencyNotice",
    "欢迎词": "WelcomeMessage",
    "欢送词": "FarewellMessage",
    "站台变更": "PlatformChange",
}

AUDIO_STATUS_ZH = {
    "idle": "空闲", "playing": "播放中", "paused": "已暂停",
    "stopped": "已停止", "error": "错误", "unknown": "未知",
}


class MainWindow:
    def __init__(self, client, on_logout=None):
        self.client = client
        self.on_logout = on_logout
        self.root = tk.Tk()
        self.root.title("火车站广播调度系统 - 主控制台")
        self.root.geometry("1080x680")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.minsize(900, 550)
        self._center()

        self.allow_close = False  # 仅由"关闭系统"按钮置真

        # 拦截窗口直接关闭（右上角 X / Alt+F4），并灰掉标题栏关闭按钮
        self.root.protocol("WM_DELETE_WINDOW", self._on_force_close)
        self.root.after(100, lambda: disable_close_button(self.root))

        # 配置 ttk 样式
        self._setup_styles()

        self._build()
        self.refresh_trains()
        self.refresh_status()

        # 定时自动刷新状态
        self._poll()

    def _setup_styles(self):
        """配置 ttk 样式，使界面更美观"""
        style = ttk.Style()
        style.theme_use('clam')

        # Treeview 样式
        style.configure("Custom.Treeview",
                       background=ENTRY_BG,
                       foreground=FG,
                       fieldbackground=ENTRY_BG,
                       rowheight=28,
                       font=FONT_BODY)
        style.configure("Custom.Treeview.Heading",
                       background=PANEL,
                       foreground=FG,
                       font=FONT_BTN,
                       relief="flat")
        style.map("Custom.Treeview",
                 background=[('selected', BTN)],
                 foreground=[('selected', FG)])
        style.map("Custom.Treeview.Heading",
                 background=[('active', BTN_HOVER)])

        # Combobox 样式
        style.configure("Custom.TCombobox",
                       fieldbackground=ENTRY_BG,
                       background=PANEL,
                       foreground=FG,
                       arrowcolor=FG)
        style.map("Custom.TCombobox",
                 fieldbackground=[('readonly', ENTRY_BG)],
                 selectbackground=[('readonly', BTN)])

    def _center(self):
        self.root.update_idletasks()
        w, h = 1080, 680
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ---------- 关闭保护 ----------
    def _on_force_close(self):
        if not self.allow_close:
            messagebox.showwarning(
                "提示",
                "请通过界面右下角的【关闭系统】按钮退出系统，不允许直接关闭窗口。",
                parent=self.root)

    # ---------- 界面构建 ----------
    def _build(self):
        # 创建主框架，使用 grid 布局更灵活
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame = tk.Frame(self.root, bg=BG)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # ===== 左侧：车次管理 =====
        left = tk.LabelFrame(main_frame, text=" 车次管理 ", bg=BG, fg=FG,
                            font=FONT_TITLE, bd=1, relief="solid",
                            highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        # 车次列表 - 使用自定义样式
        cols = ("车次", "始发", "到达", "时间", "站台", "状态")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=10,
                                 style="Custom.Treeview")
        widths = [80, 100, 100, 100, 60, 80]
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="center", minwidth=50)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        # 添加滚动条
        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", pady=8)
        self.tree.configure(yscrollcommand=vsb.set)

        # 添加表单 - 使用 grid 布局
        form_frame = tk.Frame(left, bg=BG)
        form_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)

        self.ent = {}
        fields = [
            ("车次号：", "number", 0, 0),
            ("始发站：", "dep", 0, 2),
            ("到达站：", "arr", 1, 0),
            ("发车时间：", "deptime", 1, 2),
            ("站台：", "platform", 2, 0),
        ]
        for label, key, r, c in fields:
            tk.Label(form_frame, text=label, bg=BG, fg=FG_SECONDARY, font=FONT_BODY).grid(
                row=r, column=c, padx=5, pady=6, sticky="e")
            e = tk.Entry(form_frame, width=12, font=FONT_BODY, bg=ENTRY_BG, fg=FG,
                         insertbackground=FG, relief="flat", highlightthickness=1,
                         highlightcolor=BORDER, highlightbackground=BORDER)
            e.grid(row=r, column=c + 1, padx=5, pady=6, sticky="ew")
            self.ent[key] = e

        tk.Label(form_frame, text="状态：", bg=BG, fg=FG_SECONDARY, font=FONT_BODY).grid(
            row=2, column=2, padx=5, pady=6, sticky="e")
        self.cmb_status = ttk.Combobox(form_frame, width=10, font=FONT_BODY, state="readonly",
                                        values=list(STATUS_ZH2EN.keys()),
                                        style="Custom.TCombobox")
        self.cmb_status.current(0)
        self.cmb_status.grid(row=2, column=3, padx=5, pady=6, sticky="ew")

        # 车次按钮
        btns = tk.Frame(left, bg=BG)
        btns.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        btns.columnconfigure((0,1,2,3), weight=1)

        tk.Button(btns, text="添加", width=10, font=FONT_BTN, bg=BTN, fg=FG,
                  relief="flat", cursor="hand2", command=self._add_train).grid(
            row=0, column=0, padx=4, pady=4, sticky="ew")
        tk.Button(btns, text="更新状态", width=10, font=FONT_BTN, bg=BTN_GRAY, fg=FG,
                  relief="flat", cursor="hand2", command=self._update_status).grid(
            row=0, column=1, padx=4, pady=4, sticky="ew")
        tk.Button(btns, text="移除选中", width=10, font=FONT_BTN, bg=BTN_RED, fg=FG,
                  relief="flat", cursor="hand2", command=self._remove_train).grid(
            row=0, column=2, padx=4, pady=4, sticky="ew")
        tk.Button(btns, text="刷新列表", width=10, font=FONT_BTN, bg=BTN_GRAY, fg=FG,
                  relief="flat", cursor="hand2", command=self.refresh_trains).grid(
            row=0, column=3, padx=4, pady=4, sticky="ew")

        # ===== 右侧容器 =====
        right = tk.Frame(main_frame, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)

        # ===== 手动广播 =====
        brd = tk.LabelFrame(right, text=" 手动广播 ", bg=BG, fg=FG,
                            font=FONT_TITLE, bd=1, relief="solid",
                            highlightbackground=BORDER, highlightthickness=1)
        brd.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        brd.columnconfigure((0,1,2,3), weight=1)

        # 预设按钮
        preset = tk.Frame(brd, bg=BG)
        preset.grid(row=0, column=0, columnspan=4, sticky="ew", padx=8, pady=8)
        preset.columnconfigure((0,1,2,3), weight=1)

        for i, (zh, btype) in enumerate([
            ("检票广播", "BoardingAnnouncement"),
            ("晚点广播", "DelayAnnouncement"),
            ("安全提醒", "SafetyReminder"),
            ("紧急通知", "EmergencyNotice"),
        ]):
            color = BTN_RED if zh == "紧急通知" else BTN
            tk.Button(preset, text=zh, width=10, font=FONT_BTN, bg=color, fg=FG,
                      relief="flat", cursor="hand2",
                      command=lambda b=btype: self._preset_broadcast(b)).grid(
                row=0, column=i, padx=4, sticky="ew")

        # 广播设置行
        settings = tk.Frame(brd, bg=BG)
        settings.grid(row=1, column=0, columnspan=4, sticky="ew", padx=8, pady=4)

        tk.Label(settings, text="类型：", bg=BG, fg=FG_SECONDARY, font=FONT_BODY).pack(side="left", padx=(0, 5))
        self.cmb_btype = ttk.Combobox(settings, width=14, font=FONT_BODY, state="readonly",
                                     values=list(BTYPE_ZH2EN.keys()),
                                     style="Custom.TCombobox")
        self.cmb_btype.current(0)
        self.cmb_btype.pack(side="left", padx=(0, 15))

        tk.Label(settings, text="优先级：", bg=BG, fg=FG_SECONDARY, font=FONT_BODY).pack(side="left", padx=(0, 5))
        self.spin_pri = tk.Spinbox(settings, from_=1, to=10, width=6, font=FONT_BODY,
                                   bg=ENTRY_BG, fg=FG, relief="flat", insertbackground=FG,
                                   buttonbackground=PANEL)
        self.spin_pri.delete(0, "end")
        self.spin_pri.insert(0, "5")
        self.spin_pri.pack(side="left", padx=(0, 15))

        # 内容输入
        content_frame = tk.Frame(brd, bg=BG)
        content_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=8, pady=4)
        content_frame.columnconfigure(1, weight=1)

        tk.Label(content_frame, text="内容：", bg=BG, fg=FG_SECONDARY, font=FONT_BODY).grid(row=0, column=0, padx=(0, 5))
        self.txt_msg = tk.Entry(content_frame, font=FONT_BODY, bg=ENTRY_BG, fg=FG,
                                insertbackground=FG, relief="flat", highlightthickness=1,
                                highlightcolor=BORDER, highlightbackground=BORDER)
        self.txt_msg.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        tk.Button(content_frame, text="发送广播", width=12, font=FONT_BTN, bg=BTN, fg=FG,
                  relief="flat", cursor="hand2", command=self._send_manual).grid(row=0, column=2)

        # ===== 音频控制 =====
        aud = tk.LabelFrame(right, text=" 音频控制 ", bg=BG, fg=FG,
                            font=FONT_TITLE, bd=1, relief="solid",
                            highlightbackground=BORDER, highlightthickness=1)
        aud.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        aud.columnconfigure(1, weight=1)

        # 音频文件行
        file_frame = tk.Frame(aud, bg=BG)
        file_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=8)
        file_frame.columnconfigure(1, weight=1)

        tk.Label(file_frame, text="音频文件：", bg=BG, fg=FG_SECONDARY, font=FONT_BODY).grid(row=0, column=0, padx=(0, 5))
        self.ent_audio = tk.Entry(file_frame, font=FONT_BODY, bg=ENTRY_BG, fg=FG,
                                  insertbackground=FG, relief="flat", highlightthickness=1,
                                  highlightcolor=BORDER, highlightbackground=BORDER)
        self.ent_audio.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        tk.Button(file_frame, text="播放", width=8, font=FONT_BTN, bg=BTN, fg=FG,
                  relief="flat", cursor="hand2", command=self._play_audio).grid(row=0, column=2)

        # 控制按钮行
        ab = tk.Frame(aud, bg=BG)
        ab.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8, pady=4)
        ab.columnconfigure((0,1,2,3), weight=1)

        for i, (txt, fn) in enumerate([
            ("停止", self._stop_audio), ("暂停", self._pause_audio),
            ("恢复", self._resume_audio), ("刷新状态", self.refresh_status),
        ]):
            color = BTN_RED if txt == "停止" else BTN_GRAY
            tk.Button(ab, text=txt, width=10, font=FONT_BTN, bg=color, fg=FG,
                      relief="flat", cursor="hand2", command=fn).grid(row=0, column=i, padx=4, sticky="ew")

        # 音量控制行
        vol_frame = tk.Frame(aud, bg=BG)
        vol_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8, pady=8)
        vol_frame.columnconfigure(1, weight=1)

        tk.Label(vol_frame, text="音量：", bg=BG, fg=FG_SECONDARY, font=FONT_BODY).grid(row=0, column=0, padx=(0, 5))
        self.vol = tk.Scale(vol_frame, from_=0, to=100, orient="horizontal",
                            bg=PANEL, fg=FG, highlightthickness=0, troughcolor=ENTRY_BG,
                            activebackground=BTN, sliderlength=20, width=12)
        self.vol.set(80)
        self.vol.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        tk.Button(vol_frame, text="设置音量", width=10, font=FONT_BTN, bg=BTN_GRAY, fg=FG,
                  relief="flat", cursor="hand2", command=self._set_volume).grid(row=0, column=2)

        # ===== 系统状态 =====
        sysf = tk.LabelFrame(right, text=" 系统状态 ", bg=BG, fg=FG,
                             font=FONT_TITLE, bd=1, relief="solid",
                             highlightbackground=BORDER, highlightthickness=1)
        sysf.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        sysf.columnconfigure(0, weight=1)

        # 自动广播模式
        self.var_auto = tk.IntVar(value=1)
        chk = tk.Checkbutton(sysf, text="自动广播模式", variable=self.var_auto,
                             bg=BG, fg=FG, font=FONT_BODY, selectcolor=BTN,
                             activebackground=BG, activeforeground=FG,
                             command=self._toggle_auto, cursor="hand2")
        chk.grid(row=0, column=0, sticky="w", padx=8, pady=8)

        # 状态标签 - 使用不同颜色区分
        self.lbl_queue = tk.Label(sysf, text="队列：-", bg=BG, fg=FG_SECONDARY, font=FONT_BODY, anchor="w")
        self.lbl_queue.grid(row=1, column=0, sticky="ew", padx=8, pady=3)
        self.lbl_audio = tk.Label(sysf, text="音频：-", bg=BG, fg=FG_SECONDARY, font=FONT_BODY, anchor="w")
        self.lbl_audio.grid(row=2, column=0, sticky="ew", padx=8, pady=3)
        self.lbl_sys = tk.Label(sysf, text="系统：-", bg=BG, fg=FG_SECONDARY, font=FONT_BODY, anchor="w")
        self.lbl_sys.grid(row=3, column=0, sticky="ew", padx=8, pady=3)

        # ===== 底部状态栏 =====
        bottom = tk.Frame(self.root, bg=PANEL, relief="flat")
        bottom.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom.columnconfigure(0, weight=1)

        self.lbl_status = tk.Label(bottom, text="就绪", bg=PANEL, fg=FG,
                                   font=FONT_SMALL, anchor="w", padx=10)
        self.lbl_status.grid(row=0, column=0, sticky="ew")

        btn_frame = tk.Frame(bottom, bg=PANEL)
        btn_frame.grid(row=0, column=1, padx=5)

        tk.Button(btn_frame, text="退出登录", width=12, font=FONT_BTN, bg=BTN_GRAY, fg=FG,
                  relief="flat", cursor="hand2", command=self._logout).pack(side="left", padx=4)
        tk.Button(btn_frame, text="关闭系统", width=12, font=FONT_BTN, bg=BTN_RED, fg=FG,
                  relief="flat", cursor="hand2", command=self._shutdown).pack(side="left", padx=4)

    def _set_status(self, text):
        self.lbl_status.config(text=text)

    # ---------- 车次操作 ----------
    def refresh_trains(self):
        ok, trains = self.client.get_trains()
        self.tree.delete(*self.tree.get_children())
        if not ok:
            self._set_status("车次列表获取失败")
            return
        for t in trains:
            self.tree.insert("", "end", values=(
                t.get("train_number", ""),
                t.get("departure_station", ""),
                t.get("arrival_station", ""),
                t.get("departure_time", ""),
                t.get("platform", ""),
                STATUS_EN2ZH.get(t.get("status", ""), t.get("status", "")),
            ))
        self._set_status(f"车次共 {len(trains)} 列")

    def _selected_number(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先在列表中选择一列车次", parent=self.root)
            return None
        return self.tree.item(sel[0], "values")[0]

    def _add_train(self):
        num = self.ent["number"].get().strip()
        dep = self.ent["dep"].get().strip()
        arr = self.ent["arr"].get().strip()
        dt = self.ent["deptime"].get().strip()
        plat = self.ent["platform"].get().strip()
        if not num:
            messagebox.showwarning("提示", "请输入车次号", parent=self.root)
            return
        status_en = STATUS_ZH2EN.get(self.cmb_status.get(), "Scheduled")
        ok, msg = self.client.add_train(num, dep, arr, dt, plat, status_en)
        self._set_status(msg)
        if ok:
            for k in self.ent:
                self.ent[k].delete(0, "end")
            self.refresh_trains()

    def _update_status(self):
        num = self._selected_number()
        if not num:
            return
        status_en = STATUS_ZH2EN.get(self.cmb_status.get(), "Scheduled")
        ok, msg = self.client.update_train_status(num, status_en)
        self._set_status(msg)
        if ok:
            self.refresh_trains()
            self.refresh_status()

    def _remove_train(self):
        num = self._selected_number()
        if not num:
            return
        if not messagebox.askyesno("确认", f"确定移除车次 {num}？", parent=self.root):
            return
        ok, msg = self.client.remove_train(num)
        self._set_status(msg)
        if ok:
            self.refresh_trains()

    # ---------- 广播 ----------
    def _preset_broadcast(self, btype_en):
        self.cmb_btype.set({v: k for k, v in BTYPE_ZH2EN.items()}[btype_en])
        self.txt_msg.delete(0, "end")

    def _send_manual(self):
        btype_en = BTYPE_ZH2EN.get(self.cmb_btype.get(), "SafetyReminder")
        msg = self.txt_msg.get().strip()
        if not msg:
            messagebox.showwarning("提示", "请输入广播内容", parent=self.root)
            return
        try:
            pri = int(self.spin_pri.get())
        except ValueError:
            pri = 5
        ok, r = self.client.add_manual_broadcast(btype_en, msg, pri)
        self._set_status(r)
        if ok:
            self.txt_msg.delete(0, "end")
            self.refresh_status()

    # ---------- 音频 ----------
    def _play_audio(self):
        p = self.ent_audio.get().strip()
        if not p:
            messagebox.showwarning("提示", "请输入音频文件名或路径", parent=self.root)
            return
        ok, r = self.client.play_audio(p)
        self._set_status(r)
        self.refresh_status()

    def _stop_audio(self):
        ok, r = self.client.stop_audio()
        self._set_status(r)
        self.refresh_status()

    def _pause_audio(self):
        ok, r = self.client.pause_audio()
        self._set_status(r)
        self.refresh_status()

    def _resume_audio(self):
        ok, r = self.client.resume_audio()
        self._set_status(r)
        self.refresh_status()

    def _set_volume(self):
        v = int(self.vol.get()) / 100.0
        ok, r = self.client.set_volume(v)
        self._set_status(r)

    # ---------- 状态 ----------
    def refresh_status(self):
        try:
            size, nxt = self.client.get_queue_status()
            self.lbl_queue.config(text=f"队列：待播 {size} 条；下一条：{nxt or '无'}", fg=FG_SECONDARY)

            st, cur = self.client.get_audio_status()
            status_text = AUDIO_STATUS_ZH.get(st, st)
            # 根据状态设置不同颜色
            if st == "playing":
                audio_color = GREEN
            elif st == "error":
                audio_color = RED
            else:
                audio_color = FG_SECONDARY
            self.lbl_audio.config(
                text=f"音频：{status_text}" + (f"（{cur}）" if cur else ""), fg=audio_color)

            run, auto, acct, q = self.client.get_system_status()
            sys_color = GREEN if run else RED
            self.lbl_sys.config(
                text=f"系统：{'运行中' if run else '已停止'}；自动模式 {'开' if auto else '关'}；账号 {acct} 个；队列 {q}",
                fg=sys_color)
        except Exception as e:
            self._set_status(f"刷新状态失败: {e}")

    def _toggle_auto(self):
        ok, r = self.client.set_auto_mode(bool(self.var_auto.get()))
        self._set_status(r)

    # ---------- 退出 ----------
    def _logout(self):
        if not messagebox.askyesno("确认", "确定退出登录并返回登录窗口？", parent=self.root):
            return
        self.allow_close = True
        self.root.destroy()
        if self.on_logout:
            self.on_logout()

    def _shutdown(self):
        if not messagebox.askyesno("确认", "确定关闭整个系统并停止后端服务？", parent=self.root):
            return
        ok, r = self.client.shutdown()
        self._set_status(r)
        self.allow_close = True
        self.root.after(600, self.root.destroy)

    # ---------- 定时刷新 ----------
    def _poll(self):
        """定时刷新状态，带异常处理防止崩溃"""
        if not self.root.winfo_exists():
            return
        try:
            if self.client.connected:
                self.refresh_status()
        except Exception as e:
            # 静默处理，避免频繁弹窗
            pass
        finally:
            # 确保即使出错也会继续轮询
            if self.root.winfo_exists():
                self.root.after(3000, self._poll)

    def run(self):
        self.root.mainloop()
