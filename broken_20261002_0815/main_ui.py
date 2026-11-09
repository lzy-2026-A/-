# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import ttk, messagebox
import time
import socket
import json
import os
import sys

# 配置
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ===== 广播类型（配置化，可在广播设置中自定义排序/添加）=====
DEFAULT_BC_TYPES = [
    "检票预告", "开始检票", "停止检票",
    "紧急-列车晚点·天气原因", "紧急-列车晚点·设备故障",
    "紧急-列车晚点·线路施工", "紧急-列车晚点·自然灾害",
    "紧急-列车晚点·行车事故", "紧急-列车晚点·列车超员",
    "紧急-列车晚点（通用）",
    "紧急-列车停运·天气原因", "紧急-列车停运·设备故障",
    "紧急-列车停运·线路施工", "紧急-列车停运·自然灾害",
    "紧急-列车停运·行车事故", "紧急-列车停运·列车超员",
    "紧急-列车停运（通用）",
    "紧急-变更站台", "紧急-旅客突发",
]
CHECKIN_TYPES = ("检票预告", "开始检票", "停止检票")

# ===== 设计变量（统一 UI：颜色/间距/圆角/字号）=====
DS = {
    "bg": "#0a0e1a",          # 页面背景
    "panel": "#111930",       # 卡片面板
    "panel2": "#0d1525",      # 内嵌面板
    "accent": "#4a9eff",      # 主色/强调
    "text": "#e8eef7",        # 主文字
    "text_dim": "#8899bb",    # 次要文字
    "text_faint": "#667",     # 弱化文字
    "btn": "#1a2540",         # 中性按钮
    "btn_hover": "#243560",
    "btn_primary": "#1e5bbf", "btn_primary_hover": "#2a7adf",
    "btn_success": "#1e7a3a", "btn_success_hover": "#2a9a4a",
    "btn_danger": "#8a2a2a", "btn_danger_hover": "#aa3a3a",
    "btn_warn": "#8a6a1a", "btn_warn_hover": "#aa8a2a",
    "btn_neutral": "#555", "btn_neutral_hover": "#777",
    "nav_active": "#1e3a5f", "nav_hover": "#16233f",
    "nav_border": "#2a6adf",
    "row1": "#141d33", "row2": "#0f1730",   # 表格斑马纹
    "row_sel": "#2a4a7a",                   # 表格选中
    "ok": "#4d4", "warn": "#f80", "err": "#f66",
    "radius": 10, "radius_sm": 6,
    "font": "Microsoft YaHei",
}

def zebra(tree):
    """给 Treeview 行加斑马纹 tag"""
    for i, c in enumerate(tree.get_children()):
        tree.item(c, tags=("even" if i % 2 == 0 else "odd",))

# 数字字符 → 汉字（新语音包"单个字"目录用汉字文件名）
CN_DIGITS = {"0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
             "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"}

APP_TITLE = "旅客服务智能管理广播系统"
APP_VERSION = "V26.9.25"

# TCP 连接（连 Rust 后端）
TCP_HOST = "127.0.0.1"
TCP_PORT = 8888

# 获取项目根目录
def get_app_root():
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_project_root():
    """项目根目录（开发/打包一致）：配置文件固定放这里。
    打包版 app_root 为 dist 目录，配置若写那里会被重新打包时删除 → 永久丢失。
    因此按音频库位置反推项目根（项目根\audio\语音包 或 项目根\audio）。"""
    ad = AUDIO_DIR
    try:
        if os.path.basename(ad) == "语音包":
            return os.path.dirname(os.path.dirname(ad))
        if os.path.basename(ad) == "audio":
            return os.path.dirname(ad)
    except Exception:
        pass
    return get_app_root()

def _audio_usable(d):
    """音频库可用判定：必须含 media2 或 media3（避免命中只剩 startup.mp3 的空壳）"""
    return os.path.isdir(d) and (
        os.path.isdir(os.path.join(d, "media2")) or
        os.path.isdir(os.path.join(d, "media3"))
    )

# 自动探测音频目录（开发/打包都能用；优先最新语音包，绝不回退旧库）
def get_audio_dir():
    root = get_app_root()
    # 1) 项目根 audio\语音包（用户最新整合库，优先）
    for vp in (os.path.join(root, "audio", "语音包"),
               os.path.join(root, "..", "audio", "语音包"),
               os.path.join(root, "..", "..", "audio", "语音包"),
               os.path.join(root, "..", "..", "..", "audio", "语音包")):
        vpa = os.path.abspath(vp)
        if os.path.isdir(os.path.join(vpa, "单个字")) and os.path.isdir(os.path.join(vpa, "车站")):
            return vpa
    # 2) 常规 audio 目录（含 media2/media3）
    for candidate in (
        os.path.join(root, "audio"),
        os.path.join(root, "..", "audio"),
        os.path.join(root, "..", "..", "audio"),
        os.path.join(root, "..", "..", "..", "audio"),
    ):
        cand = os.path.abspath(candidate)
        if _audio_usable(cand):
            return cand
    return os.path.join(root, "audio")

AUDIO_DIR = get_audio_dir()

# ===== 任务栏图标/分组：显式 AppUserModelID（修复任务栏显示 Python 默认图标）=====
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PassengerBroadcastSystem.1.0")
except Exception:
    pass

# ===== 单实例锁：同一时间只允许一个 main_ui 进程（重复启动被拦截）=====
def pv_stretch(data, rate, sr):
    """相位声码器时间拉伸：严格保持音调、重叠相加无爆音。
    用于大幅变速（<0.95x 或 >1.05x），纯 numpy 实现。"""
    import numpy as np
    if abs(rate - 1.0) < 1e-3 or len(data) < 2048:
        return data
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = np.asarray(data, dtype=np.float64)
    n = len(data)
    win = int(sr * 0.032)
    hop = win // 3
    if hop < 64:
        hop = 64
    if win > n:
        win = max(256, n // 2)
        hop = win // 3
    w = np.hanning(win)
    frames = []
    for i in range(0, n - win, hop):
        frames.append(data[i:i + win] * w)
    if not frames:
        return data
    X = np.fft.rfft(np.array(frames), axis=1)
    mag = np.abs(X)
    ana_phase = np.angle(X)
    n_frames = len(frames)
    hop_out = hop / rate
    n_out = max(int(n / rate), 1)
    out = np.zeros(n_out + win)
    out_phase = ana_phase[0].copy()
    prev_ana = ana_phase[0].copy()
    bin_freq = np.fft.rfftfreq(win, 1.0 / sr)
    expected_dp = 2 * np.pi * bin_freq * hop / sr
    hop_ratio = hop_out / hop
    for f in range(n_frames):
        if f > 0:
            dp = ana_phase[f] - prev_ana
            dp -= np.round((dp - expected_dp) / (2 * np.pi)) * 2 * np.pi
            out_phase = out_phase + dp * hop_ratio
        else:
            out_phase = ana_phase[0].copy()
        Y = mag[f] * np.exp(1j * out_phase)
        frame = np.fft.irfft(Y, win)
        idx = int(round(f * hop_out))
        if idx + win > len(out):
            break
        out[idx:idx + win] += frame * w
        prev_ana = ana_phase[f]
    out /= (win / hop / 2.0)
    p_in = np.abs(data).max()
    p_out = np.abs(out).max()
    if p_out > 1e-9 and p_in > 1e-9:
        out *= (p_in / p_out)
    return out[:n_out]


def wsola_stretch(data, rate, sr):
    """WSOLA 时间拉伸：只改变播放速度、不改变音调。
    rate>1 变快（缩短），rate<1 变慢（拉长），纯 numpy 实现，无额外依赖。
    大幅变速（|rate-1|>0.05）自动切换到相位声码器，保证音调与无爆音。"""
    import numpy as np
    if abs(rate - 1.0) < 1e-3 or len(data) < 2048:
        return data
    if abs(rate - 1.0) > 0.05:
        return pv_stretch(data, rate, sr)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = np.asarray(data, dtype=np.float64)
    n = len(data)
    n_out = max(int(n / rate), 1)
    win = int(sr * 0.030)
    if win < 256:
        win = 256
    if win > n:
        win = max(128, n // 2)
    hop_out = max(int(win / rate), 1)
    out = np.zeros(n_out)
    w0 = min(win, n_out)
    out[0:w0] = data[0:w0]
    out_pos = win
    ana_pos = win
    prev_gap_start = None
    sear = max(1, int(win * 0.25))
    step = max(1, win // 128)
    while ana_pos + win <= n and out_pos + win <= n_out:
        tail = out[out_pos - win:out_pos]
        lo = max(0, ana_pos - sear)
        hi = min(n - win, ana_pos + sear)
        best = ana_pos
        best_v = -1e18
        for c in range(lo, hi + 1, step):
            seg = data[c:c + win]
            v = np.dot(tail, seg) / (np.linalg.norm(seg) + 1e-9)
            if v > best_v:
                best_v = v
                best = c
        ov = win - hop_out
        if ov > 0:
            # 变快：相邻帧重叠交叉淡化（音调不变）
            ramp = np.linspace(1.0, 0.0, ov)
            s0 = data[best:best + ov]
            out[out_pos - ov:out_pos] = out[out_pos - ov:out_pos] * ramp + s0 * (1.0 - ramp)
            out[out_pos:out_pos + hop_out] = data[best + ov:best + ov + hop_out]
        else:
            # 变慢：帧原样放置；帧间过渡区 = 上帧尾淡出 + 本帧头淡入（平滑衔接防爆音）
            out[out_pos:out_pos + win] = data[best:best + win]
            gap = hop_out - win
            if gap > 0 and out_pos + win + gap <= n_out:
                ramp = np.linspace(1.0, 0.0, gap)
                out[out_pos + win:out_pos + win + gap] = data[best + win - 1] * ramp
                if prev_gap_start is not None and prev_gap_start + gap <= n_out:
                    s2 = data[best:best + gap]
                    ramp2 = np.linspace(0.0, 1.0, gap)
                    out[prev_gap_start:prev_gap_start + gap] += s2 * ramp2
                prev_gap_start = out_pos + win
            else:
                prev_gap_start = None
        out_pos += hop_out
        ana_pos = best + win
    if out_pos < n_out and ana_pos < n:
        rem = min(n_out - out_pos, n - ana_pos)
        if rem > 0:
            seg = data[ana_pos:ana_pos + rem].copy()
            ramp_n = min(rem, 512)
            ramp = np.linspace(0.0, 1.0, ramp_n)
            seg[:ramp_n] = seg[:ramp_n] * ramp
            out[out_pos:out_pos + rem] = seg
    return out


def _acquire_single_instance():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 27890))
        s.listen(1)
    except OSError:
        # 已有实例在运行 → 提示并退出
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, "程序已经在运行中，请勿重复启动。", "旅客服务智能管理广播系统", 0x40)
        except Exception:
            pass
        sys.exit(1)
    return s

_SINGLE_SOCK = _acquire_single_instance()

class BroadcastApp(ctk.CTk):
    def __init__(self, username="admin"):
        super().__init__()
        self.username = username
        self.title(APP_TITLE)
        self.geometry("1400x800")
        # 窗口/任务栏图标：多路径查找（开发=项目根；打包=exe 同目录/_MEIPASS，均能生效）
        try:
            _ico = None
            for _cand in (os.path.join(get_project_root(), "ico", "app.ico"),
                          os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                                       "ico", "app.ico"),
                          os.path.join(getattr(sys, "_MEIPASS", ""),
                                       "ico", "app.ico")):
                if _cand and os.path.exists(_cand):
                    _ico = _cand
                    break
            if _ico:
                self.iconbitmap(_ico)
        except Exception:
            pass
        # 拦截右上角关闭按钮
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        # 延迟调用 Windows 系统最大化
        self.after(100, self.maximize_window)
        # 初始化 UI
        self.__init_body()

    def maximize_window(self):
        """调用 Windows 系统最大化窗口"""
        try:
            self.wm_state('zoomed')
        except:
            pass

    def on_closing(self):
        """拦截关闭按钮"""
        import tkinter.messagebox as messagebox
        messagebox.showwarning("提示", "请在右下角点击「关闭系统」退出")

    def __init_body(self):
        # TCP 连接
        self.tcp_sock = None
        # ===== 广播状态统一数据源（车次树状态列 + 大屏同源）=====
        self._train_states = {}          # {车次: 当前状态}
        self._train_state_prev = {}      # {车次: 播放前状态}
        self._active_bcast_train = None  # 当前播放涉及的车次
        self._stop_flag = False          # 停止播放标志（合成/播放阶段均可中止）

        # 配置网格布局
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 顶部栏
        self.create_header()

        # 左侧导航
        self.create_sidebar()

        # 右侧内容区
        self.create_content()

        # 底部状态栏
        self.create_footer()

        # 时钟更新
        self.update_clock()

        # TCP 连接延迟到窗口显示后，加快启动速度
        self.after(500, self.connect_tcp)

    def create_header(self):
        """顶部栏"""
        header = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color="#141d30")
        header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header.grid_propagate(False)

        # Logo
        logo = ctk.CTkLabel(header, text="🚄", font=ctk.CTkFont(size=28))
        logo.pack(side="left", padx=15, pady=10)

        # 标题
        title = ctk.CTkLabel(header, text=APP_TITLE, font=ctk.CTkFont(size=20, weight="bold"), text_color="#ffffff")
        title.pack(side="left", padx=10)

        # 右侧：时钟 + 用户
        self.clock_label = ctk.CTkLabel(header, text="00:00:00", font=ctk.CTkFont(size=16, family="Consolas"), text_color=DS["accent"])
        self.clock_label.pack(side="right", padx=20)

        user = ctk.CTkLabel(header, text=f"用户：{self.username}", font=ctk.CTkFont(size=14), text_color=DS["text_dim"])
        user.pack(side="right", padx=10)

    def create_sidebar(self):
        """左侧导航栏"""
        sidebar = ctk.CTkFrame(self, width=180, corner_radius=0, fg_color=DS["panel2"])
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # 导航按钮
        self.nav_buttons = []
        nav_items = [
            ("📢 广播管理", self.show_broadcast_with_startup),
            ("🚆 车辆管理", self.show_train),
            ("🖥️ 车站大屏", self.show_screen),
            ("⚙️ 系统设置", self.show_system),
            ("🔊 广播设置", self.show_bcast_set),
        ]

        for i, (text, cmd) in enumerate(nav_items):
            btn = ctk.CTkButton(
                sidebar, text=text, command=cmd,
                font=ctk.CTkFont(size=14),
                fg_color="transparent", hover_color=DS["nav_hover"],
                text_color=DS["text_dim"], anchor="w",
                height=48, corner_radius=6,
                border_spacing=15
            )
            btn.pack(fill="x", padx=10, pady=3)
            self.nav_buttons.append(btn)

        # 默认选中第一个
        self.set_active_nav(0)

    def set_active_nav(self, index):
        """设置选中的导航"""
        for i, btn in enumerate(self.nav_buttons):
            if i == index:
                btn.configure(fg_color=DS["nav_active"], text_color=DS["accent"], border_width=2, border_color=DS["nav_border"])
            else:
                btn.configure(fg_color="transparent", text_color=DS["text_dim"], border_width=0)

    def create_content(self):
        """右侧内容区"""
        self.content_frame = ctk.CTkFrame(self, fg_color=DS["bg"], corner_radius=0)
        self.content_frame.grid(row=1, column=1, sticky="nsew", padx=15, pady=15)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # 广播管理面板（默认显示）
        self.broadcast_panel = self.create_broadcast_panel()
        self.broadcast_panel.grid(row=0, column=0, sticky="nsew")

        # 车辆管理面板
        self.train_panel = self.create_train_panel()
        self.train_panel.grid(row=0, column=0, sticky="nsew")
        self.train_panel.grid_remove()

        # 车站大屏面板
        self.screen_panel = self.create_screen_panel()
        self.screen_panel.grid(row=0, column=0, sticky="nsew")
        self.screen_panel.grid_remove()

        # 系统设置面板（含定时广播）
        self.system_panel = self.create_system_panel()
        self.system_panel.grid(row=0, column=0, sticky="nsew")
        self.system_panel.grid_remove()

        # 广播设置面板
        self.create_bcast_set_panel()
        # 加载已保存的广播配置（开始音/结束音/步骤/映射）
        self.load_bc_config()
        # 定时广播轮询（每秒检查，到点自动播放）
        self.refresh_sched_train_list()
        self.after(1000, self._schedule_tick)

    def create_screen_panel(self):
        """车站大屏：高铁站电子屏风格（深蓝底、双语表头、彩色状态、按开车时间自动变状态）"""
        BLUE_D = "#04294a"
        BLUE_H = "#06355c"
        panel = ctk.CTkFrame(self.content_frame, fg_color=BLUE_D, corner_radius=0)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        # ===== 顶部：标题 + 时间 + 欢迎横幅 =====
        head = ctk.CTkFrame(panel, fg_color=BLUE_H, corner_radius=0, height=118)
        head.grid(row=0, column=0, sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        head.grid_propagate(False)
        ctk.CTkLabel(head, text="旅客服务智能管理广播系统 · 车站大屏",
                    font=ctk.CTkFont(size=22, weight="bold"),
                    text_color="#9fd4ff").grid(row=0, column=0, sticky="w", padx=30, pady=(14, 0))
        self.screen_clock = ctk.CTkLabel(head, text="--:--:--",
                                         font=ctk.CTkFont(size=34, weight="bold"),
                                         text_color="#ffffff")
        self.screen_clock.grid(row=0, column=1, sticky="e", padx=30, pady=(8, 0))
        self.screen_date = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=15), text_color="#9fc8ee")
        self.screen_date.grid(row=1, column=1, sticky="e", padx=30)
        # 欢迎横幅（站名来自系统设置：车站显示设置）
        self.screen_welcome = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=30, weight="bold"),
                                           text_color="#ffd24d")
        self.screen_welcome.grid(row=2, column=0, columnspan=2, sticky="w", padx=30, pady=(6, 6))

        # ===== 中部：列车表（大字号块状行，参考高铁站电子屏） =====
        mid = ctk.CTkFrame(panel, fg_color=BLUE_D, corner_radius=0)
        mid.grid(row=1, column=0, sticky="nsew", padx=14, pady=(8, 4))
        self.screen_container = mid
        self.screen_rows = {}          # idx -> {labels, raw}
        self._screen_widgets = []      # 自建的表头/行控件（刷新时只销毁这些）
        self._build_screen_header(mid)

        # ===== 底部：状态 + 刷新 =====
        foot = ctk.CTkFrame(panel, fg_color=BLUE_H, corner_radius=0)
        foot.grid(row=2, column=0, sticky="ew")
        self.screen_status = ctk.CTkLabel(foot, text="● 大屏运行中",
                                          font=ctk.CTkFont(size=14, weight="bold"), text_color="#6be26b")
        self.screen_status.pack(side="left", padx=24, pady=12)
        ctk.CTkButton(foot, text="🔄 刷新", width=90, height=32, fg_color="#0a4a8a",
                      hover_color="#0d5aa5", font=ctk.CTkFont(size=13),
                      command=self.refresh_screen).pack(side="right", padx=12, pady=8)
        return panel

    # ---------- 大屏表头（双语，参考高铁站电子屏） ----------
    def _build_screen_header(self, mid):
        inner = getattr(mid, "_parent_frame", mid)
        hdr = ["车次 Train", "始发站 From", "开点 Departs", "到点 Arrives",
               "终到站 To", "检票口/车厢 Check-in", "状态 Status"]
        # 表头背景条：与数据行等宽、5 列均分（均匀对称）
        head_frame = ctk.CTkFrame(inner, fg_color="#0d4a8a", corner_radius=6, height=44)
        head_frame.pack(fill="x", padx=0, pady=(0, 8))
        head_frame.pack_propagate(False)
        # uniform 组：列宽严格按权重均分，忽略文字宽度（长表头不撑宽列）
        for i in range(7):
            head_frame.grid_columnconfigure(i, weight=1, minsize=60, uniform="scol")
        for i, h in enumerate(hdr):
            lb = ctk.CTkLabel(head_frame, text=h, font=ctk.CTkFont(size=13, weight="bold"),
                              text_color="#cfe6ff", anchor="center")
            lb.grid(row=0, column=i, sticky="ew", padx=8)
            self._screen_widgets.append(lb)
        self._screen_widgets.append(head_frame)
        return hdr

    # ---------- 大屏数据行（大字号块状行） ----------
    def _add_screen_row(self, mid, idx, r):
        """r: [车次, 类型, 发站, 到站, 开点, 检票口, 站台, 状态]"""
        inner = getattr(mid, "_parent_frame", mid)
        bg = "#0a3a68" if idx % 2 == 0 else "#0b4278"
        row_frame = ctk.CTkFrame(inner, fg_color=bg, corner_radius=6)
        row_frame.pack(fill="x", padx=0, pady=4)
        # 7 列均分（与表头 uniform 一致，保证逐列竖向对齐 + 均匀对称）
        for i in range(7):
            row_frame.grid_columnconfigure(i, weight=1, minsize=60, uniform="scol")
        _arr = str(r[8]) if len(r) > 8 else "--:--"
        vals = [str(r[0]), str(r[2]), str(r[4]), _arr, str(r[3]), str(r[5])]
        labels = []
        for col, v in enumerate(vals):
            lb = ctk.CTkLabel(row_frame, text=v, font=ctk.CTkFont(size=20, weight="bold"),
                              text_color="#ffffff", fg_color="transparent", anchor="center")
            lb.grid(row=0, column=col, sticky="ew", padx=8, pady=6)
            labels.append(lb)
            self._screen_widgets.append(lb)
        st_lb = ctk.CTkLabel(row_frame, text="", font=ctk.CTkFont(size=20, weight="bold"),
                             fg_color="transparent", anchor="center")
        st_lb.grid(row=0, column=6, sticky="ew", padx=8, pady=6)
        labels.append(st_lb)
        self._screen_widgets.append(st_lb)
        self._screen_widgets.append(row_frame)
        self.screen_rows[idx] = {"labels": labels, "raw": r}

    # ---------- 大屏状态列刷新（按开车时间 + 数据状态） ----------
    def _update_screen_statuses(self, smin=None):
        try:
            now = time.localtime()
            now_min = now.tm_hour * 60 + now.tm_min
            smin = smin if smin is not None else 5
            for idx, row in self.screen_rows.items():
                r = row["raw"]
                dep = (str(r[4]) or "").strip()
                # 状态实时读统一数据源（车次树状态列），而非行创建时的快照
                st_txt = ""
                for _c in self.bc_train_tree.get_children():
                    _vals = list(self.bc_train_tree.item(_c)["values"])
                    if _vals and str(_vals[0]) == str(r[0]):
                        st_txt = str(_vals[7]) if len(_vals) > 7 else ""
                        break
                st_txt = st_txt.strip()
                auto = "正在候车"
                if dep:
                    try:
                        hh, mm = dep.split(":")
                        dep_min = int(hh) * 60 + int(mm)
                        if now_min >= dep_min:
                            auto = "停止检票"
                        elif now_min >= dep_min - int(smin):
                            auto = "正在检票"
                        else:
                            auto = "正在候车"
                    except Exception:
                        auto = "正在候车"
                # 所有已知状态一律保留用户设定，绝不被时间逻辑覆盖（"跳回去"修复）
                if st_txt in ("停止检票", "正在检票", "正在候车", "已发车", "晚点", "待检票", "停运",
                              "计划中", "检票中", "已到达", "取消"):
                    disp = st_txt
                else:
                    disp = auto
                color = {"停止检票": "#ff5a5a", "正在检票": "#4dff6e",
                         "正在候车": "#ffd24d", "已发车": "#9aa7b5",
                         "晚点": "#ff9a3d", "待检票": "#9adcff",
                         "停运": "#ff5a5a", "计划中": "#9aa7b5",
                         "检票中": "#4dff6e", "已到达": "#4dff6e",
                         "取消": "#ff5a5a"}.get(disp, "#ffd24d")
                # 状态列始终是行内最后一个 label（与列数无关）
                row["labels"][-1].configure(text=disp, text_color=color)
        except Exception:
            pass

    def create_system_panel(self):
        """系统设置：定时广播（指定时间播放指定广播+车次）"""
        panel = ctk.CTkFrame(self.content_frame, fg_color=DS["panel"], corner_radius=10)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(panel, text="⏰ 定时广播设置（到点自动播放指定广播）",
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=DS["accent"]).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(panel, text="每天到设定时间自动播放：时间(HH:MM) + 广播类型 + 车次（车次可留空=播放默认测试车次）",
                    font=ctk.CTkFont(size=11), text_color=DS["text_dim"]).grid(row=0, column=0, sticky="w", padx=20, pady=(44, 4))

        # ===== 添加区 =====
        add_frame = ctk.CTkFrame(panel, fg_color=DS["panel2"], corner_radius=8)
        add_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(8, 4))
        add_frame.grid_columnconfigure(1, weight=1)
        add_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(add_frame, text="时间:", font=ctk.CTkFont(size=12),
                    text_color=DS["text_dim"]).grid(row=0, column=0, padx=(14, 4), pady=10)
        self.sched_time_entry = ctk.CTkEntry(add_frame, width=90, placeholder_text="08:30",
                                            font=ctk.CTkFont(size=12))
        self.sched_time_entry.grid(row=0, column=1, sticky="w", padx=4, pady=10)

        ctk.CTkLabel(add_frame, text="类型:", font=ctk.CTkFont(size=12),
                    text_color=DS["text_dim"]).grid(row=0, column=2, padx=(14, 4), pady=10)
        sched_types = list(self.get_bcast_types())
        self.sched_type_cmb = ctk.CTkComboBox(add_frame, values=sched_types, width=150,
                                             font=ctk.CTkFont(size=12), dropdown_font=ctk.CTkFont(size=12),
                                             fg_color="#2a2a2a", button_color="#3a3a3a",
                                             button_hover_color="#4a4a4a",
                                             dropdown_fg_color="#ffffff", dropdown_text_color="#000000",
                                             dropdown_hover_color="#e2e2e2")
        self.sched_type_cmb.set("检票预告")
        self.sched_type_cmb.grid(row=0, column=3, sticky="w", padx=4, pady=10)

        ctk.CTkLabel(add_frame, text="车次:", font=ctk.CTkFont(size=12),
                    text_color=DS["text_dim"]).grid(row=0, column=4, padx=(14, 4), pady=10)
        self.sched_train_cmb = ctk.CTkComboBox(add_frame, values=[], width=130,
                                              font=ctk.CTkFont(size=12), dropdown_font=ctk.CTkFont(size=12),
                                              fg_color="#2a2a2a", button_color="#3a3a3a",
                                              button_hover_color="#4a4a4a",
                                              dropdown_fg_color="#ffffff", dropdown_text_color="#000000",
                                              dropdown_hover_color="#e2e2e2")
        self.sched_train_cmb.grid(row=0, column=5, sticky="w", padx=4, pady=10)

        ctk.CTkButton(add_frame, text="＋ 添加定时", width=100, height=32,
                     fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                     font=ctk.CTkFont(size=12), command=self.add_schedule).grid(row=0, column=6, padx=(14, 14), pady=10)

        # ===== 任务列表 =====
        list_frame = ctk.CTkFrame(panel, fg_color=DS["panel2"], corner_radius=8)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(4, 10))
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        self.sched_tree = ttk.Treeview(list_frame, columns=("时间", "广播类型", "车次", "状态"),
                                       show="headings", height=10, style="Sched.Treeview")
        sst = ttk.Style()
        try:
            sst.theme_use("clam")
        except Exception:
            pass
        sst.configure("Sched.Treeview", font=(DS["font"], 11), rowheight=30,
                      background=DS["row1"], fieldbackground=DS["row1"],
                      foreground=DS["text"], borderwidth=0)
        sst.map("Sched.Treeview",
                background=[("selected", DS["row_sel"])],
                foreground=[("selected", "#ffffff")])
        for i, col in enumerate(("时间", "广播类型", "车次", "状态")):
            self.sched_tree.heading(col, text=col)
            self.sched_tree.column(col, width=[90, 170, 120, 80][i], anchor="center")
        self.sched_tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.sched_tree.bind("<Double-1>", self.toggle_schedule)

        op_frame = ctk.CTkFrame(panel, fg_color="transparent")
        op_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 14))
        ctk.CTkButton(op_frame, text="⏯ 启用/停用(双击列表也可)", width=160, height=32,
                     fg_color=DS["btn"], hover_color=DS["btn_hover"],
                     command=self.toggle_schedule).pack(side="left", padx=2)
        ctk.CTkButton(op_frame, text="- 删除选中", width=110, height=32,
                     fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                     command=self.del_schedule).pack(side="left", padx=2)
        ctk.CTkButton(op_frame, text="↺ 恢复默认(清空)", width=120, height=32,
                     fg_color=DS["btn_warn"], hover_color=DS["btn_warn_hover"],
                     command=self.clear_schedule).pack(side="right", padx=2)

        # ===== 车站显示设置（大屏欢迎语 / 停止检票提前量） =====
        sta_frame = ctk.CTkFrame(panel, fg_color=DS["panel2"], corner_radius=8)
        sta_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 14))
        sta_frame.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(sta_frame, text="车站显示设置（大屏欢迎语 / 停止检票提示）",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=DS["accent"]).grid(row=0, column=0, columnspan=6, sticky="w", padx=14, pady=(10, 4))
        ctk.CTkLabel(sta_frame, text="车站站名:", font=ctk.CTkFont(size=12),
                    text_color=DS["text_dim"]).grid(row=1, column=0, padx=(14, 4), pady=8)
        self.station_entry = ctk.CTkEntry(sta_frame, width=160, font=ctk.CTkFont(size=12))
        self.station_entry.insert(0, "丽水站")
        self.station_entry.grid(row=1, column=1, padx=4, pady=8)
        ctk.CTkLabel(sta_frame, text="停止检票提前(分钟):", font=ctk.CTkFont(size=12),
                    text_color=DS["text_dim"]).grid(row=1, column=2, padx=(14, 4), pady=8)
        self.stop_min_entry = ctk.CTkEntry(sta_frame, width=80, font=ctk.CTkFont(size=12))
        self.stop_min_entry.insert(0, "5")
        self.stop_min_entry.grid(row=1, column=3, padx=4, pady=8)
        ctk.CTkLabel(sta_frame, text="改完自动保存，大屏立即生效", font=ctk.CTkFont(size=10),
                    text_color=DS["text_dim"]).grid(row=1, column=4, sticky="w", padx=10, pady=8)

        def _save_sta(_e=None):
            try:
                self.save_bc_settings(silent=True)
            except Exception:
                pass
        self.station_entry.bind("<FocusOut>", _save_sta)
        self.station_entry.bind("<Return>", _save_sta)
        self.stop_min_entry.bind("<FocusOut>", _save_sta)
        self.stop_min_entry.bind("<Return>", _save_sta)

        # 初始化定时任务列表（从配置加载）
        self.bc_schedule = []
        self.refresh_sched_train_list()
        if hasattr(self, "load_bc_config"):
            # 配置加载后由 load_bc_config 填充；这里先建空列表
            pass
        return panel

    def create_bcast_set_panel(self):
        """广播设置面板（步骤式，每步可选音频）"""
        self.bcast_set_panel = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.bcast_set_panel.grid(row=0, column=0, sticky="nsew")
        self.bcast_set_panel.grid_remove()
        self.bcast_set_panel.grid_columnconfigure(0, weight=1)
        self.bcast_set_panel.grid_columnconfigure(1, weight=1)
        self.bcast_set_panel.grid_rowconfigure(0, weight=1)

        # ===== 左侧：字符映射表（可滚动，避免内容溢出被裁剪）=====
        map_frame = ctk.CTkScrollableFrame(self.bcast_set_panel, fg_color=DS["panel"], corner_radius=10)
        map_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 7))

        ctk.CTkLabel(map_frame, text="字符映射（字母/数字 → 音频）",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=DS["accent"]).pack(anchor="w", padx=15, pady=(15, 10))

        map_cols = ("字符", "对应音频")
        self.map_tree = ttk.Treeview(map_frame, columns=map_cols, show="headings", height=15)
        self.map_tree.heading("字符", text="车次字符")
        self.map_tree.heading("对应音频", text="音频文件名")
        self.map_tree.column("字符", width=80, anchor="center")
        self.map_tree.column("对应音频", width=150, anchor="w")
        self.map_tree.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        default_map = [
            ("G", "高"), ("D", "动"), ("K", "快"),
            ("0", "零"), ("1", "一"), ("2", "二"), ("3", "三"),
            ("4", "四"), ("5", "五"), ("6", "六"), ("7", "七"),
            ("8", "八"), ("9", "九"),
        ]
        for ch, audio in default_map:
            self.map_tree.insert("", "end", values=(ch, audio))
        zebra(self.map_tree)
        self.map_tree.bind("<Double-1>", self.edit_map_cell)

        # 映射表操作按钮
        map_btn_frame = ctk.CTkFrame(map_frame, fg_color="transparent")
        map_btn_frame.pack(fill="x", padx=15, pady=(0, 8))
        ctk.CTkButton(map_btn_frame, text="+ 添加映射", width=100, height=28,
                     fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                     command=self.add_map).pack(side="left", padx=2)
        ctk.CTkButton(map_btn_frame, text="- 删除映射", width=100, height=28,
                     fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                     command=self.del_map).pack(side="left", padx=2)
        ctk.CTkButton(map_btn_frame, text="📁 浏览设置", width=100, height=28,
                     fg_color=DS["btn"], hover_color=DS["btn_hover"],
                     command=self.browse_map_audio).pack(side="left", padx=2)
        ctk.CTkButton(map_btn_frame, text="↺ 恢复默认", width=100, height=28,
                     fg_color=DS["btn"], hover_color=DS["btn_hover"],
                     command=self.reset_map_defaults).pack(side="left", padx=2)

        # ===== 开始音 / 结束音设置 =====
        sound_frame = ctk.CTkFrame(map_frame, fg_color=DS["panel2"], corner_radius=8)
        sound_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(sound_frame, text="广播提示音设置",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=DS["accent"]).pack(anchor="w", padx=10, pady=(10, 5))

        # 开始音
        start_row = ctk.CTkFrame(sound_frame, fg_color="transparent")
        start_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(start_row, text="开始音:", width=50,
                    font=ctk.CTkFont(size=11), text_color="#aaa").pack(side="left")
        self.start_sound_btn = ctk.CTkButton(start_row, text="提示音/tsy1.mp3",
                                             height=26, fg_color=DS["btn"], hover_color=DS["btn_hover"],
                                             font=ctk.CTkFont(size=10),
                                             command=self.browse_start_sound)
        self.start_sound_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # 结束音
        end_row = ctk.CTkFrame(sound_frame, fg_color="transparent")
        end_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(end_row, text="结束音:", width=50,
                    font=ctk.CTkFont(size=11), text_color="#aaa").pack(side="left")
        self.end_sound_btn = ctk.CTkButton(end_row, text="无（点击选择）",
                                           height=26, fg_color=DS["btn"], hover_color=DS["btn_hover"],
                                           font=ctk.CTkFont(size=10),
                                           command=self.browse_end_sound)
        self.end_sound_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # 语速设置
        ctk.CTkLabel(sound_frame, text="播放参数，保存后生效",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=DS["accent"]).pack(anchor="w", padx=10, pady=(8, 2))

        speed_row = ctk.CTkFrame(sound_frame, fg_color="transparent")
        speed_row.pack(fill="x", padx=10, pady=(2, 10))
        ctk.CTkLabel(speed_row, text="整体播放速度:", width=88,
                    font=ctk.CTkFont(size=11), text_color="#aaa").pack(side="left")
        self.speed_slider = ctk.CTkSlider(speed_row, from_=0.5, to=2.0, number_of_steps=30)
        self.speed_slider.set(1.0)
        self.speed_slider.pack(side="left", fill="x", expand=True, padx=(5, 5))
        self.speed_label = ctk.CTkLabel(speed_row, text="1.00x", width=48,
                                        font=ctk.CTkFont(size=11), text_color=DS["accent"])
        self.speed_label.pack(side="left")

        # 滑条实时显示数值
        def _on_speed(v):
            """语速改动：立即更新显示 + 节流自动保存（配置立即生效）"""
            try:
                self.speed_label.configure(text=f"{float(v):.2f}x")
            except Exception:
                pass
            aid = getattr(self, "_speed_save_after", None)
            if aid:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
            def _do_save():
                try:
                    self.save_bc_settings(silent=True)
                except Exception:
                    pass
                self._speed_save_after = None
            self._speed_save_after = self.after(800, _do_save)
        self.speed_slider.configure(command=_on_speed)

        # 变量播放速度（只作用于车次/发站/到站/检票口/站台等变量音频，变速不变调）
        var_sp_row = ctk.CTkFrame(sound_frame, fg_color="transparent")
        var_sp_row.pack(fill="x", padx=10, pady=(2, 10))
        ctk.CTkLabel(var_sp_row, text="变量播放速度:", width=88,
                    font=ctk.CTkFont(size=11), text_color="#aaa").pack(side="left")
        self.var_speed_slider = ctk.CTkSlider(var_sp_row, from_=0.5, to=2.0, number_of_steps=30)
        self.var_speed_slider.set(1.0)
        self.var_speed_slider.pack(side="left", fill="x", expand=True, padx=(5, 5))
        self.var_speed_label = ctk.CTkLabel(var_sp_row, text="1.00x", width=48,
                                            font=ctk.CTkFont(size=11), text_color=DS["accent"])
        self.var_speed_label.pack(side="left")

        def _on_var_speed(v):
            """变量速度改动：立即更新显示 + 节流自动保存（配置立即生效）"""
            try:
                self.var_speed_label.configure(text=f"{float(v):.2f}x")
            except Exception:
                pass
            aid = getattr(self, "_var_sp_save_after", None)
            if aid:
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
            def _do_save():
                try:
                    self.save_bc_settings(silent=True)
                except Exception:
                    pass
                self._var_sp_save_after = None
            self._var_sp_save_after = self.after(800, _do_save)
        self.var_speed_slider.configure(command=_on_var_speed)

        # ===== 变量音频目录设置 =====
        var_frame = ctk.CTkFrame(map_frame, fg_color=DS["panel2"], corner_radius=8)
        var_frame.pack(fill="x", padx=15, pady=(0, 10))
        ctk.CTkLabel(var_frame, text="变量音频目录设置（发站/到站/车次/检票口/站台/数字/单个字从哪里取音频）",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=DS["accent"]).pack(anchor="w", padx=10, pady=(10, 5))
        ctk.CTkLabel(var_frame, text="默认=类型名（如 车站→audio/media2/车站），可填 media3/车站 等路径；映射的音频也支持填路径",
                    font=ctk.CTkFont(size=10), text_color=DS["text_dim"]).pack(anchor="w", padx=10, pady=(0, 6))

        self.var_dir_entries = {}
        var_rows = [("车站", "发站/到站目录:"), ("检票口", "检票口目录:"),
                    ("站台", "站台目录:"), ("数字", "数字目录:"),
                    ("单个字", "单个字目录:")]
        for key, label in var_rows:
            row = ctk.CTkFrame(var_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(row, text=label, width=115,
                        font=ctk.CTkFont(size=11), text_color="#aaa").pack(side="left")
            entry = ctk.CTkEntry(row, font=ctk.CTkFont(size=10), height=28)
            entry.insert(0, key)
            entry.pack(side="left", fill="x", expand=True, padx=(4, 4))
            entry.bind("<FocusOut>", lambda e, k=key: self.save_dir_map_silent())
            entry.bind("<Return>", lambda e, k=key: self.save_dir_map_silent())
            ctk.CTkButton(row, text="浏览", width=52, height=26, fg_color=DS["btn"], hover_color=DS["btn_hover"],
                         font=ctk.CTkFont(size=10),
                         command=lambda k=key, e=entry: self.browse_var_dir(k, e)).pack(side="left", padx=(0, 2))
            self.var_dir_entries[key] = entry

        ctk.CTkButton(var_frame, text="恢复默认目录", height=28, fg_color=DS["btn_warn"], hover_color=DS["btn_warn_hover"],
                     font=ctk.CTkFont(size=11), command=self.reset_var_dirs).pack(anchor="w", padx=10, pady=(6, 10))
        self.dir_map = {"车站": "车站", "检票口": "检票口", "站台": "站台", "数字": "数字", "单个字": "单个字"}

        # ===== 通用音频配置（启动音频 / 主界面播放音频）=====
        gen_frame = ctk.CTkFrame(map_frame, fg_color=DS["panel2"], corner_radius=8)
        gen_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(gen_frame, text="通用音频配置，保存后生效",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=DS["accent"]).pack(anchor="w", padx=10, pady=(10, 5))

        # --- 启动音频 ---
        su_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        su_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(su_row, text="启动音频:", width=90,
                    font=ctk.CTkFont(size=11), text_color="#aaa").pack(side="left")
        self.startup_audio_entry = ctk.CTkEntry(su_row, placeholder_text="tsy/tsy2.mp3",
                                                font=ctk.CTkFont(size=10), height=28)
        self.startup_audio_entry.insert(0, "tsy/tsy2.mp3")
        self.startup_audio_entry.pack(side="left", fill="x", expand=True, padx=(4, 4))
        self.startup_audio_entry.bind("<FocusOut>", lambda e: self.save_bc_settings(silent=True))
        self.startup_audio_entry.bind("<Return>", lambda e: self.save_bc_settings(silent=True))
        ctk.CTkButton(su_row, text="浏览", width=52, height=26, fg_color=DS["btn"], hover_color=DS["btn_hover"],
                     font=ctk.CTkFont(size=10), command=self.browse_startup_audio).pack(side="left", padx=(0, 2))
        ctk.CTkButton(su_row, text="试听", width=52, height=26, fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                     font=ctk.CTkFont(size=10), command=lambda: self.preview_cfg_audio(self.startup_audio_entry)).pack(side="left", padx=(0, 2))
        ctk.CTkButton(su_row, text="停止", width=52, height=26, fg_color="#555", hover_color="#777",
                     font=ctk.CTkFont(size=10), command=self.stop_preview_audio).pack(side="left", padx=(0, 2))

        # --- 主界面播放音频 ---
        ma_row = ctk.CTkFrame(gen_frame, fg_color="transparent")
        ma_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(ma_row, text="主界面播放音频:", width=90,
                    font=ctk.CTkFont(size=11), text_color="#aaa").pack(side="left")
        self.main_audio_entry = ctk.CTkEntry(ma_row, placeholder_text="留空=用步骤开始音",
                                             font=ctk.CTkFont(size=10), height=28)
        self.main_audio_entry.pack(side="left", fill="x", expand=True, padx=(4, 4))
        self.main_audio_entry.bind("<FocusOut>", lambda e: self.save_bc_settings(silent=True))
        self.main_audio_entry.bind("<Return>", lambda e: self.save_bc_settings(silent=True))
        ctk.CTkButton(ma_row, text="浏览", width=52, height=26, fg_color=DS["btn"], hover_color=DS["btn_hover"],
                     font=ctk.CTkFont(size=10), command=self.browse_main_audio).pack(side="left", padx=(0, 2))
        ctk.CTkButton(ma_row, text="试听", width=52, height=26, fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                     font=ctk.CTkFont(size=10), command=lambda: self.preview_cfg_audio(self.main_audio_entry)).pack(side="left", padx=(0, 2))
        ctk.CTkButton(ma_row, text="停止", width=52, height=26, fg_color="#555", hover_color="#777",
                     font=ctk.CTkFont(size=10), command=self.stop_preview_audio).pack(side="left", padx=(0, 2))

        # 恢复默认
        ctk.CTkButton(gen_frame, text="恢复默认音频", height=28,
                     fg_color=DS["btn_warn"], hover_color=DS["btn_warn_hover"],
                     font=ctk.CTkFont(size=11),
                     command=self.reset_default_audio).pack(fill="x", padx=10, pady=(6, 10))

        # ===== 广播类型管理（自定义排序 + 添加类型）=====
        type_frame = ctk.CTkFrame(map_frame, fg_color=DS["panel2"], corner_radius=8)
        type_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(type_frame, text="广播类型管理（自定义排序、添加类型，如 紧急-自然灾害/停运/检修 等）",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=DS["accent"]).pack(anchor="w", padx=10, pady=(10, 5))

        self.type_tree = ttk.Treeview(type_frame, columns=("类型",), show="headings", height=6)
        self.type_tree.heading("类型", text="广播类型（紧急广播弹窗也按此列表显示）")
        self.type_tree.column("类型", width=220, anchor="w")
        self.type_tree.pack(fill="x", padx=10, pady=(0, 5))
        for _typ in self.get_bcast_types():
            self.type_tree.insert("", "end", values=(_typ,))
        zebra(self.type_tree)

        type_row = ctk.CTkFrame(type_frame, fg_color="transparent")
        type_row.pack(fill="x", padx=10, pady=(0, 5))
        self.new_type_entry = ctk.CTkEntry(type_row, placeholder_text="新类型名，如 紧急-自然灾害",
                                           font=ctk.CTkFont(size=11), height=28)
        self.new_type_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.new_type_entry.bind("<Return>", lambda e: self.add_bcast_type())
        ctk.CTkButton(type_row, text="添加", width=56, height=28,
                      fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                      font=ctk.CTkFont(size=11), command=self.add_bcast_type).pack(side="left")

        type_btn = ctk.CTkFrame(type_frame, fg_color="transparent")
        type_btn.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkButton(type_btn, text="↑ 上移", width=64, height=26, fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      font=ctk.CTkFont(size=11),
                      command=lambda: self.move_bcast_type(-1)).pack(side="left", padx=2)
        ctk.CTkButton(type_btn, text="↓ 下移", width=64, height=26, fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      font=ctk.CTkFont(size=11),
                      command=lambda: self.move_bcast_type(1)).pack(side="left", padx=2)
        ctk.CTkButton(type_btn, text="删除", width=64, height=26, fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                      font=ctk.CTkFont(size=11), command=self.del_bcast_type).pack(side="left", padx=2)

        # ===== 手动播放（排序模式）：自定义顺序播放 =====
        manual_frame = ctk.CTkFrame(map_frame, fg_color=DS["panel2"], corner_radius=8)
        manual_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(manual_frame, text="手动播放（排序模式）",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=DS["accent"]).pack(anchor="w", padx=10, pady=(10, 5))
        ctk.CTkLabel(manual_frame, text="自定义播放顺序：每一步可指定音频文件/语速，排完按顺序播放",
                     font=ctk.CTkFont(size=10), text_color=DS["text_dim"]).pack(anchor="w", padx=10, pady=(0, 6))
        ctk.CTkButton(manual_frame, text="🔄 打开手动播放排序窗口", height=32,
                     fg_color="#555", hover_color="#777",
                     font=ctk.CTkFont(size=12),
                     command=self.open_manual_play_dialog).pack(fill="x", padx=10, pady=(0, 10))

        # ===== 右侧：检票预告步骤 =====
        tpl_frame = ctk.CTkFrame(self.bcast_set_panel, fg_color=DS["panel"], corner_radius=10)
        tpl_frame.grid(row=0, column=1, sticky="nsew")

        # 选择要设置的按钮
        ctk.CTkLabel(tpl_frame, text="选择要设置的按钮:",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#ccc").pack(anchor="w", padx=15, pady=(15, 3))

        self.bc_type_cmb = ctk.CTkComboBox(tpl_frame,
                                           values=self.get_bcast_types(),
                                           command=self.on_bc_type_change,
                                           fg_color="#ffffff", text_color="#000000",
                                           button_color="#d5d5d5", button_hover_color="#b5b5b5",
                                           dropdown_fg_color="#ffffff", dropdown_text_color="#000000",
                                           dropdown_hover_color="#e2e2e2")
        self.bc_type_cmb.set("检票预告")
        self.bc_type_cmb.pack(fill="x", padx=15, pady=(0, 10))
        # 显式初始化步骤内存字典（保证切换/保存都可用）
        if not hasattr(self, "bc_steps"):
            self.bc_steps = {}
        self._cur_bc_type = "检票预告"
        if "检票预告" not in self.bc_steps:
            self.bc_steps["检票预告"] = [list(s) for s in self.get_default_steps("检票预告")]

        ctk.CTkLabel(tpl_frame, text="广播步骤（按顺序播放）",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=DS["accent"]).pack(anchor="w", padx=15, pady=(0, 10))

        ctk.CTkLabel(tpl_frame, text="每行一步，{发站}{到站}{车次}{检票口}{站台}{停靠站台} 是变量；双击可改内容与本步语速",
                    font=ctk.CTkFont(size=11), text_color=DS["text_dim"]).pack(anchor="w", padx=15, pady=(0, 10))

        # 步骤列表（第 3 列 = 本步语速，1.00x=跟随整体语速）
        step_cols = ("顺序", "音频文件", "语速")
        self.step_tree = ttk.Treeview(tpl_frame, columns=step_cols, show="headings", height=10)
        self.step_tree.heading("顺序", text="顺序")
        self.step_tree.heading("音频文件", text="音频文件路径")
        self.step_tree.heading("语速", text="语速")
        self.step_tree.column("顺序", width=48, anchor="center")
        self.step_tree.column("音频文件", width=200, anchor="w")
        self.step_tree.column("语速", width=52, anchor="center")
        self.step_tree.pack(fill="x", padx=15, pady=(0, 5))
        self.step_tree.bind("<Double-1>", self.edit_step_cell)

        # 默认步骤
        default_steps = [
            ("1", "其他/各位旅客请注意"),
            ("2", "单个字/由"),
            ("3", "{发站}"),
            ("4", "单个字/开往"),
            ("5", "{到站}"),
            ("6", "单个字/的"),
            ("7", "{车次}"),
            ("8", "单个字/次列车"),
            ("9", "其他/即将开始检票，请您整理好您的随"),
            ("10", "{检票口}"),
            ("11", "其他/号检票口检票进站。"),
        ]
        for num, content in default_steps:
            self.step_tree.insert("", "end", values=(num, content, "1.00x"))
        zebra(self.step_tree)

        # 绑定拖拽排序
        self.bind_step_drag()

        # 选择文件按钮 + 插入变量按钮
        file_row = ctk.CTkFrame(tpl_frame, fg_color="transparent")
        file_row.pack(fill="x", padx=15, pady=(0, 5))
        ctk.CTkButton(file_row, text="浏览选择音频文件...", height=32,
                     fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                     command=self.browse_audio_file).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ctk.CTkButton(file_row, text="＋ 变量", width=90, height=32,
                     fg_color="#7a5a1e", hover_color="#9a7a2a",
                     command=self.insert_var_step).pack(side="left", padx=(3, 0))

        # 操作按钮
        btn_frame = ctk.CTkFrame(tpl_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkButton(btn_frame, text="↑ 上移", width=60, height=30,
                     fg_color=DS["btn"], hover_color=DS["btn_hover"],
                     command=self.move_step_up).pack(side="left", padx=2)

        ctk.CTkButton(btn_frame, text="↓ 下移", width=60, height=30,
                     fg_color=DS["btn"], hover_color=DS["btn_hover"],
                     command=self.move_step_down).pack(side="left", padx=2)

        ctk.CTkButton(btn_frame, text="+ 添加", width=60, height=30,
                     fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                     command=self.add_step).pack(side="left", padx=2)

        ctk.CTkButton(btn_frame, text="- 删除", width=60, height=30,
                     fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                     command=self.del_step).pack(side="left", padx=2)

        btn_frame2 = ctk.CTkFrame(tpl_frame, fg_color="transparent")
        btn_frame2.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(btn_frame2, text="测试播放", width=100, height=32,
                     fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                     command=self.test_play_steps).pack(side="left", padx=2)

        ctk.CTkButton(btn_frame2, text="取消修改", width=90, height=32,
                     fg_color="#555", hover_color="#777",
                     command=self.cancel_bc_changes).pack(side="left", padx=2)

        ctk.CTkButton(btn_frame2, text="恢复默认", width=90, height=32,
                     fg_color=DS["btn_warn"], hover_color=DS["btn_warn_hover"],
                     command=self.reset_default_steps).pack(side="left", padx=2)

        ctk.CTkButton(btn_frame2, text="保存设置", width=100, height=32,
                     fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                     command=self.save_bc_settings).pack(side="right", padx=2)

    def add_step(self):
        """添加步骤（空内容，选中后用浏览按钮选择音频）"""
        self.step_tree.insert("", "end", values=("新", "", "1.00x"))
        self.renumber_steps()
        self.sync_steps_to_memory()
        self.save_bc_settings(silent=True)
        self.set_status("已添加步骤（已自动保存），选中后点浏览选择音频，或直接输入")

    def insert_var_step(self):
        """插入变量步骤（{发站}{到站}{车次}{检票口}）"""
        from tkinter import simpledialog
        var = simpledialog.askstring("插入变量",
                                     "输入变量名：发站 / 到站 / 车次 / 检票口 / 站台 / 停靠站台", parent=self)
        if not var or not var.strip():
            return
        var = var.strip().strip("{}").strip()
        sel = self.step_tree.selection()
        text = "{" + var + "}"
        if sel:
            idx = self.step_tree.index(sel[0])
            self.step_tree.insert("", idx + 1, values=("新", text, "1.00x"))
        else:
            self.step_tree.insert("", "end", values=("新", text, "1.00x"))
        self.renumber_steps()
        self.sync_steps_to_memory()
        self.save_bc_settings(silent=True)
        self.set_status(f"已插入变量步骤：{text}（已自动保存）")

    def edit_step_cell(self, event):
        """双击编辑步骤内容（支持 {变量}、音频路径；改完自动保存）"""
        sel = self.step_tree.selection()
        if not sel:
            return
        from tkinter import simpledialog
        vals = self.step_tree.item(sel[0])["values"]
        old_speed = str(vals[2]) if len(vals) > 2 else "1.00x"
        new = simpledialog.askstring("编辑步骤",
                                     f"步骤内容（{vals[0]}）：\n{{发站}}{{到站}}{{车次}}{{检票口}}{{站台}}{{停靠站台}} 是变量，也可填音频路径",
                                     initialvalue=str(vals[1]), parent=self)
        if new is not None:
            spd = simpledialog.askstring("编辑语速",
                                         "本步语速（如 1.0 / 1.2 / 0.8，留空 = 跟随整体语速）",
                                         initialvalue=old_speed.replace("x", ""), parent=self)
            if spd is None:
                spd = old_speed.replace("x", "")
            spd = str(spd).strip() or "1.0"
            try:
                spd = f"{float(spd):.2f}x"
            except Exception:
                spd = "1.00x"
            self.step_tree.item(sel[0], values=(vals[0], new.strip(), spd))
            self.renumber_steps()
            self.sync_steps_to_memory()
            self.save_bc_settings(silent=True)
            self.set_status(f"步骤已更新（已自动保存）：{new.strip()} 语速 {spd}")

    def sync_steps_to_memory(self):
        """把面板当前步骤同步到内存配置（保证主界面播放用最新配置）"""
        if not hasattr(self, "step_tree"):
            return
        if not hasattr(self, "bc_steps"):
            self.bc_steps = {}
        steps = []
        for child in self.step_tree.get_children():
            vals = self.step_tree.item(child)["values"]
            spd = vals[2] if len(vals) > 2 else "1.00x"
            steps.append([str(vals[0]), str(vals[1]), str(spd)])
        cur = getattr(self, "_cur_bc_type", "检票预告")
        self.bc_steps[cur] = steps

    def del_step(self):
        """删除选中步骤（二次确认）"""
        sel = self.step_tree.selection()
        if sel:
            if not messagebox.askyesno("删除步骤", "确定删除选中的步骤吗？"):
                return
            self.step_tree.delete(sel)
            self.renumber_steps()
            self.sync_steps_to_memory()
            self.save_bc_settings(silent=True)

    def renumber_steps(self):
        """重新给所有步骤编号（并刷新斑马纹，保留语速列）"""
        children = self.step_tree.get_children()
        for i, child in enumerate(children):
            item = self.step_tree.item(child)
            vals = item["values"]
            spd = vals[2] if len(vals) > 2 else "1.00x"
            self.step_tree.item(child, values=(str(i+1), vals[1], spd))
        zebra(self.step_tree)

    def move_step_up(self):
        """上移选中步骤（移动整行 iid，序号自动重排）"""
        sel = self.step_tree.selection()
        if not sel:
            return
        target = sel[0]
        children = self.step_tree.get_children()
        idx = children.index(target)
        if idx > 0:
            # 记录数据，删除，插到上一行位置
            item = self.step_tree.item(target)
            self.step_tree.delete(target)
            self.step_tree.insert("", idx - 1, iid=target, values=item["values"])
            self.renumber_steps()
            self.step_tree.selection_set(target)
            self.sync_steps_to_memory()
            self.save_bc_settings(silent=True)

    def move_step_down(self):
        """下移选中步骤（移动整行 iid，序号自动重排）"""
        sel = self.step_tree.selection()
        if not sel:
            return
        target = sel[0]
        children = self.step_tree.get_children()
        idx = children.index(target)
        if idx < len(children) - 1:
            item = self.step_tree.item(target)
            self.step_tree.delete(target)
            self.step_tree.insert("", idx + 1, iid=target, values=item["values"])
            self.renumber_steps()
            self.step_tree.selection_set(target)
            self.sync_steps_to_memory()
            self.save_bc_settings(silent=True)

    def add_bcast_type(self):
        """添加广播类型（立即保存，紧急广播弹窗/定时广播同步生效）"""
        name = self.new_type_entry.get().strip()
        if not name:
            self.set_status("请输入类型名")
            return
        if name in self.get_bcast_types():
            self.set_status(f"类型 {name} 已存在")
            return
        types = self.get_bcast_types()
        types.append(name)
        self._bcast_types = types
        if not hasattr(self, "bc_steps"):
            self.bc_steps = {}
        self.bc_steps[name] = []
        self.refresh_type_combos()
        self.new_type_entry.delete(0, "end")
        self.save_bc_settings(silent=True)
        self.set_status(f"已添加广播类型：{name}")

    def move_bcast_type(self, delta):
        """上移/下移广播类型（自定义排序，立即保存）"""
        sel = self.type_tree.selection()
        if not sel:
            self.set_status("请先在类型列表中选择要移动的类型")
            return
        types = self.get_bcast_types()
        cur = self.type_tree.item(sel[0])["values"][0]
        idx = types.index(cur)
        nidx = idx + delta
        if nidx < 0 or nidx >= len(types):
            return
        types[idx], types[nidx] = types[nidx], types[idx]
        self._bcast_types = types
        self.refresh_type_combos()
        self.save_bc_settings(silent=True)
        self.set_status(f"类型顺序已更新：{cur}")

    def del_bcast_type(self):
        """删除广播类型（同步清理步骤配置）"""
        sel = self.type_tree.selection()
        if not sel:
            self.set_status("请先在类型列表中选择要删除的类型")
            return
        cur = self.type_tree.item(sel[0])["values"][0]
        if cur in CHECKIN_TYPES:
            self.set_status("检票预告/开始检票/停止检票 为内置类型，不可删除")
            return
        if not messagebox.askyesno("删除广播类型", f"确定删除广播类型「{cur}」吗？"):
            return
        types = self.get_bcast_types()
        if cur in types:
            types.remove(cur)
        self._bcast_types = types
        if hasattr(self, "bc_steps") and cur in self.bc_steps:
            del self.bc_steps[cur]
        self.refresh_type_combos()
        self.save_bc_settings(silent=True)
        self.set_status(f"已删除广播类型：{cur}")

    def get_default_steps(self, choice):
        """每种广播类型的默认步骤"""
        defaults = {
            "检票预告": [
                ("1", "其他/各位旅客请注意"),
                ("2", "单个字/由"),
                ("3", "{发站}"),
                ("4", "单个字/开往"),
                ("5", "{到站}"),
                ("6", "单个字/的"),
                ("7", "{车次}"),
                ("8", "单个字/次列车"),
                ("9", "其他/即将开始检票，请您整理好您的随"),
                ("10", "{检票口}"),
                ("11", "其他/号检票口检票进站。"),
            ],
            "开始检票": [
                ("1", "其他/现在开始检票，请持有该车车票的"),
                ("2", "{检票口}"),
                ("3", "其他/号检票口检票进站。"),
            ],
            "停止检票": [
                ("1", "紧急广播/停止检票"),
            ],
            "紧急-列车晚点（通用）": [
                ("1", "晚点/1各位旅客请注意"), ("2", "晚点/2由"), ("3", "{发站}"),
                ("4", "晚点/3开往"), ("5", "{到站}"), ("6", "晚点/4的"),
                ("7", "{车次}"), ("8", "晚点/5次列车"),
            ],
            "紧急-列车晚点·天气原因": [
                ("1", "晚点/1各位旅客请注意"), ("2", "晚点/2由"), ("3", "{发站}"),
                ("4", "晚点/3开往"), ("5", "{到站}"), ("6", "晚点/4的"),
                ("7", "{车次}"), ("8", "晚点/5次列车"), ("9", "晚点/6因天气原因晚点到"),
            ],
            "紧急-列车晚点·设备故障": [
                ("1", "晚点/1各位旅客请注意"), ("2", "晚点/2由"), ("3", "{发站}"),
                ("4", "晚点/3开往"), ("5", "{到站}"), ("6", "晚点/4的"),
                ("7", "{车次}"), ("8", "晚点/5次列车"), ("9", "晚点/6因设备故障晚点到"),
            ],
            "紧急-列车晚点·线路施工": [
                ("1", "晚点/1各位旅客请注意"), ("2", "晚点/2由"), ("3", "{发站}"),
                ("4", "晚点/3开往"), ("5", "{到站}"), ("6", "晚点/4的"),
                ("7", "{车次}"), ("8", "晚点/5次列车"), ("9", "晚点/6因线路施工晚点到"),
            ],
            "紧急-列车晚点·自然灾害": [
                ("1", "晚点/1各位旅客请注意"), ("2", "晚点/2由"), ("3", "{发站}"),
                ("4", "晚点/3开往"), ("5", "{到站}"), ("6", "晚点/4的"),
                ("7", "{车次}"), ("8", "晚点/5次列车"), ("9", "晚点/6因自然灾害晚点到"),
            ],
            "紧急-列车晚点·行车事故": [
                ("1", "晚点/1各位旅客请注意"), ("2", "晚点/2由"), ("3", "{发站}"),
                ("4", "晚点/3开往"), ("5", "{到站}"), ("6", "晚点/4的"),
                ("7", "{车次}"), ("8", "晚点/5次列车"), ("9", "晚点/6因行车事故晚点到"),
            ],
            "紧急-列车晚点·列车超员": [
                ("1", "晚点/1各位旅客请注意"), ("2", "晚点/2由"), ("3", "{发站}"),
                ("4", "晚点/3开往"), ("5", "{到站}"), ("6", "晚点/4的"),
                ("7", "{车次}"), ("8", "晚点/5次列车"), ("9", "晚点/6因列车超员晚点到"),
            ],
            "紧急-列车停运（通用）": [
                ("1", "停运/1旅客们，我们非常"), ("2", "停运/2由"), ("3", "{发站}"),
                ("4", "停运/3开往"), ("5", "{到站}"), ("6", "停运/4的"),
                ("7", "{车次}"), ("8", "停运/5次列车"),
                ("9", "停运/6今日停运"), ("10", "停运/6请持有"), ("11", "{车次}"),
                ("12", "停运/7次列车车票的旅客"),
            ],
            "紧急-列车停运·天气原因": [
                ("1", "停运/1旅客们，我们非常"), ("2", "停运/2由"), ("3", "{发站}"),
                ("4", "停运/3开往"), ("5", "{到站}"), ("6", "停运/4的"),
                ("7", "{车次}"), ("8", "停运/5次列车"), ("9", "停运/5因天气原因"),
                ("10", "停运/6今日停运"), ("11", "停运/6请持有"), ("12", "{车次}"),
                ("13", "停运/7次列车车票的旅客"),
            ],
            "紧急-列车停运·设备故障": [
                ("1", "停运/1旅客们，我们非常"), ("2", "停运/2由"), ("3", "{发站}"),
                ("4", "停运/3开往"), ("5", "{到站}"), ("6", "停运/4的"),
                ("7", "{车次}"), ("8", "停运/5次列车"), ("9", "停运/5因设备故障"),
                ("10", "停运/6今日停运"), ("11", "停运/6请持有"), ("12", "{车次}"),
                ("13", "停运/7次列车车票的旅客"),
            ],
            "紧急-列车停运·线路施工": [
                ("1", "停运/1旅客们，我们非常"), ("2", "停运/2由"), ("3", "{发站}"),
                ("4", "停运/3开往"), ("5", "{到站}"), ("6", "停运/4的"),
                ("7", "{车次}"), ("8", "停运/5次列车"), ("9", "停运/5因线路施工"),
                ("10", "停运/6今日停运"), ("11", "停运/6请持有"), ("12", "{车次}"),
                ("13", "停运/7次列车车票的旅客"),
            ],
            "紧急-列车停运·自然灾害": [
                ("1", "停运/1旅客们，我们非常"), ("2", "停运/2由"), ("3", "{发站}"),
                ("4", "停运/3开往"), ("5", "{到站}"), ("6", "停运/4的"),
                ("7", "{车次}"), ("8", "停运/5次列车"), ("9", "停运/5因自然灾害"),
                ("10", "停运/6今日停运"), ("11", "停运/6请持有"), ("12", "{车次}"),
                ("13", "停运/7次列车车票的旅客"),
            ],
            "紧急-列车停运·行车事故": [
                ("1", "停运/1旅客们，我们非常"), ("2", "停运/2由"), ("3", "{发站}"),
                ("4", "停运/3开往"), ("5", "{到站}"), ("6", "停运/4的"),
                ("7", "{车次}"), ("8", "停运/5次列车"), ("9", "停运/5因行车事故"),
                ("10", "停运/6今日停运"), ("11", "停运/6请持有"), ("12", "{车次}"),
                ("13", "停运/7次列车车票的旅客"),
            ],
            "紧急-列车停运·列车超员": [
                ("1", "停运/1旅客们，我们非常"), ("2", "停运/2由"), ("3", "{发站}"),
                ("4", "停运/3开往"), ("5", "{到站}"), ("6", "停运/4的"),
                ("7", "{车次}"), ("8", "停运/5次列车"), ("9", "停运/5因列车超员"),
                ("10", "停运/6今日停运"), ("11", "停运/6请持有"), ("12", "{车次}"),
                ("13", "停运/7次列车车票的旅客"),
            ],
            "紧急-变更站台": [("1", "紧急广播/列车变更站台")],
            "紧急-即将进站": [("1", "紧急广播/列车即将进站")],
            "紧急-旅客突发": [("1", "紧急广播/候车区有旅客突发情况")],
            "紧急-工作人员注意": [("1", "紧急广播/工作人员请注意")],
            "紧急-致歉": [("1", "紧急广播/致歉")],
        }
        return defaults.get(choice, [])

    def on_bc_type_change(self, choice):
        """切换广播类型：先把当前步骤存进内存字典，再加载目标类型步骤"""
        # 初始化内存字典
        if not hasattr(self, "bc_steps"):
            self.bc_steps = {}

        # 保存当前显示的步骤（如果步骤树存在且有当前类型）
        if hasattr(self, "step_tree") and hasattr(self, "_cur_bc_type"):
            cur_steps = []
            for child in self.step_tree.get_children():
                vals = self.step_tree.item(child)["values"]
                spd = vals[2] if len(vals) > 2 else "1.00x"
                cur_steps.append([str(vals[0]), str(vals[1]), str(spd)])
            self.bc_steps[self._cur_bc_type] = cur_steps

        # 记录当前类型
        self._cur_bc_type = choice

        # 加载目标类型步骤：优先内存，其次默认
        if choice in self.bc_steps:
            steps = self.bc_steps[choice]
        else:
            steps = self.get_default_steps(choice)
            self.bc_steps[choice] = [list(s) for s in steps]

        # 刷新步骤树（兼容 2/3 元组步骤：语速列）
        for child in self.step_tree.get_children():
            self.step_tree.delete(child)
        for s in steps:
            if isinstance(s, (list, tuple)) and len(s) >= 3:
                self.step_tree.insert("", "end", values=(s[0], s[1], s[2]))
            else:
                num, content = s[0], s[1]
                self.step_tree.insert("", "end", values=(num, content, "1.00x"))
        zebra(self.step_tree)

    def browse_audio_file(self):
        """浏览选择音频文件"""
        from tkinter import filedialog
        import os

        start_dir = AUDIO_DIR

        filename = filedialog.askopenfilename(
            title="选择音频文件",
            initialdir=start_dir,
            filetypes=[("音频文件", "*.mp3;*.wav"), ("所有文件", "*.*")]
        )

        if filename:
            # 转成相对 AUDIO_DIR 的路径（media3/其他/xxx.mp3 或 media2/车站/xxx.mp3）
            try:
                rel = os.path.relpath(filename, AUDIO_DIR)
            except Exception:
                rel = filename
            # 音频在 audio 目录之外（如桌面自定义音频）→ 直接存完整路径
            if rel.startswith("..") or (len(rel) > 2 and rel[1] == ":"):
                rel = filename
            # 选中的行更新
            sel = self.step_tree.selection()
            if sel:
                cur_vals = self.step_tree.item(sel[0])["values"]
                spd = cur_vals[2] if len(cur_vals) > 2 else "1.00x"
                self.step_tree.item(sel[0], values=(cur_vals[0], rel, spd))
                self.renumber_steps()
                self.sync_steps_to_memory()
                self.save_bc_settings(silent=True)
                self.set_status(f"已选择：{rel}（已自动保存）")
            else:
                self.set_status(f"已选择：{rel}（未选中步骤行）")

    def browse_start_sound(self):
        """选择开始音（改完自动静默写入配置，不弹保存窗口）"""
        import tkinter.filedialog as fd
        start_dir = os.path.join(AUDIO_DIR, "media2", "提示音")
        filename = fd.askopenfilename(
            title="选择开始音",
            initialdir=start_dir if os.path.isdir(start_dir) else AUDIO_DIR,
            filetypes=[("音频文件", "*.mp3;*.wav"), ("所有文件", "*.*")]
        )
        if filename:
            try:
                rel = os.path.relpath(filename, AUDIO_DIR)
            except Exception:
                rel = filename
            self.start_sound_btn.configure(text=rel)
            ok = self.save_sound_settings_silent()
            self.set_status(f"开始音：{rel}（已自动保存）" if ok else f"开始音：{rel}（保存失败）")

    def browse_end_sound(self):
        """选择结束音（改完自动静默写入配置，不弹保存窗口）"""
        import tkinter.filedialog as fd
        filename = fd.askopenfilename(
            title="选择结束音",
            initialdir=os.path.join(AUDIO_DIR, "media2", "提示音") if os.path.isdir(os.path.join(AUDIO_DIR, "media2", "提示音")) else AUDIO_DIR,
            filetypes=[("音频文件", "*.mp3;*.wav"), ("所有文件", "*.*")]
        )
        if filename:
            try:
                rel = os.path.relpath(filename, AUDIO_DIR)
            except Exception:
                rel = filename
            self.end_sound_btn.configure(text=rel)
            ok = self.save_sound_settings_silent()
            self.set_status(f"结束音：{rel}（已自动保存）" if ok else f"结束音：{rel}（保存失败）")

    def save_sound_settings_silent(self):
        """仅把开始音/结束音写入配置文件（静默，不弹窗、不覆盖其他配置）"""
        try:
            cfg_path = self.get_config_path()
            cfg = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["start_sound"] = self.start_sound_btn.cget("text")
            cfg["end_sound"] = self.end_sound_btn.cget("text")
            if cfg["end_sound"] == "无（点击选择）":
                cfg["end_sound"] = ""
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    # ===== 变量音频目录 + 映射路径支持 =====
    def get_var_dir(self, key):
        """取变量类型对应的音频目录（用户可配置，默认 = 类型名）"""
        dm = getattr(self, "dir_map", None) or {}
        return dm.get(key) or key

    def resolve_map_audio(self, val):
        """映射值解析：绝对路径→直接播放；'单个字/高'或'media3/单个字/高.mp3'→按路径找；纯名'高'→单个字目录"""
        val = str(val).strip()
        if not val:
            return None
        # 绝对路径（D:/xxx/高.mp3、\\\\server\\... 等）→ 直接使用
        if os.path.isabs(val) or (len(val) > 2 and val[1] == ":" and val[0].isalpha()):
            return ("__abs__", val)
        if "/" in val or "\\" in val:
            v = val.replace("\\", "/")
            parts = [x for x in v.split("/") if x]
            if not parts:
                return None
            fn = parts[-1]
            if fn.lower().endswith(".mp3"):
                fn = fn[:-4]
            d = "/".join(parts[:-1]).strip()
            if d:
                return (d, fn)
            return (self.get_var_dir("单个字"), fn)
        return (self.get_var_dir("单个字"), val.replace(".mp3", ""))

    def save_dir_map_silent(self):
        """仅保存变量音频目录到配置（静默，不弹窗、不覆盖其他配置）"""
        try:
            cfg_path = self.get_config_path()
            cfg = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["dir_map"] = {}
            for k, entry in getattr(self, "var_dir_entries", {}).items():
                v = entry.get().strip()
                cfg["dir_map"][k] = v if v else k
            self.dir_map = dict(cfg["dir_map"])
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def reset_var_dirs(self):
        """恢复变量音频目录为默认"""
        for k, entry in getattr(self, "var_dir_entries", {}).items():
            entry.delete(0, "end")
            entry.insert(0, k)
        ok = self.save_dir_map_silent()
        self.set_status("变量音频目录已恢复默认（已自动保存）" if ok else "恢复失败")

    def browse_var_dir(self, key, entry):
        """浏览选择变量音频目录"""
        import tkinter.filedialog as fd
        d = fd.askdirectory(title=f"选择{key}音频目录", initialdir=AUDIO_DIR)
        if not d:
            return
        try:
            rel = os.path.relpath(d, AUDIO_DIR).replace("\\", "/")
        except Exception:
            rel = d
        if rel.startswith(".."):
            rel = d
        entry.delete(0, "end")
        entry.insert(0, rel)
        ok = self.save_dir_map_silent()
        self.set_status(f"{key}目录：{rel}（已自动保存）" if ok else f"{key}目录保存失败")

    def edit_map_cell(self, event):
        """双击编辑映射的音频（支持路径）"""
        sel = self.map_tree.selection()
        if not sel:
            return
        from tkinter import simpledialog
        vals = self.map_tree.item(sel[0])["values"]
        new = simpledialog.askstring("编辑映射",
                                     f"字符 {vals[0]} 的音频（支持路径，如 media3/单个字/高）:",
                                     initialvalue=str(vals[1]), parent=self)
        if new is not None and new.strip():
            self.map_tree.item(sel[0], values=(vals[0], new.strip()))
            zebra(self.map_tree)
            ok = self.save_map_silent()
            self.set_status(f"已更新映射：{vals[0]} → {new.strip()}（已自动保存）" if ok else f"更新失败：{vals[0]}")

    def save_map_silent(self):
        """静默保存字符映射表（含自定义路径），不覆盖其他配置、不弹窗"""
        try:
            cfg_path = self.get_config_path()
            cfg = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["char_map"] = {}
            for child in self.map_tree.get_children():
                vals = self.map_tree.item(child)["values"]
                cfg["char_map"][str(vals[0])] = str(vals[1])
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def browse_map_audio(self):
        """浏览设置选中映射的音频（库内存相对路径，库外存绝对路径）"""
        sel = self.map_tree.selection()
        if not sel:
            self.set_status("请先选中要设置音频的映射行")
            return
        import tkinter.filedialog as fd
        filename = fd.askopenfilename(
            title="选择映射音频",
            initialdir=AUDIO_DIR,
            filetypes=[("音频文件", "*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg"), ("所有文件", "*.*")]
        )
        if not filename:
            return
        try:
            rel = os.path.relpath(filename, AUDIO_DIR).replace("\\", "/")
        except Exception:
            rel = filename
        if rel.startswith(".."):
            rel = filename  # 库外：用绝对路径
        vals = self.map_tree.item(sel[0])["values"]
        self.map_tree.item(sel[0], values=(vals[0], rel))
        zebra(self.map_tree)
        ok = self.save_map_silent()
        self.set_status(f"{vals[0]} → {rel}（已自动保存）" if ok else f"{vals[0]} 保存失败")

    def reset_map_defaults(self):
        """恢复默认字符映射（G→高/D→动/K→快/数字汉字）"""
        default_map = [
            ("G", "高"), ("D", "动"), ("K", "快"),
            ("0", "零"), ("1", "一"), ("2", "二"), ("3", "三"),
            ("4", "四"), ("5", "五"), ("6", "六"), ("7", "七"),
            ("8", "八"), ("9", "九"),
        ]
        for child in self.map_tree.get_children():
            self.map_tree.delete(child)
        for ch, audio in default_map:
            self.map_tree.insert("", "end", values=(ch, audio))
        zebra(self.map_tree)
        ok = self.save_map_silent()
        self.set_status("字符映射已恢复默认（已自动保存）" if ok else "恢复失败")

    # ===== 通用音频配置：启动音频 / 主界面播放音频 =====
    def browse_startup_audio(self):
        """浏览选择启动音频"""
        import tkinter.filedialog as fd
        filename = fd.askopenfilename(
            title="选择启动音频",
            initialdir=AUDIO_DIR,
            filetypes=[("音频文件", "*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg"), ("所有文件", "*.*")]
        )
        if filename:
            rel = self.to_rel_or_abs(filename)
            ok, msg = self.validate_audio_path(rel)
            if ok:
                self.startup_audio_entry.delete(0, "end")
                self.startup_audio_entry.insert(0, rel)
                self.save_bc_settings(silent=True)
                self.set_status(f"启动音频：{rel}（已自动保存）")
            else:
                self.set_status(f"启动音频校验失败：{msg}")

    def browse_main_audio(self):
        """浏览选择主界面播放音频"""
        import tkinter.filedialog as fd
        filename = fd.askopenfilename(
            title="选择主界面播放音频",
            initialdir=AUDIO_DIR,
            filetypes=[("音频文件", "*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg"), ("所有文件", "*.*")]
        )
        if filename:
            rel = self.to_rel_or_abs(filename)
            ok, msg = self.validate_audio_path(rel)
            if ok:
                self.main_audio_entry.delete(0, "end")
                self.main_audio_entry.insert(0, rel)
                self.save_bc_settings(silent=True)
                self.set_status(f"主界面播放音频：{rel}（已自动保存）")
            else:
                self.set_status(f"主界面播放音频校验失败：{msg}")

    def to_rel_or_abs(self, path):
        """路径转相对 AUDIO_DIR（优先），否则原样返回"""
        try:
            rel = os.path.relpath(path, AUDIO_DIR)
            if not rel.startswith(".."):
                return rel.replace("\\", "/")
        except Exception:
            pass
        return path

    def resolve_audio_path(self, path):
        """把配置里的路径解析为绝对路径（支持相对 AUDIO_DIR、绝对路径、URL）"""
        if not path:
            return None
        path = str(path).strip()
        if path.startswith(("http://", "https://")):
            return path
        p = path.replace("\\", os.sep).replace("/", os.sep)
        if os.path.isabs(p):
            return p
        return os.path.abspath(os.path.join(AUDIO_DIR, p))

    def validate_audio_path(self, path):
        """校验音频路径：存在、格式、大小、时长、可播放"""
        if not path or not str(path).strip():
            return False, "路径为空"
        path = str(path).strip()
        if path.startswith(("http://", "https://")):
            return True, "URL（在线音频）"
        p = self.resolve_audio_path(path)
        if not os.path.exists(p):
            return False, "文件不存在"
        ext = os.path.splitext(p)[1].lower()
        if ext not in (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"):
            return False, f"不支持的格式：{ext}"
        size = os.path.getsize(p)
        if size <= 0:
            return False, "文件为空（0 字节）"
        try:
            import soundfile as sf
            info = sf.info(p)
            dur = info.frames / info.samplerate
        except Exception:
            return False, "无法解析/不可播放"
        return True, f"{size // 1024}KB，{dur:.1f}秒"

    def preview_cfg_audio(self, entry):
        """试听配置的音频"""
        path = entry.get().strip() if entry else ""
        if not path:
            self.set_status("请先输入或选择音频")
            return
        ok, msg = self.validate_audio_path(path)
        if not ok:
            self.set_status(f"校验失败：{msg}")
            return
        self.set_status(f"试听中：{path}（{msg}）")
        self._preview_path = path
        self.play_single_audio(path)

    def stop_preview_audio(self):
        """停止试听"""
        import ctypes
        try:
            ctypes.windll.winmm.mciSendStringW("close all", None, 0, None)
        except Exception:
            pass
        self.set_status("已停止试听")

    def reset_default_audio(self):
        """恢复默认音频配置"""
        self.startup_audio_entry.delete(0, "end")
        self.startup_audio_entry.insert(0, "tsy/tsy2.mp3")
        self.main_audio_entry.delete(0, "end")
        self.set_status("已恢复默认音频（启动音频=tsy/tsy2.mp3，主界面播放音频=空）")

    def play_single_audio(self, path):
        """播放单个音频文件（线程内 MCI，防并发）"""
        import threading
        import ctypes
        import tempfile
        import shutil
        import os
        import time

        if getattr(self, "_playing", False):
            self.set_status("正在播放中，请稍候")
            return

        resolved = self.resolve_audio_path(path)
        if not resolved or resolved.startswith(("http://", "https://")):
            self.set_status("暂不支持在线 URL 播放，请使用本地文件")
            return
        if not os.path.exists(resolved):
            self.set_status(f"文件不存在：{path}")
            return

        self._playing = True

        def do_play():
            try:
                # 复制到纯英文临时路径，避免中文路径 MCI 报错
                tmp = os.path.join(tempfile.gettempdir(), "bc_single.mp3")
                if os.path.exists(tmp):
                    os.remove(tmp)
                shutil.copy2(resolved, tmp)
                mci = ctypes.windll.winmm
                alias = "bc_single"
                mci.mciSendStringW(f"close {alias}", None, 0, None)
                ret = mci.mciSendStringW(f'open "{tmp}" alias {alias}', None, 0, None)
                if ret != 0:
                    # 尝试原路径
                    ret = mci.mciSendStringW(f'open "{resolved}" alias {alias}', None, 0, None)
                if ret == 0:
                    mci.mciSendStringW(f"play {alias}", None, 0, None)
                    t0 = time.time()
                    while time.time() - t0 < 300:
                        # 停止标志：由播放线程自己退出并 close（停止立即生效）
                        if getattr(self, "_stop_flag", False):
                            break
                        status = ctypes.create_unicode_buffer(255)
                        mci.mciSendStringW(f"status {alias} mode", status, 255, None)
                        if status.value != "playing":
                            break
                        time.sleep(0.05)
                    mci.mciSendStringW(f"close {alias}", None, 0, None)
            except Exception:
                pass
            finally:
                self._playing = False

        threading.Thread(target=do_play, daemon=True).start()

    def add_map(self):
        """添加字符映射"""
        from tkinter import simpledialog
        ch = simpledialog.askstring("添加映射", "输入车次字符（如 G、1、X）:", parent=self)
        if not ch or not ch.strip():
            return
        ch = ch.strip().upper()
        audio = simpledialog.askstring("添加映射", f"输入 {ch} 对应的音频文件名（如 高）:", parent=self)
        if not audio or not audio.strip():
            return
        # 检查是否已存在
        for mc in self.map_tree.get_children():
            if self.map_tree.item(mc)["values"][0] == ch:
                self.map_tree.item(mc, values=(ch, audio.strip()))
                self.set_status(f"已更新映射：{ch} → {audio.strip()}")
                return
        self.map_tree.insert("", "end", values=(ch, audio.strip()))
        zebra(self.map_tree)
        self.set_status(f"已添加映射：{ch} → {audio.strip()}")

    def del_map(self):
        """删除选中映射（二次确认）"""
        sel = self.map_tree.selection()
        if sel:
            if not messagebox.askyesno("删除映射", "确定删除选中的字符映射吗？"):
                return
            self.map_tree.delete(sel)
            zebra(self.map_tree)
            self.set_status("已删除映射")
        else:
            self.set_status("请先选中要删除的映射")

    def map_lookup(self, ch, default):
        """查字符映射表"""
        ch = str(ch).upper()
        for mc in self.map_tree.get_children():
            vals = self.map_tree.item(mc)["values"]
            if vals and str(vals[0]).upper() == ch:
                return str(vals[1])
        return default

    def parse_step(self, step_val):
        """把步骤内容解析成 (subdir, filename) 或 ("var", 变量名) 或 ("__path__", 完整路径)"""
        step_val = str(step_val).strip()
        if not step_val:
            return None
        # 完整路径：音频文件实际存在 → 直接播放
        if os.path.exists(step_val) and step_val.lower().endswith((".mp3", ".wav")):
            return ("__path__", step_val)
        full_cand = os.path.join(AUDIO_DIR, step_val)
        if os.path.exists(full_cand) and full_cand.lower().endswith((".mp3", ".wav")):
            return ("__path__", full_cand)
        # 变量
        if step_val.startswith("{") and step_val.endswith("}"):
            return ("var", step_val[1:-1].strip())
        # 新格式 media2/子目录/文件
        if step_val.startswith("media2/"):
            rest = step_val[len("media2/"):]
            if "/" in rest:
                subdir, fn = rest.split("/", 1)
                return (subdir, fn.replace(".mp3", "").strip())
            return ("其他", rest.replace(".mp3", "").strip())
        # 新格式 media3/子目录/文件
        if step_val.startswith("media3/"):
            rest = step_val[len("media3/"):]
            if "/" in rest:
                subdir, fn = rest.split("/", 1)
                return (subdir, fn.replace(".mp3", "").strip())
            return ("其他", rest.replace(".mp3", "").strip())
        # 旧格式 子目录/文件
        if "/" in step_val:
            subdir, fn = step_val.split("/", 1)
            return (subdir.strip(), fn.replace(".mp3", "").strip())
        # 纯文件名 → 其他目录
        return ("其他", step_val.replace(".mp3", "").strip())

    def find_audio_file(self, subdir, filename, fuzzy=True):
        """按类型查找音频文件：精确 → 变体 → 模糊。
        搜索层：media2 → media3 → media（旧库，用户常放自定义音频）→ 根目录子目录"""
        root = AUDIO_DIR
        filename = str(filename).strip()
        if not filename:
            return None
        # 绝对路径（映射自定义路径）：直接使用
        if subdir == "__abs__":
            for cand in (filename, filename + ".mp3"):
                if os.path.exists(cand):
                    return cand
            return None
        # 语音包（扁平结构）模式：只在语音包内查找，绝不回退旧库
        if os.path.isdir(os.path.join(root, "单个字")) and os.path.isdir(os.path.join(root, "车站")):
            return self._find_in_voice_pack(subdir, filename, fuzzy)
        # 子目录含路径（如 media3/车站）：直接按 audio/路径 查找
        if "/" in subdir or "\\" in subdir:
            base = os.path.join(root, subdir.replace("\\", "/"))
            for cand in (os.path.join(base, filename + ".mp3"),
                         os.path.join(base, filename + "站.mp3")):
                if os.path.exists(cand):
                    return cand
            if fuzzy and os.path.isdir(base):
                try:
                    for f in os.listdir(base):
                        if f.endswith(".mp3") and filename in f:
                            return os.path.join(base, f)
                except Exception:
                    pass
            return None
        # 提示音：media2/提示音 → media/提示音 → media 根 → media2 根 → tsy
        if subdir == "提示音":
            for cand in (os.path.join(root, "media2", "提示音", filename + ".mp3"),
                         os.path.join(root, "media", "提示音", filename + ".mp3"),
                         os.path.join(root, "media", filename + ".mp3"),
                         os.path.join(root, "media2", filename + ".mp3"),
                         os.path.join(root, "tsy", filename + ".mp3"),
                         os.path.join(root, "tsy", "广播开始音" + filename + ".mp3"),
                         os.path.join(root, "tsy", "广播结束音" + filename + ".mp3")):
                if os.path.exists(cand):
                    return cand
            return None
        # 数字：精确 + 补零（1→01）
        if subdir == "数字":
            for base in (os.path.join(root, "media2", "数字"), os.path.join(root, "media", "数字")):
                cands = [os.path.join(base, filename + ".mp3")]
                if filename.isdigit():
                    cands.append(os.path.join(base, filename.zfill(2) + ".mp3"))
                for cand in cands:
                    if os.path.exists(cand):
                        return cand
            return None
        # 检票口：精确 + 小写
        if subdir == "检票口":
            for base in (os.path.join(root, "media2", "检票口"), os.path.join(root, "media", "检票口")):
                for cand in (os.path.join(base, filename + ".mp3"),
                             os.path.join(base, filename.lower() + ".mp3")):
                    if os.path.exists(cand):
                        return cand
            return None
        # 车站：media2/车站 → media3/车站 → media/车站 → media3/其他 → media/其他；精确 → +站 → 模糊
        if subdir == "车站":
            dirs = [os.path.join(root, "media2", "车站"),
                    os.path.join(root, "media3", "车站"),
                    os.path.join(root, "media", "车站"),
                    os.path.join(root, "media3", "其他"),
                    os.path.join(root, "media", "其他")]
            for d in dirs:
                p = os.path.join(d, filename + ".mp3")
                if os.path.exists(p):
                    return p
            for d in dirs:
                p = os.path.join(d, filename + "站.mp3")
                if os.path.exists(p):
                    return p
            if fuzzy:
                for d in dirs:
                    if not os.path.isdir(d):
                        continue
                    try:
                        for f in os.listdir(d):
                            if f.endswith(".mp3") and filename in f:
                                return os.path.join(d, f)
                    except Exception:
                        pass
            return None
        # 站台/股道：精确 → 小写 → 去末尾字母
        if subdir in ("站台", "股道"):
            for base in (os.path.join(root, "media2", subdir), os.path.join(root, "media", subdir)):
                for cand in (os.path.join(base, filename + ".mp3"),
                             os.path.join(base, filename.lower() + ".mp3")):
                    if os.path.exists(cand):
                        return cand
                if len(filename) > 1 and filename[-1].isalpha():
                    p = os.path.join(base, filename[:-1] + ".mp3")
                    if os.path.exists(p):
                        return p
            return None
        # 默认：同时搜索 media2/子目录、media3/子目录、media/子目录、AUDIO_DIR/子目录
        for base in (os.path.join(root, "media2", subdir),
                     os.path.join(root, "media3", subdir),
                     os.path.join(root, "media", subdir),
                     os.path.join(root, subdir)):
            for cand in (os.path.join(base, filename + ".mp3"),
                         os.path.join(base, filename + "站.mp3")):
                if os.path.exists(cand):
                    return cand
            if fuzzy and os.path.isdir(base):
                try:
                    for f in os.listdir(base):
                        if f.endswith(".mp3") and filename in f:
                            return os.path.join(base, f)
                except Exception:
                    pass
        # 全局兜底：全库文件名匹配（完整名优先且唯一，避免歧义）
        if fuzzy:
            scan_bases = (os.path.join(root, "media2"), os.path.join(root, "media3"),
                          os.path.join(root, "media"), os.path.join(root, "tsy"), root)
            exact_hits = []
            for sb in scan_bases:
                if not os.path.isdir(sb):
                    continue
                try:
                    for d in os.listdir(sb):
                        dd = os.path.join(sb, d)
                        if not os.path.isdir(dd):
                            continue
                        for f in os.listdir(dd):
                            if not f.endswith(".mp3"):
                                continue
                            if f[:-4] == filename:
                                exact_hits.append(os.path.join(dd, f))
                except Exception:
                    pass
            if len(exact_hits) == 1:
                return exact_hits[0]
            if len(exact_hits) > 1:
                # 多目录同名：优先 media3（常用自定义目录），其次 media
                for hit in exact_hits:
                    if "/media3/" in hit.replace("\\", "/"):
                        return hit
                for hit in exact_hits:
                    if "/media/" in hit.replace("\\", "/"):
                        return hit
                return exact_hits[0]
            # 包含匹配：取最短文件名（最接近原名）
            contain_hits = []
            for sb in scan_bases:
                if not os.path.isdir(sb):
                    continue
                try:
                    for d in os.listdir(sb):
                        dd = os.path.join(sb, d)
                        if not os.path.isdir(dd):
                            continue
                        for f in os.listdir(dd):
                            if f.endswith(".mp3") and filename in f:
                                contain_hits.append((len(f), os.path.join(dd, f)))
                except Exception:
                    pass
            if contain_hits:
                contain_hits.sort(key=lambda x: x[0])
                return contain_hits[0][1]
        return None

    def _find_in_voice_pack(self, subdir, filename, fuzzy=True):
        """新语音包（扁平结构）查找：只在语音包内，绝不回退旧库。
        适配：数字在"单个字"（汉字文件名 7→七）、站台带 t 后缀（3t.mp3）、
        提示音为"广播开始音1~5"、检票预告/开始检票/停止检票在 检票 目录下"""
        root = AUDIO_DIR
        filename = str(filename).strip()
        if not filename:
            return None
        # 兼容 media2/xxx、media3/xxx 旧写法 → 目录名取最后一段
        if "/" in subdir or "\\" in subdir:
            subdir = subdir.replace("\\", "/").rstrip("/").split("/")[-1]
        if not subdir:
            return None

        cands = [filename + ".mp3"]
        if subdir == "站台":
            cands.append(filename + "t.mp3")
            cands.append(filename + "站.mp3")
        elif subdir == "车站":
            cands.append(filename + "站.mp3")
        elif subdir.startswith("数字"):
            # 数字类目录（数字/数字2…）：先试本目录（数字2/七.mp3），再试单个字（汉字文件名 7→七）
            cn = CN_DIGITS.get(filename, filename)
            cn_cands = [cn + ".mp3", filename + ".mp3"]
            d_self = os.path.join(root, subdir)
            for c in cn_cands:
                p = os.path.join(d_self, c)
                if os.path.exists(p):
                    return p
            subdir = "单个字"
            cands = cn_cands

        d = os.path.join(root, subdir)
        for c in cands:
            p = os.path.join(d, c)
            if os.path.exists(p):
                return p

        # 模糊：该目录内包含文件名的
        if fuzzy and os.path.isdir(d):
            try:
                for f in os.listdir(d):
                    if f.endswith(".mp3") and filename in f:
                        return os.path.join(d, f)
            except Exception:
                pass

        # 全局兜底：只在语音包内递归模糊匹配（取最短文件名）
        if fuzzy:
            hits = []
            try:
                for base_dir, _dirs, files in os.walk(root):
                    for f in files:
                        if f.endswith(".mp3") and filename in f:
                            hits.append((len(f), os.path.join(base_dir, f)))
            except Exception:
                pass
            if hits:
                hits.sort(key=lambda x: x[0])
                return hits[0][1]
        return None

    def resolve_gate(self, gate):
        """检票口解析：完整文件 → 去字母（A1→1）→ 拆读（字母缺音频时跳过）
        目录取配置（检票口目录可自定义），字母按映射（映射值支持路径）"""
        gate = str(gate).upper()
        d = self.get_var_dir("检票口")
        # 1) 完整文件名（A1.mp3 / a1.mp3）
        if self.find_audio_file(d, gate):
            return [(d, gate)]
        # 2) 去字母：A1 → 1（读"一号检票口"）
        if len(gate) > 1 and gate[0].isalpha() and gate[1:].isdigit():
            pure = gate[1:]
            if self.find_audio_file(d, pure):
                return [(d, pure)]
            return [(self.get_var_dir("数字"), c) for c in pure]
        # 3) 拆读：数字先查映射表（改映射立即生效），字母查映射（无映射跳过）
        items = []
        for c in gate:
            if c.isdigit():
                mapped = self.map_lookup(c, "")
                if mapped:
                    ra = self.resolve_map_audio(mapped)
                    if ra:
                        items.append(ra)
                        continue
                items.append((self.get_var_dir("数字"), c))
            else:
                mapped = self.map_lookup(c, "")
                if mapped:
                    ra = self.resolve_map_audio(mapped)
                    if ra:
                        items.append(ra)
        return items

    @staticmethod
    def _parse_speed(s):
        try:
            return float(str(s).replace("x", "").strip() or "1.0")
        except Exception:
            return 1.0

    def resolve_audio_items(self, steps, values):
        """把步骤 + 车次值解析成音频片段列表（统一逻辑：车次/发站/到站/检票口/站台）
        空值字段自动跳过，避免"缺音频: 车站/"类误报"""
        tno = str(values.get("no") or "").strip().upper()
        tfrom = str(values.get("from") or "").strip()
        tto = str(values.get("to") or "").strip()
        tgate = str(values.get("gate") or "").strip()
        tplat = str(values.get("platform") or "").strip()
        audio_list = []
        for step in steps:
            # 兼容三种形式：[num, content, speed]（配置）、(0, [num, content, speed])（树包装）、(num, content)
            step_speed = 1.0
            num = 0
            if isinstance(step, (list, tuple)) and len(step) >= 2:
                num = step[0]
                content = step[1]
                if isinstance(step, (list, tuple)) and len(step) >= 3:
                    step_speed = self._parse_speed(step[2])
            else:
                content = step
            # 树包装的第二层：[num, content, speed] 或 (num, content)
            if isinstance(content, (list, tuple)) and len(content) >= 2:
                if len(content) >= 3:
                    step_speed = self._parse_speed(content[2])
                content = content[1]
            parsed = self.parse_step(content)
            if parsed is None:
                continue
            kind, value = parsed
            if kind == "var":
                # 变量音频标记 is_var=True：播放速度走"变量播放速度"
                if value == "车次":
                    if not tno:
                        continue
                    first = self.map_lookup(tno[0], "")
                    if first:
                        ra = self.resolve_map_audio(first)
                        if ra:
                            audio_list.append((ra[0], ra[1], step_speed, True))
                    for c in tno[1:]:
                        if c.isdigit():
                            _mapped = self.map_lookup(c, "")
                            if _mapped:
                                _ra = self.resolve_map_audio(_mapped)
                                if _ra:
                                    audio_list.append((_ra[0], _ra[1], step_speed, True))
                                    continue
                            audio_list.append((self.get_var_dir("数字"), c, step_speed, True))
                elif value == "发站":
                    if tfrom:
                        audio_list.append((self.get_var_dir("车站"), tfrom, step_speed, True))
                elif value == "到站":
                    if tto:
                        audio_list.append((self.get_var_dir("车站"), tto, step_speed, True))
                elif value == "检票口":
                    if tgate:
                        audio_list.extend([(s, f, step_speed, True) for s, f in self.resolve_gate(tgate)])
                elif value in ("站台", "停靠站台"):
                    if tplat:
                        audio_list.append((self.get_var_dir("站台"), str(tplat), step_speed, True))
                else:
                    audio_list.append(("其他", value, step_speed, True))
            else:
                # 主语音：is_var=False（用该步骤自己的播放速度）
                audio_list.append((kind, value, step_speed, False))
        return audio_list

    def test_play_steps(self):
        """测试播放所有步骤（用无缝拼接播放，含开始音/结束音/语速）"""
        self.sync_steps_to_memory()
        self.set_status("开始测试播放...")
        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")

        tree_steps = []
        for child in self.step_tree.get_children():
            vals = self.step_tree.item(child)["values"]
            spd = vals[2] if len(vals) > 2 else "1.00x"
            tree_steps.append((0, [vals[0], vals[1], spd]))
        # 测试播放优先用当前选中车次（贴近真实广播），无则用测试值
        if self.current_train and self.current_train.get("no"):
            tv = {
                "no": self.current_train.get("no", "G1234"),
                "from": self.current_train.get("from", "杭州东"),
                "to": self.current_train.get("to", "宁波"),
                "gate": self.current_train.get("gate", "A1"),
                "platform": self.current_train.get("platform", "3"),
            }
        else:
            tv = {"no": "G1234", "from": "杭州东", "to": "宁波", "gate": "A1", "platform": "3"}
        audio_list = self.resolve_audio_items(tree_steps, tv)

        if not audio_list:
            self.set_status("没有可播放的步骤（请先添加步骤）")
            self.bc_status_dot.configure(text="● 就绪", text_color="#4a4")
            return

        # 无缝拼接播放（自动带开始音/结束音/语速）
        self.play_concat_audio(audio_list)

    def create_broadcast_panel(self):
        """广播管理面板（专业车站广播控制台）"""
        panel = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        panel.grid_columnconfigure(0, weight=3)
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        # ===== 顶部工具栏 =====
        toolbar = ctk.CTkFrame(panel, fg_color=DS["panel"], corner_radius=8, height=50)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=(0, 8))
        toolbar.grid_propagate(False)

        toolbar_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        toolbar_inner.pack(fill="x", padx=12, pady=8)

        # 左边：标题
        ctk.CTkLabel(toolbar_inner, text="🚄 广播控制台", font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=DS["accent"]).pack(side="left", padx=(5, 20))

        # 中间：快捷按钮
        btn_style_tb = {"width": 80, "height": 32, "font": ctk.CTkFont(size=12)}

        ctk.CTkButton(toolbar_inner, text="+ 添车次", fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                     command=self.add_train_dialog, **btn_style_tb).pack(side="left", padx=3)

        ctk.CTkButton(toolbar_inner, text="- 删车次", fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                     command=self.del_selected_train, **btn_style_tb).pack(side="left", padx=3)

        ctk.CTkButton(toolbar_inner, text="🔄 刷新", fg_color=DS["btn"], hover_color=DS["btn_hover"],
                     command=self.refresh_trains, **btn_style_tb).pack(side="left", padx=3)

        ctk.CTkButton(toolbar_inner, text="⏹ 停止播放", fg_color="#555", hover_color="#777",
                     command=self.stop_all_audio, **btn_style_tb).pack(side="left", padx=3)

        # 右边：状态
        self.bc_status_dot = ctk.CTkLabel(toolbar_inner, text="● 系统就绪",
                                         font=ctk.CTkFont(size=12, weight="bold"),
                                         text_color="#4d4")
        self.bc_status_dot.pack(side="right", padx=10)

        # ===== 左侧：车次列表 =====
        left_frame = ctk.CTkFrame(panel, fg_color=DS["panel"], corner_radius=8)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        # 列表标题
        list_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        list_header.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 5))

        ctk.CTkLabel(list_header, text="今日车次列表", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=DS["accent"]).pack(side="left")

        ctk.CTkLabel(list_header, text="(点击选中车次后可广播)", font=ctk.CTkFont(size=11),
                    text_color="#667").pack(side="left", padx=10)

        # 车次表格
        columns = ("车次", "类型", "发站", "到站", "开点", "检票口", "站台", "状态", "到点")
        self.bc_train_tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=15)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview.Heading", font=(DS["font"], 10, "bold"),
                       background=DS["panel2"], foreground=DS["text"], relief="flat", padding=6)
        style.map("Treeview.Heading", background=[("active", DS["btn"])])
        style.configure("Treeview", font=(DS["font"], 10), rowheight=30,
                       background=DS["row1"], fieldbackground=DS["row1"], foreground=DS["text"], borderwidth=0)
        style.map("Treeview",
                  background=[("selected", DS["row_sel"])],
                  foreground=[("selected", "#ffffff")])
        # 斑马纹
        self.bc_train_tree.tag_configure("odd", background=DS["row1"])
        self.bc_train_tree.tag_configure("even", background=DS["row2"])

        col_widths = [70, 50, 80, 80, 60, 60, 50, 70, 60]
        for i, col in enumerate(columns):
            self.bc_train_tree.heading(col, text=col)
            self.bc_train_tree.column(col, width=col_widths[i], anchor="center")

        self.bc_train_tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.bc_train_tree.bind("<<TreeviewSelect>>", self.on_train_select)

        # 只加载已保存的车次（有多少辆显示多少辆，无数据不新增示例）
        self.load_trains_data()
        zebra(self.bc_train_tree)

        # ===== 右侧：广播操作面板（可滚动，紧急类型多时不裁切）=====
        right_frame = ctk.CTkScrollableFrame(panel, fg_color=DS["panel"], corner_radius=8)
        right_frame.grid(row=1, column=1, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)

        # 当前选中车次
        self.current_train_label = ctk.CTkLabel(right_frame, text="未选择车次",
                                            font=ctk.CTkFont(size=12, weight="bold"),
                                            text_color=DS["text_dim"],
                                            fg_color=DS["panel2"], corner_radius=6,
                                            height=28)
        self.current_train_label.pack(fill="x", padx=12, pady=(5, 4))

        # 广播按钮分组
        btn_style_big = {"font": ctk.CTkFont(size=13, weight="bold"), "height": 34, "corner_radius": 6}

        # 检票组
        ctk.CTkLabel(right_frame, text="── 检票广播 ──", font=ctk.CTkFont(size=11),
                    text_color="#667").pack(pady=(5, 3))

        ctk.CTkButton(right_frame, text="📢 检票预告", fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                     command=self.bcast_ticket_preview, **btn_style_big).pack(fill="x", padx=12, pady=4)

        ctk.CTkButton(right_frame, text="✅ 开始检票", fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                     command=self.bcast_ticket_start, **btn_style_big).pack(fill="x", padx=12, pady=4)

        ctk.CTkButton(right_frame, text="⏹ 停止检票", fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                     command=self.bcast_ticket_stop, **btn_style_big).pack(fill="x", padx=12, pady=4)

                # 紧急组：列车晚点 / 列车停运 / 其他 分组合并平铺（每行两个，点击即播）
        emg_types = [t for t in self.get_bcast_types() if t not in CHECKIN_TYPES]
        late_types = [t for t in emg_types if "晚点" in t]
        stop_types = [t for t in emg_types if "停运" in t]
        other_types = [t for t in emg_types if "晚点" not in t and "停运" not in t]

        emg_style = {"font": ctk.CTkFont(size=12, weight="bold"), "height": 28, "corner_radius": 6}

        def _emg_group(title, types, color, btn_color, btn_hover):
            ctk.CTkLabel(right_frame, text=f"── {title} ──", font=ctk.CTkFont(size=10),
                         text_color=color).pack(pady=(3, 1))
            if not types:
                return
            frame = ctk.CTkFrame(right_frame, fg_color="transparent")
            frame.pack(fill="x", padx=12, pady=1)
            for _i in range(2):
                frame.grid_columnconfigure(_i, weight=1)
            for _i, _typ in enumerate(types):
                _label = _typ.split("·")[-1].replace("紧急-", "")
                if _label.endswith("（通用）"):
                    _label = "通用"
                ctk.CTkButton(frame, text=f"🚨 {_label}",
                              fg_color=btn_color, hover_color=btn_hover,
                              command=lambda t=_typ: self.broadcast_emergency_type(t),
                              **emg_style).grid(row=_i // 2, column=_i % 2, sticky="ew", padx=2, pady=1)

        _emg_group("列车晚点", late_types, "#ff9a3d", DS["btn_warn"], DS["btn_warn_hover"])
        _emg_group("列车停运", stop_types, "#ff5a5a", DS["btn_danger"], DS["btn_danger_hover"])
        _emg_group("其他紧急", other_types, "#f66", DS["btn_danger"], DS["btn_danger_hover"])

        self.current_train = None
        self._playing = False

        return panel

    def get_trains_path(self):
        """车次数据文件（固定放在项目根目录）"""
        p = os.path.join(get_project_root(), "trains.json")
        try:
            old = os.path.join(get_app_root(), "trains.json")
            if os.path.exists(old) and os.path.abspath(old) != os.path.abspath(p) and not os.path.exists(p):
                with open(old, "r", encoding="utf-8") as f:
                    data = f.read()
                with open(p, "w", encoding="utf-8") as f:
                    f.write(data)
        except Exception:
            pass
        return p

    def save_trains_data(self):
        """把当前车次列表持久化到 trains.json（写入前自动备份）"""
        try:
            rows = [list(self.bc_train_tree.item(c)["values"]) for c in self.bc_train_tree.get_children()]
            self._backup_cfg(self.get_trains_path())
            with open(self.get_trains_path(), "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.set_status(f"车次保存失败: {e}")

    def load_trains_data(self):
        """从 trains.json 加载车次到主界面列表，成功返回 True"""
        path = self.get_trains_path()
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                rows = json.load(f)
            for r in rows:
                rr = list(r)
                if len(rr) < 9:
                    rr.append("--:--")  # 旧数据无到点字段，补默认值
                self.bc_train_tree.insert("", "end", values=tuple(rr))
            return True
        except Exception:
            return False

    def add_train_dialog(self):
        """添加车次对话框（弹窗输入 → 插入列表 → 持久化）"""
        # 防止已有对话框重复打开
        if getattr(self, "_train_dialog", None) is not None and self._train_dialog.winfo_exists():
            self._train_dialog.lift()
            self._train_dialog.focus_force()
            return
        dlg = ctk.CTkToplevel(self)
        self._train_dialog = dlg  # 保存引用，防止被 GC 回收导致窗口瞬间消失
        dlg.title("添加车次")
        dlg.geometry("380x470")
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=DS["panel"])

        ctk.CTkLabel(dlg, text="添加新车次", font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=DS["accent"]).grid(row=0, column=0, columnspan=3, padx=10, pady=(12, 8))

        labels = ["车次号", "类型", "发站", "到站", "开点", "到点", "检票口", "站台", "状态"]
        defaults = ["", "高铁", "", "", "", "--:--", "A1", "", "待检票"]
        fields = {}
        for i, (lab, dft) in enumerate(zip(labels, defaults)):
            ctk.CTkLabel(dlg, text=lab + ":", font=ctk.CTkFont(size=12),
                        text_color=DS["text_dim"]).grid(row=i + 1, column=0, sticky="e", padx=(12, 4), pady=4)
            e = ctk.CTkEntry(dlg, font=ctk.CTkFont(size=12),
                            placeholder_text=dft if dft else f"请输入{lab}")
            e.grid(row=i + 1, column=1, columnspan=2, sticky="ew", padx=4, pady=4)
            fields[lab] = e

        def on_ok():
            no = fields["车次号"].get().strip()
            if not no:
                self.set_status("车次号不能为空")
                return
            row = (no,
                   fields["类型"].get().strip() or "高铁",
                   fields["发站"].get().strip(),
                   fields["到站"].get().strip(),
                   fields["开点"].get().strip(),
                   fields["检票口"].get().strip() or "A1",
                   fields["站台"].get().strip(),
                   fields["状态"].get().strip() or "待检票",
                   fields["到点"].get().strip() or "--:--")
            self.bc_train_tree.insert("", "end", values=row)
            zebra(self.bc_train_tree)
            self.save_trains_data()
            self.set_status(f"已添加车次：{no}")
            self._train_dialog = None
            dlg.destroy()

        def on_cancel():
            self._train_dialog = None
            dlg.destroy()

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.grid(row=11, column=0, columnspan=3, pady=(14, 12))
        ctk.CTkButton(btn_row, text="确定添加", width=100, height=32,
                     fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                     command=on_ok).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="取消", width=80, height=32,
                     fg_color=DS["btn_neutral"], hover_color=DS["btn_neutral_hover"],
                     command=on_cancel).pack(side="left", padx=8)

    def refresh_trains(self):
        """刷新车次列表（从 trains.json 重载）"""
        self.set_status("刷新车次列表...")
        for c in self.bc_train_tree.get_children():
            self.bc_train_tree.delete(c)
        self.load_trains_data()
        zebra(self.bc_train_tree)
        self.current_train = None
        self.current_train_label.configure(text="未选择车次")
        self.set_status("车次列表已刷新")

    def add_train_to_list(self):
        """兼容入口：弹出添加车次对话框"""
        self.add_train_dialog()

    def del_selected_train(self):
        """删除选中车次（二次确认 + 持久化）"""
        sel = self.bc_train_tree.selection()
        if sel:
            if not messagebox.askyesno("删除车次", "确定删除选中的车次吗？"):
                return
            self.bc_train_tree.delete(sel)
            zebra(self.bc_train_tree)
            self.save_trains_data()
            self.current_train = None
            self.current_train_label.configure(text="未选择车次")
            self.set_status("已删除车次")
        else:
            self.set_status("请先选择车次")

    def on_train_select(self, event):
        """选中车次（列: 车次/类型/发站/到站/开点/检票口/站台/状态）"""
        sel = self.bc_train_tree.selection()
        if sel:
            item = self.bc_train_tree.item(sel[0])
            vals = item["values"]
            no = vals[0]
            self.current_train = {
                "no": no,
                "from": vals[2],     # 发站
                "to": vals[3],       # 到站
                "gate": vals[5],     # 检票口
                "platform": vals[6], # 站台
            }
            self.current_train_label.configure(text=f"当前车次：{no}  {vals[2]}→{vals[3]}  {vals[5]}口 {vals[6]}站台")
            self.set_status(f"已选择：{no}")
        else:
            # 取消选择：清空当前车次，防止对旧车次误广播
            self.current_train = None
            if hasattr(self, "current_train_label"):
                self.current_train_label.configure(text="未选择车次")

    def play_audio_by_name(self, audio_name, subdir="其他"):
        """根据文件名播放音频"""
        import os
        audio_path = os.path.join(AUDIO_DIR, "media3", subdir, audio_name + ".mp3")
        audio_path = os.path.abspath(audio_path)
        self.play_audio_file("media3/" + subdir + "/" + audio_name + ".mp3")

    def build_audio_list_from_steps(self, type_name, steps_override=None):
        """根据配置步骤（或手动排序步骤） + 当前车次，构建音频片段列表"""
        # 播放前强制同步：面板里的修改（即使未点保存）立即生效
        self.sync_steps_to_memory()
        # 读配置步骤（手动排序窗口可传入 steps_override）
        steps = None
        if steps_override is not None:
            steps = list(steps_override)
        elif hasattr(self, "bc_steps"):
            steps = self.bc_steps.get(type_name)
        if not steps:
            steps = self.get_default_steps(type_name)

        # 测试值兜底（未选车次时）
        test_from = "杭州东" if not (self.current_train and self.current_train.get("from")) else self.current_train["from"]
        test_to = "宁波" if not (self.current_train and self.current_train.get("to")) else self.current_train["to"]
        test_no = "G1234" if not (self.current_train and self.current_train.get("no")) else self.current_train["no"]
        test_gate = "A1" if not (self.current_train and self.current_train.get("gate")) else self.current_train["gate"]

        values = {
            "no": test_no,
            "from": test_from,
            "to": test_to,
            "gate": test_gate,
            "platform": self.current_train.get("platform") if self.current_train else "3",
        }
        return self.resolve_audio_items(steps, values)

    def bcast_ticket_preview(self):
        """检票预告广播：按广播设置里配置的步骤播放"""
        if not self.current_train:
            self.set_status("请先选择车次！")
            return

        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        self.set_status(f"检票预告：{self.current_train['no']}")
        self._active_bcast_train = self.current_train["no"]
        # keep=True：检票业务状态由广播操作决定，播放结束不重置
        self._set_train_state(self.current_train["no"], "待检票", keep=True)

        audio_list = self.build_audio_list_from_steps("检票预告")
        self.play_concat_audio(audio_list)

    def bcast_ticket_start(self):
        """开始检票广播：按广播设置里配置的步骤播放"""
        if not self.current_train:
            self.set_status("请先选择车次！")
            return

        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        self.set_status(f"开始检票：{self.current_train['no']}")
        self._active_bcast_train = self.current_train["no"]
        # keep=True：开始检票后保持"正在检票"，直到手动停止/结束检票
        self._set_train_state(self.current_train["no"], "正在检票", keep=True)

        audio_list = self.build_audio_list_from_steps("开始检票")
        self.play_concat_audio(audio_list)

    def bcast_ticket_stop(self):
        """停止检票：按广播设置里配置的步骤播放"""
        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        self.set_status("停止检票")
        if self.current_train:
            self._active_bcast_train = self.current_train["no"]
            # keep=True：停止检票后保持"停止检票"，播放结束不重置
            self._set_train_state(self.current_train["no"], "停止检票", keep=True)
        audio_list = self.build_audio_list_from_steps("停止检票")
        self.play_concat_audio(audio_list)

    def bcast_emergency(self):
        """紧急广播（列车晚点）"""
        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        self.set_status("紧急广播")
        audio_list = self.build_audio_list_from_steps("紧急-列车晚点")
        self.play_concat_audio(audio_list)

    def broadcast_emergency_type(self, emg_type):
        """按类型播放紧急广播（从配置步骤读取，自动带开始音/结束音）
        晚点/停运类型触发时同步选中车次状态到大屏（持续性状态，播完不恢复）"""
        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        self.set_status(f"紧急广播：{emg_type}")

        if self.current_train:
            no = self.current_train["no"]
            if "晚点" in emg_type:
                self._set_train_state(no, "晚点", keep=True)
            elif "停运" in emg_type:
                self._set_train_state(no, "停运", keep=True)

        audio_list = self.build_audio_list_from_steps(emg_type)
        self.play_concat_audio(audio_list)

    def simple_broadcast(self, name):
        """简单广播：直接播放对应的完整音频文件"""
        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        self.set_status(f"正在广播：{name}")

        # 音频文件映射
        audio_map = {
            "检票预告": "其他/旅客们，你们好。由",
            "开始检票": "其他/现在开始检票，请持有该车车票的",
            "停止检票": "紧急广播/停止检票",
            "紧急广播": "紧急广播/列车晚点",
        }

        if name in audio_map:
            self.play_audio_file("media3/" + audio_map[name] + ".mp3")

        # 3秒后恢复
        self.after(3000, lambda: self.bc_status_dot.configure(text="● 就绪", text_color="#4a4"))

    def play_manual(self):
        """手动播放：输入文件名则播放该文件；为空且有主界面播放音频配置则播放配置音频"""
        text = self.manual_entry.get().strip()
        if text:
            # 支持直接输入完整路径或相对路径
            resolved = self.resolve_audio_path(text)
            if os.path.exists(resolved):
                self.play_single_audio(resolved)
                self.set_status(f"播放：{text}")
            else:
                self.play_audio_file("media3/其他/" + text + ".mp3")
                self.set_status(f"播放：{text}")
        else:
            main_audio = ""
            if hasattr(self, "main_audio_entry"):
                main_audio = self.main_audio_entry.get().strip()
            if main_audio:
                self.play_single_audio(main_audio)
                self.set_status(f"播放主界面音频：{main_audio}")
            else:
                self.set_status("请输入文件名")

    def load_manual_steps(self):
        """读取手动播放排序步骤（配置 manual_steps：[[音频, 语速], ...]）"""
        try:
            pth = self.get_config_path()
            if os.path.exists(pth):
                with open(pth, "r", encoding="utf-8") as f:
                    _c = json.load(f)
                raw = _c.get("manual_steps") or []
                out = []
                for s in raw:
                    if isinstance(s, (list, tuple)) and s:
                        out.append([str(s[0]), str(s[1]) if len(s) > 1 else "1.00x"])
                return out
        except Exception:
            pass
        return []

    def save_manual_steps(self):
        """把手动播放步骤树保存到配置（立即持久化）"""
        try:
            pth = self.get_config_path()
            self._backup_cfg(pth)
            cfg = {}
            if os.path.exists(pth):
                with open(pth, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            steps = []
            if hasattr(self, "manual_tree") and self.manual_tree.winfo_exists():
                for c in self.manual_tree.get_children():
                    v = self.manual_tree.item(c)["values"]
                    steps.append([str(v[1]), str(v[2]) if len(v) > 2 else "1.00x"])
            cfg["manual_steps"] = steps
            with open(pth, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            self.set_status(f"手动播放顺序已保存（{len(steps)} 步）")
        except Exception as e:
            self.set_status(f"手动播放顺序保存失败: {e}")

    def open_manual_play_dialog(self):
        """手动播放（排序模式）：窗口配置步骤顺序 → 播放/保存"""
        if getattr(self, "_manual_dlg", None) is not None and self._manual_dlg.winfo_exists():
            self._manual_dlg.lift()
            self._manual_dlg.focus_force()
            return
        dlg = ctk.CTkToplevel(self)
        self._manual_dlg = dlg
        dlg.title("手动播放（排序模式）")
        dlg.geometry("600x560")
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color=DS["panel"])
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(dlg, text="🔄 手动播放（排序模式）", font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=DS["accent"]).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(dlg, text="每行一步：音频文件或 {变量}；双击可编辑内容与语速；播放时按顺序依次合成",
                     font=ctk.CTkFont(size=11), text_color=DS["text_dim"]).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        cols = ("顺序", "音频文件", "语速")
        self.manual_tree = ttk.Treeview(dlg, columns=cols, show="headings", height=12)
        self.manual_tree.heading("顺序", text="顺序")
        self.manual_tree.heading("音频文件", text="音频文件路径")
        self.manual_tree.heading("语速", text="语速")
        self.manual_tree.column("顺序", width=52, anchor="center")
        self.manual_tree.column("音频文件", width=330, anchor="w")
        self.manual_tree.column("语速", width=56, anchor="center")
        self.manual_tree.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 6))
        self.manual_tree.bind("<Double-1>", self.edit_manual_cell)

        steps = self.load_manual_steps()
        for i, s in enumerate(steps):
            self.manual_tree.insert("", "end", values=(i + 1, s[0], s[1]))
        zebra(self.manual_tree)

        # 编辑按钮行
        edit_row = ctk.CTkFrame(dlg, fg_color="transparent")
        edit_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 6))
        ctk.CTkButton(edit_row, text="📁 浏览选择音频...", height=30, fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                      font=ctk.CTkFont(size=11), command=self.manual_add_file).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ctk.CTkButton(edit_row, text="＋ 变量", width=80, height=30, fg_color="#7a5a1e", hover_color="#9a7a2a",
                      font=ctk.CTkFont(size=11), command=self.manual_insert_var).pack(side="left", padx=(3, 0))

        move_row = ctk.CTkFrame(dlg, fg_color="transparent")
        move_row.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 6))
        for txt, cmd, w in [("↑ 上移", lambda: self.manual_move_step(-1), 70),
                            ("↓ 下移", lambda: self.manual_move_step(1), 70),
                            ("删除", self.manual_del_step, 70)]:
            ctk.CTkButton(move_row, text=txt, width=w, height=30, fg_color=DS["btn"], hover_color=DS["btn_hover"],
                          font=ctk.CTkFont(size=11), command=cmd).pack(side="left", padx=3)

        # 播放控制行
        play_row = ctk.CTkFrame(dlg, fg_color="transparent")
        play_row.grid(row=5, column=0, sticky="ew", padx=16, pady=(6, 12))
        ctk.CTkButton(play_row, text="▶ 播放", height=34, fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                      font=ctk.CTkFont(size=12, weight="bold"), command=self.play_manual_steps).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ctk.CTkButton(play_row, text="⏹ 停止", height=34, fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                      font=ctk.CTkFont(size=12), command=self.stop_all_audio).pack(side="left", fill="x", expand=True, padx=(3, 3))
        ctk.CTkButton(play_row, text="💾 保存顺序", height=34, fg_color="#555", hover_color="#777",
                      font=ctk.CTkFont(size=12), command=self.save_manual_steps).pack(side="left", fill="x", expand=True, padx=(3, 0))

    def manual_add_file(self):
        """手动播放：浏览选择音频文件插入步骤"""
        from tkinter import filedialog
        fp = filedialog.askopenfilename(title="选择音频文件",
                                        filetypes=[("音频文件", "*.mp3 *.wav"), ("所有文件", "*.*")])
        if not fp:
            return
        # 转为相对项目根的路径（存在则相对，否则绝对）
        try:
            rel = os.path.relpath(fp, get_project_root())
            if not rel.startswith(".."):
                disp = rel
            else:
                disp = fp
        except Exception:
            disp = fp
        n = len(self.manual_tree.get_children()) + 1
        self.manual_tree.insert("", "end", values=(n, disp, "1.00x"))
        zebra(self.manual_tree)

    def manual_insert_var(self):
        """手动播放：插入变量步骤"""
        n = len(self.manual_tree.get_children()) + 1
        self.manual_tree.insert("", "end", values=(n, "{车次}", "1.00x"))
        zebra(self.manual_tree)

    def manual_move_step(self, delta):
        sel = self.manual_tree.selection()
        if not sel:
            return
        target = sel[0]
        children = self.manual_tree.get_children()
        idx = children.index(target)
        nidx = idx + delta
        if nidx < 0 or nidx >= len(children):
            return
        item = self.manual_tree.item(target)
        self.manual_tree.delete(target)
        self.manual_tree.insert("", nidx, iid=target, values=item["values"])
        self.renumber_manual_steps()
        self.manual_tree.selection_set(target)
        zebra(self.manual_tree)

    def manual_del_step(self):
        sel = self.manual_tree.selection()
        if not sel:
            return
        self.manual_tree.delete(sel[0])
        self.renumber_manual_steps()
        zebra(self.manual_tree)

    def renumber_manual_steps(self):
        for i, c in enumerate(self.manual_tree.get_children()):
            v = list(self.manual_tree.item(c)["values"])
            v[0] = i + 1
            self.manual_tree.item(c, values=tuple(v))

    def edit_manual_cell(self, event):
        """双击编辑手动播放步骤（内容 或 语速）"""
        region = self.manual_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.manual_tree.identify_column(event.x)
        row = self.manual_tree.identify_row(event.y)
        if not row:
            return
        idx = int(col.replace("#", "")) - 1
        if idx == 0:
            return
        vals = list(self.manual_tree.item(row)["values"])
        from tkinter import simpledialog
        if idx == 1:
            new = simpledialog.askstring("编辑音频", "音频文件路径（相对项目根）或 {变量}：", initialvalue=str(vals[1]))
        else:
            new = simpledialog.askstring("编辑语速", "本步语速（1.00x=跟随整体，如 0.75 / 1.25 / 1.50）：", initialvalue=str(vals[2]))
        if new:
            vals[idx] = new
            self.manual_tree.item(row, values=tuple(vals))

    def play_manual_steps(self):
        """按手动播放排序步骤播放（与检票广播同一引擎，自动带开始音/结束音）"""
        steps = []
        for c in self.manual_tree.get_children():
            v = self.manual_tree.item(c)["values"]
            steps.append([str(v[0]), str(v[1]), str(v[2])])
        if not steps:
            self.set_status("手动播放：请先添加音频步骤")
            return
        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        self.set_status(f"手动播放：{len(steps)} 步按顺序合成")
        audio_list = self.build_audio_list_from_steps("手动播放", steps_override=steps)
        self.play_concat_audio(audio_list)

    def get_bcast_types(self):
        """广播类型列表：内存优先 → 配置 → 默认（广播设置可自定义排序/添加）"""
        if getattr(self, "_bcast_types", None):
            return list(self._bcast_types)
        try:
            p = self.get_config_path()
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    _c = json.load(f)
                if _c.get("bcast_types"):
                    self._bcast_types = list(_c["bcast_types"])
                    return list(self._bcast_types)
        except Exception:
            pass
        self._bcast_types = list(DEFAULT_BC_TYPES)
        return list(self._bcast_types)

    def refresh_type_combos(self):
        """类型下拉刷新（添加/删除/排序后调用）"""
        types = self.get_bcast_types()
        if hasattr(self, "bc_type_cmb") and self.bc_type_cmb.winfo_exists():
            cur = self.bc_type_cmb.get()
            self.bc_type_cmb.configure(values=types)
            if cur in types:
                self.bc_type_cmb.set(cur)
            else:
                self.bc_type_cmb.set(types[0] if types else "")
        if hasattr(self, "sched_type_cmb") and self.sched_type_cmb.winfo_exists():
            cur = self.sched_type_cmb.get()
            self.sched_type_cmb.configure(values=types)
            if cur in types:
                self.sched_type_cmb.set(cur)
            else:
                self.sched_type_cmb.set(types[0] if types else "")
        if hasattr(self, "type_tree") and self.type_tree.winfo_exists():
            for c in self.type_tree.get_children():
                self.type_tree.delete(c)
            for typ in types:
                self.type_tree.insert("", "end", values=(typ,))
            zebra(self.type_tree)

    def get_config_path(self):
        """配置文件路径（固定放在项目根目录，不随音频目录/打包目录变化）"""
        p = os.path.join(get_project_root(), "bcast_config.json")
        # 旧版本曾写入打包目录(dist\main_ui)：若新位置没有而旧位置有，自动迁移，避免配置丢失
        try:
            old = os.path.join(get_app_root(), "bcast_config.json")
            if os.path.exists(old) and os.path.abspath(old) != os.path.abspath(p) and not os.path.exists(p):
                with open(old, "r", encoding="utf-8") as f:
                    data = f.read()
                with open(p, "w", encoding="utf-8") as f:
                    f.write(data)
        except Exception:
            pass
        return p

    @staticmethod
    def _backup_cfg(path):
        """保存前备份旧配置（保留最近一版 .bak，防止配置意外丢失）"""
        try:
            import shutil
            if path and os.path.exists(path):
                shutil.copy(path, path + ".bak")
        except Exception:
            pass

    def load_bc_config(self):
        """加载广播配置（开始音/结束音/步骤/映射）"""
        cfg_path = self.get_config_path()
        if not os.path.exists(cfg_path):
            return
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            # 主配置损坏/缺失 → 自动从备份恢复（防止配置丢失）
            cfg = {}
            try:
                _bk = cfg_path + ".bak"
                if os.path.exists(_bk):
                    with open(_bk, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    import shutil
                    shutil.copy(_bk, cfg_path)
            except Exception:
                pass
            if not cfg:
                return

        # 开始音/结束音
        if cfg.get("start_sound"):
            self.start_sound_btn.configure(text=cfg["start_sound"])
        if cfg.get("end_sound"):
            self.end_sound_btn.configure(text=cfg["end_sound"])

        # 语速
        try:
            if "speed" in cfg and hasattr(self, "speed_slider"):
                self.speed_slider.set(float(cfg["speed"]))
                self.speed_label.configure(text=f"{float(cfg['speed']):.2f}x")
            if "var_speed" in cfg and hasattr(self, "var_speed_slider"):
                self.var_speed_slider.set(float(cfg["var_speed"]))
                self.var_speed_label.configure(text=f"{float(cfg['var_speed']):.2f}x")
        except Exception:
            pass
        if hasattr(self, "station_entry"):
            self.station_entry.delete(0, "end")
            self.station_entry.insert(0, str(cfg.get("station_name", "丽水站")))
        if hasattr(self, "stop_min_entry"):
            self.stop_min_entry.delete(0, "end")
            self.stop_min_entry.insert(0, str(cfg.get("stop_check_min", 5)))

        # 启动音频 / 主界面播放音频（通用音频配置）
        if hasattr(self, "startup_audio_entry"):
            self.startup_audio_entry.delete(0, "end")
            self.startup_audio_entry.insert(0, cfg.get("startup_audio", "tsy/tsy2.mp3"))
        if hasattr(self, "main_audio_entry"):
            self.main_audio_entry.delete(0, "end")
            self.main_audio_entry.insert(0, cfg.get("main_audio", ""))

        # 步骤（所有类型 → 内存字典，再显示当前类型）
        if cfg.get("steps"):
            self.bc_steps = {}
            for typ, steps in cfg["steps"].items():
                norm = []
                for s in steps:
                    s = list(s)
                    norm.append([str(s[0]), str(s[1]), (str(s[2]) if len(s) > 2 else "1.00x")])
                self.bc_steps[typ] = norm
            # 显示当前类型
            if hasattr(self, "step_tree"):
                cur_type = self.bc_type_cmb.get()
                steps = self.bc_steps.get(cur_type) or self.get_default_steps(cur_type)
                for child in self.step_tree.get_children():
                    self.step_tree.delete(child)
                for s in steps:
                    if isinstance(s, (list, tuple)) and len(s) >= 3:
                        self.step_tree.insert("", "end", values=(s[0], s[1], s[2]))
                    else:
                        num, content = s[0], s[1]
                        self.step_tree.insert("", "end", values=(num, content, "1.00x"))
                zebra(self.step_tree)
                self._cur_bc_type = cur_type

        # 字符映射（合并默认：用户未配置的键自动补默认，数字映射永远齐全）
        if cfg.get("char_map") and hasattr(self, "map_tree"):
            for child in self.map_tree.get_children():
                self.map_tree.delete(child)
            merged = dict(cfg["char_map"])
            for _ch, _audio in [("G", "高"), ("D", "动"), ("K", "快"),
                                ("0", "零"), ("1", "一"), ("2", "二"), ("3", "三"),
                                ("4", "四"), ("5", "五"), ("6", "六"), ("7", "七"),
                                ("8", "八"), ("9", "九")]:
                if _ch not in merged:
                    merged[_ch] = _audio
            for ch, audio in merged.items():
                self.map_tree.insert("", "end", values=(ch, audio))
            zebra(self.map_tree)

        # 变量音频目录
        if hasattr(self, "var_dir_entries"):
            for k, entry in self.var_dir_entries.items():
                entry.delete(0, "end")
                entry.insert(0, cfg.get("dir_map", {}).get(k, k))
            self.dir_map = dict(cfg.get("dir_map") or {})

        # 定时广播任务
        if cfg.get("schedule") and hasattr(self, "bc_schedule"):
            self.bc_schedule = [dict(s) for s in cfg["schedule"]]
            self.refresh_sched_list_ui()

    def save_bc_settings(self, silent=False):
        """保存广播设置到配置文件；silent=True 时只更新状态栏，不弹窗（修改即自动保存）"""
        # 初始化保护（未切换过类型时也能保存）
        if not hasattr(self, "bc_steps"):
            self.bc_steps = {}
        if not hasattr(self, "_cur_bc_type"):
            self._cur_bc_type = "检票预告"
        # 当前类型不存在时补默认（类型可自定义）
        for typ in self.get_bcast_types():
            if typ not in self.bc_steps:
                self.bc_steps[typ] = [list(s) for s in self.get_default_steps(typ)]

        cfg = {}

        # 保留定时广播配置（防止本次保存覆盖丢失）
        _sched_old = []
        try:
            if os.path.exists(self.get_config_path()):
                with open(self.get_config_path(), encoding="utf-8") as _f:
                    _old_cfg = json.load(_f)
                _sched_old = _old_cfg.get("schedule") or []
        except Exception:
            pass

        # 开始音/结束音
        cfg["start_sound"] = self.start_sound_btn.cget("text")
        cfg["end_sound"] = self.end_sound_btn.cget("text")
        if cfg["end_sound"] == "无（点击选择）":
            cfg["end_sound"] = ""

        # 语速
        try:
            cfg["speed"] = float(self.speed_slider.get())
            cfg["var_speed"] = float(self.var_speed_slider.get()) if hasattr(self, "var_speed_slider") else 1.0
        except Exception:
            cfg["speed"] = 1.0
            cfg["var_speed"] = 1.0
        if hasattr(self, "station_entry"):
            cfg["station_name"] = self.station_entry.get().strip() or "丽水站"
        if hasattr(self, "stop_min_entry"):
            try:
                cfg["stop_check_min"] = max(1, int(float(self.stop_min_entry.get().strip() or "5")))
            except Exception:
                cfg["stop_check_min"] = 5

        # 启动音频 / 主界面播放音频（通用音频配置）
        cfg["startup_audio"] = self.startup_audio_entry.get().strip() if hasattr(self, "startup_audio_entry") else ""
        cfg["main_audio"] = self.main_audio_entry.get().strip() if hasattr(self, "main_audio_entry") else ""

        # 先把当前显示的步骤同步进内存字典
        self.sync_steps_to_memory()

        # 步骤（所有类型，从内存字典读取，绝不覆盖用户设置）
        cfg["steps"] = {}
        for typ in self.get_bcast_types():
            steps = self.bc_steps.get(typ)
            if steps is None:
                steps = self.get_default_steps(typ)
                self.bc_steps[typ] = [list(s) for s in steps]
            out_steps = []
            for s in steps:
                s = list(s)
                spd = str(s[2]) if len(s) > 2 else "1.00x"
                out_steps.append([str(s[0]), str(s[1]), spd])
            cfg["steps"][typ] = out_steps

        # 字符映射
        cfg["char_map"] = {}
        for child in self.map_tree.get_children():
            vals = self.map_tree.item(child)["values"]
            cfg["char_map"][str(vals[0])] = str(vals[1])

        # 变量音频目录
        cfg["dir_map"] = {}
        for k in ("车站", "检票口", "站台", "数字", "单个字"):
            cfg["dir_map"][k] = self.get_var_dir(k)

        # 定时广播任务（有内存列表用内存，否则保留旧配置）
        cfg["schedule"] = [dict(s) for s in getattr(self, "bc_schedule", _sched_old)]

        # 广播类型列表（自定义排序/添加后持久化）
        cfg["bcast_types"] = self.get_bcast_types()

        # 空步骤提示（不阻止保存，播放时会跳过）
        empty_count = 0
        for typ in cfg["steps"]:
            for s in cfg["steps"][typ]:
                if not str(s[1]).strip():
                    empty_count += 1

        # 写入文件（写入前自动备份旧配置，防止意外丢失）
        try:
            cfg_path = self.get_config_path()
            self._backup_cfg(cfg_path)
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            if silent:
                self.set_status("广播设置已自动保存" + (f"（有 {empty_count} 个空步骤，播放时会自动跳过）" if empty_count else ""))
            else:
                self.set_status("广播设置已保存")
                if empty_count:
                    messagebox.showinfo("保存成功",
                                        f"广播设置已保存（有 {empty_count} 个空步骤，播放时会自动跳过）")
                else:
                    messagebox.showinfo("保存成功", "广播设置已保存，重启后依然生效")
        except Exception as e:
            self.set_status(f"保存失败: {e}")
            messagebox.showerror("保存失败", f"广播设置保存失败：{e}\n请检查磁盘权限。")

    def cancel_bc_changes(self):
        """取消修改：把步骤恢复为磁盘上已保存的配置（没有则恢复默认）"""
        cfg_path = self.get_config_path()
        loaded = False
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if cfg.get("steps") and hasattr(self, "step_tree"):
                    cur_type = self._cur_bc_type
                    steps = cfg["steps"].get(cur_type)
                    if steps:
                        for child in self.step_tree.get_children():
                            self.step_tree.delete(child)
                        for s in steps:
                            if isinstance(s, (list, tuple)) and len(s) >= 3:
                                self.step_tree.insert("", "end", values=(s[0], s[1], s[2]))
                            else:
                                num, content = s[0], s[1]
                                self.step_tree.insert("", "end", values=(num, content, "1.00x"))
                        self.renumber_steps()
                        self.sync_steps_to_memory()
                        loaded = True
            except Exception:
                pass
        if not loaded:
            # 无磁盘配置 → 恢复默认
            cur_type = getattr(self, "_cur_bc_type", "检票预告")
            for child in self.step_tree.get_children():
                self.step_tree.delete(child)
            for num, content in self.get_default_steps(cur_type):
                self.step_tree.insert("", "end", values=(num, content, "1.00x"))
            self.renumber_steps()
            self.sync_steps_to_memory()
        self.set_status("已取消修改，恢复为已保存配置")

    def reset_default_steps(self):
        """恢复当前类型为默认步骤"""
        if not messagebox.askyesno("恢复默认", "确定把当前类型的广播步骤恢复为默认顺序吗？"):
            return
        cur_type = getattr(self, "_cur_bc_type", "检票预告")
        for child in self.step_tree.get_children():
            self.step_tree.delete(child)
        for num, content in self.get_default_steps(cur_type):
            self.step_tree.insert("", "end", values=(num, content, "1.00x"))
        self.renumber_steps()
        self.sync_steps_to_memory()
        self.set_status(f"已恢复 {cur_type} 为默认步骤")

    def _save_steps_silent_after_drag(self):
        """拖拽排序结束后自动保存"""
        try:
            self.save_bc_settings(silent=True)
        except Exception:
            pass

    def bind_step_drag(self):
        """给步骤表绑定拖拽排序"""
        tree = self.step_tree

        def on_press(event):
            iid = tree.identify_row(event.y)
            if iid:
                tree._drag_row = iid
                tree.selection_set(iid)

        def on_release(event):
            src = getattr(tree, "_drag_row", None)
            tree._drag_row = None
            if not src:
                return
            dst = tree.identify_row(event.y)
            if dst and dst != src:
                children = tree.get_children()
                if src in children and dst in children:
                    item = tree.item(src)
                    # 判断拖到 dst 行的上半还是下半：上半→插到 dst 前，下半→插到 dst 后
                    above = False
                    bbox = tree.bbox(dst)
                    if bbox:
                        above = event.y < bbox[1] + bbox[3] / 2
                    tree.delete(src)
                    children2 = tree.get_children()
                    di2 = children2.index(dst) if dst in children2 else 0
                    insert_pos = di2 if above else di2 + 1
                    tree.insert("", insert_pos, iid=src, values=item["values"])
                    self.renumber_steps()
                    self.sync_steps_to_memory()
                    self._save_steps_silent_after_drag()
                    self.set_status("已调整顺序（拖拽，已自动保存）")

        tree.bind("<Button-1>", on_press, add="+")
        tree.bind("<B1-Motion>", lambda e: None, add="+")
        tree.bind("<ButtonRelease-1>", on_release, add="+")

    def on_bc_train_select(self, event):
        """选中车次事件（与主界面选中同步）"""
        selected = self.bc_train_tree.selection()
        if selected:
            item = self.bc_train_tree.item(selected[0])
            vals = item["values"]
            train_no = vals[0]
            self.current_train = {
                "no": train_no,
                "from": vals[2],
                "to": vals[3],
                "gate": vals[5] if len(vals) > 5 else "A1",
                "platform": vals[6] if len(vals) > 6 else "",
            }
            self.set_status(f"已选择：{train_no}")

    def do_broadcast(self, broadcast_type):
        """执行广播（按类型走配置步骤）"""
        if not self.current_train:
            self.set_status("请先选择车次！")
            return

        self.bc_status_dot.configure(text="● 广播中", text_color=DS["warn"])
        if broadcast_type == "检票预告广播":
            self.bcast_ticket_preview()
        elif broadcast_type == "检票进站广播":
            self.bcast_ticket_start()
        elif broadcast_type == "停止检票广播":
            self.bcast_ticket_stop()
        elif broadcast_type == "列车晚点":
            self.broadcast_emergency_type("紧急-列车晚点")
        else:
            self.simple_broadcast(broadcast_type)

    # ========== 广播状态统一数据源（树状态列 + 大屏同源） ==========
    def _set_train_state(self, no, state, keep=False):
        """更新车次状态：树状态列 + 大屏状态同步（统一状态源）
        keep=True：状态为持续性状态（晚点/停运），播放结束/停止不恢复"""
        try:
            no = str(no)
            prev = "待检票"
            for c in self.bc_train_tree.get_children():
                vals = list(self.bc_train_tree.item(c)["values"])
                if vals and str(vals[0]) == no:
                    if len(vals) > 7:
                        prev = vals[7]
                        vals[7] = state
                        self.bc_train_tree.item(c, values=tuple(vals))
                    break
            # keep=True：prev 记为新状态，恢复时恢复成同值 → 不跳变
            self._train_state_prev[no] = state if keep else prev
            self._train_states[no] = state
            # 大屏同源刷新（行已建立时立即生效；未建立时进入大屏自动重建）
            if getattr(self, "screen_rows", None) and self.screen_rows:
                self._update_screen_statuses(getattr(self, "_screen_smin", 5))
        except Exception:
            pass

    def _restore_train_state(self, no):
        """播放结束/停止后恢复车次状态"""
        try:
            if not no:
                return
            no = str(no)
            prev = self._train_state_prev.pop(no, "待检票")
            self._train_states.pop(no, None)
            for c in self.bc_train_tree.get_children():
                vals = list(self.bc_train_tree.item(c)["values"])
                if vals and str(vals[0]) == no:
                    if len(vals) > 7:
                        vals[7] = prev
                        self.bc_train_tree.item(c, values=tuple(vals))
                    break
            if getattr(self, "screen_rows", None) and self.screen_rows:
                self._update_screen_statuses(getattr(self, "_screen_smin", 5))
        except Exception:
            pass

    def stop_all_audio(self):
        """停止所有音频（置停止标志：各播放线程自行 close，立即生效）
        注意：winmm MCI 非线程安全，主线程调 stop/close 对子线程播放无效且引入竞争，
        因此停止只置标志，由拥有 MCI 句柄的播放线程自己退出并 close。"""
        self._stop_flag = True
        self.set_status("已停止播放")
        self.bc_status_dot.configure(text="● 就绪", text_color="#4a4")
        # 停止后恢复被播放车次的状态（反向同步）
        self._restore_train_state(getattr(self, "_active_bcast_train", None))

    def manual_broadcast(self):
        """手动广播（与手动播放一致）"""
        self.play_manual()

    def create_train_panel(self):
        """车辆管理面板（车次管理：完整编辑，9 列与主界面同源）"""
        panel = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        panel.grid_columnconfigure(0, weight=3)
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_rowconfigure(0, weight=1)

        # 左侧：车次列表（9 列与主界面一致）
        list_frame = ctk.CTkFrame(panel, fg_color=DS["panel"], corner_radius=10)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(list_frame, text="🚆 车次列表（9 列与主界面同源，选中自动回填）",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=DS["accent"]).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 5))

        columns = ("车次", "类型", "发站", "到站", "开点", "检票口", "站台", "状态", "到点")
        _tst = ttk.Style()
        try:
            _tst.theme_use("clam")
        except Exception:
            pass
        _tst.configure("Train.Treeview", font=(DS["font"], 11), rowheight=30,
                       background=DS["row1"], fieldbackground=DS["row1"],
                       foreground=DS["text"], borderwidth=0)
        _tst.map("Train.Treeview",
                 background=[("selected", DS["row_sel"])],
                 foreground=[("selected", "#ffffff")])
        self.train_tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                       height=15, style="Train.Treeview")
        _col_w = {"车次": 82, "类型": 56, "发站": 80, "到站": 90, "开点": 66,
                  "检票口": 72, "站台": 50, "状态": 70, "到点": 70}
        for col in columns:
            self.train_tree.heading(col, text=col)
            self.train_tree.column(col, width=_col_w[col], anchor="center")
        self.train_tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.train_tree.bind("<<TreeviewSelect>>", self.on_train_tree_select)

        # 加载车次（zebra 在 load_trains 内部调用）
        self.load_trains()

        # 右侧：详情面板（完整可编辑字段）
        detail_frame = ctk.CTkFrame(panel, fg_color=DS["panel"], corner_radius=10)
        detail_frame.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        detail_frame.grid_columnconfigure(0, weight=1)
        detail_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(detail_frame, text="车次详情（选中列表项自动填充，改完点更新）",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color=DS["accent"])\
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 5))

        # 表单（2 列紧凑布局）
        self.train_fields = {}
        fields = [
            ("车次号", "num"),
            ("类型", "typ"),
            ("始发站(起点)", "dep"),
            ("终点站", "arr"),
            ("开点(发车时间)", "dept"),
            ("到点(到达时间)", "arr_time"),
            ("检票口", "ckpt"),
            ("站台", "plat"),
        ]
        for i, (label, key) in enumerate(fields):
            r, c = 1 + i // 2, i % 2
            ctk.CTkLabel(detail_frame, text=label + ":", font=ctk.CTkFont(size=11),
                         text_color=DS["text_dim"]).grid(row=r, column=c, sticky="w", padx=(12, 2), pady=(6, 0))
            entry = ctk.CTkEntry(detail_frame, font=ctk.CTkFont(size=12), height=30)
            entry.grid(row=r + 1, column=c, sticky="ew", padx=(12, 8), pady=(0, 4))
            self.train_fields[key] = entry

        # 状态下拉
        ctk.CTkLabel(detail_frame, text="状态:", font=ctk.CTkFont(size=11),
                     text_color=DS["text_dim"]).grid(row=6, column=0, sticky="w", padx=(12, 2), pady=(6, 0))
        self.status_cmb = ctk.CTkComboBox(detail_frame, values=["待检票", "计划中", "检票中", "晚点", "停运", "已发车", "已到达", "取消"],
                                          font=ctk.CTkFont(size=12), width=130)
        self.status_cmb.set("待检票")
        self.status_cmb.grid(row=7, column=0, sticky="ew", padx=(12, 8), pady=(0, 4))

        # 按钮
        btn_row1 = ctk.CTkFrame(detail_frame, fg_color="transparent")
        btn_row1.grid(row=8, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 5))
        ctk.CTkButton(btn_row1, text="添加", font=ctk.CTkFont(size=12), fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                      command=self.add_train).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(btn_row1, text="更新", font=ctk.CTkFont(size=12), fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                      command=self.update_train).pack(side="left", fill="x", expand=True, padx=(5, 0))

        btn_row2 = ctk.CTkFrame(detail_frame, fg_color="transparent")
        btn_row2.grid(row=9, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))
        ctk.CTkButton(btn_row2, text="移除", font=ctk.CTkFont(size=12), fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                      command=self.remove_train).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(btn_row2, text="刷新", font=ctk.CTkFont(size=12), fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      command=self.load_trains).pack(side="left", fill="x", expand=True, padx=(5, 0))

        return panel

    def on_train_tree_select(self, _evt=None):
        """车辆管理：选中列表项自动回填表单"""
        sel = self.train_tree.selection()
        if not sel:
            return
        vals = list(self.train_tree.item(sel[0])["values"])
        if len(vals) < 9:
            vals = vals + [""] * (9 - len(vals))
        self.train_fields["num"].delete(0, "end")
        self.train_fields["num"].insert(0, str(vals[0]))
        self.train_fields["typ"].delete(0, "end")
        self.train_fields["typ"].insert(0, str(vals[1]))
        self.train_fields["dep"].delete(0, "end")
        self.train_fields["dep"].insert(0, str(vals[2]))
        self.train_fields["arr"].delete(0, "end")
        self.train_fields["arr"].insert(0, str(vals[3]))
        self.train_fields["dept"].delete(0, "end")
        self.train_fields["dept"].insert(0, str(vals[4]))
        self.train_fields["ckpt"].delete(0, "end")
        self.train_fields["ckpt"].insert(0, str(vals[5]))
        self.train_fields["plat"].delete(0, "end")
        self.train_fields["plat"].insert(0, str(vals[6]))
        self.status_cmb.set(str(vals[7]))
        self.train_fields["arr_time"].delete(0, "end")
        self.train_fields["arr_time"].insert(0, str(vals[8]))

    def create_footer(self):
        """底部状态栏"""
        footer = ctk.CTkFrame(self, height=35, corner_radius=0, fg_color=DS["panel2"])
        footer.grid(row=2, column=0, columnspan=2, sticky="nsew")
        footer.grid_propagate(False)

        self.status_label = ctk.CTkLabel(footer, text="正在启动...", font=ctk.CTkFont(size=12), text_color=DS["text_dim"])
        self.status_label.pack(side="left", padx=15)

        # 右侧按钮
        btn_frame = ctk.CTkFrame(footer, fg_color="transparent")
        btn_frame.pack(side="right", padx=15)
        ctk.CTkButton(btn_frame, text="关闭系统", font=ctk.CTkFont(size=12), width=80,
                      fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                      command=self.quit_app).pack(side="left", padx=5)

    # ========== 导航切换 ==========
    def show_broadcast(self):
        self.set_active_nav(0)
        self.broadcast_panel.grid()
        self.train_panel.grid_remove()
        self.screen_panel.grid_remove()
        self.system_panel.grid_remove()
        self.bcast_set_panel.grid_remove()

    def show_train(self):
        self.set_active_nav(1)
        self.broadcast_panel.grid_remove()
        self.train_panel.grid()
        self.screen_panel.grid_remove()
        self.system_panel.grid_remove()
        self.bcast_set_panel.grid_remove()
        self.refresh_sched_train_list()

    def show_screen(self):
        self.set_active_nav(2)
        self.broadcast_panel.grid_remove()
        self.train_panel.grid_remove()
        self.screen_panel.grid()
        self.system_panel.grid_remove()
        self.bcast_set_panel.grid_remove()
        # 进入大屏即刷新数据并启动时钟
        self.refresh_screen()
        self._screen_tick()

    def show_system(self):
        self.set_active_nav(3)
        self.broadcast_panel.grid_remove()
        self.train_panel.grid_remove()
        self.screen_panel.grid_remove()
        self.system_panel.grid()
        self.bcast_set_panel.grid_remove()

    def show_bcast_set(self):
        self.set_active_nav(4)
        self.broadcast_panel.grid_remove()
        self.train_panel.grid_remove()
        self.screen_panel.grid_remove()
        self.system_panel.grid_remove()
        self.bcast_set_panel.grid()

    # ========== 功能函数 ==========
    def refresh_screen(self):
        """刷新大屏列车表（与主界面车次同源）+ 欢迎横幅 + 彩色状态"""
        try:
            # 站名 / 停检提前量（读取系统设置输入框，立即生效）
            name = ""
            if hasattr(self, "station_entry"):
                name = self.station_entry.get().strip()
            name = name or "丽水站"
            smin = 5
            if hasattr(self, "stop_min_entry"):
                try:
                    smin = max(1, int(float(self.stop_min_entry.get().strip() or "5")))
                except Exception:
                    smin = 5
            self._screen_smin = smin
            if hasattr(self, "screen_welcome") and self.screen_welcome.winfo_exists():
                self.screen_welcome.configure(text=f"{name} 欢迎您")
            # 清空旧行（表头 + 数据），重建（只销毁自建控件，避免破坏滚动组件）
            for w in self._screen_widgets:
                try:
                    if w.winfo_exists():
                        w.destroy()
                except Exception:
                    pass
            self._screen_widgets.clear()
            self.screen_rows.clear()
            rows = []
            for c in self.bc_train_tree.get_children():
                rows.append(list(self.bc_train_tree.item(c)["values"]))
            self._build_screen_header(self.screen_container)
            for i, r in enumerate(rows):
                self._add_screen_row(self.screen_container, i, r)
            self._update_screen_statuses(smin)
            if hasattr(self, "screen_status"):
                self.screen_status.configure(text=f"● 大屏运行中 · 共 {len(rows)} 趟列车", text_color="#6be26b")
            self.set_status(f"车站大屏已刷新（{len(rows)} 趟列车）")
        except Exception as e:
            self.set_status(f"大屏刷新失败：{e}")

    def _screen_tick(self):
        """大屏时钟每秒刷新；状态列每 5 秒按开车时间自动更新"""
        try:
            now = time.strftime("%H:%M:%S")
            if hasattr(self, "screen_clock") and self.screen_clock.winfo_exists():
                self.screen_clock.configure(text=now)
                self.screen_date.configure(text=time.strftime("%Y年%m月%d日  %A"))
            # 每 5 秒刷新一次状态列（按开车时间自动变状态）
            if int(time.time()) % 5 == 0 and getattr(self, "screen_rows", None):
                self._update_screen_statuses(getattr(self, "_screen_smin", 5))
        except Exception:
            pass
        self.after(1000, self._screen_tick)

    def refresh_sched_train_list(self):
        """刷新定时任务车次下拉（从主界面车次列表）"""
        try:
            nos = []
            for c in self.bc_train_tree.get_children():
                vals = self.bc_train_tree.item(c)["values"]
                if vals and str(vals[0]).strip() and str(vals[0]) not in nos:
                    nos.append(str(vals[0]))
            if hasattr(self, "sched_train_cmb"):
                self.sched_train_cmb.configure(values=nos)
                cur = self.sched_train_cmb.get()
                if cur and cur not in nos:
                    self.sched_train_cmb.set("")
        except Exception:
            pass

    def _sched_save_to_file(self):
        """把定时任务写入配置文件"""
        try:
            cfg_path = self.get_config_path()
            self._backup_cfg(cfg_path)
            cfg = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, encoding="utf-8") as f:
                    cfg = json.load(f)
            cfg["schedule"] = [dict(s) for s in getattr(self, "bc_schedule", [])]
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def refresh_sched_list_ui(self):
        """刷新定时任务列表 UI"""
        if not hasattr(self, "sched_tree"):
            return
        for c in self.sched_tree.get_children():
            self.sched_tree.delete(c)
        for s in getattr(self, "bc_schedule", []):
            st = "✅ 启用" if s.get("enabled") else "⏸ 停用"
            self.sched_tree.insert("", "end", values=(s.get("time", ""), s.get("type", ""),
                                                       s.get("train", "") or "（默认）", st))
        zebra(self.sched_tree)

    def add_schedule(self):
        """添加定时任务"""
        tstr = self.sched_time_entry.get().strip()
        if not tstr:
            self.set_status("请先输入时间（HH:MM）")
            return
        if len(tstr.split(":")) != 2:
            self.set_status("时间格式错误：应为 HH:MM，如 08:30")
            return
        try:
            hh, mm = tstr.split(":")
            if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
                raise ValueError
        except ValueError:
            self.set_status("时间格式错误：应为 HH:MM，如 08:30")
            return
        tstr = f"{int(hh):02d}:{int(mm):02d}"
        btype = self.sched_type_cmb.get() or "检票预告"
        train = self.sched_train_cmb.get().strip()
        if not hasattr(self, "bc_schedule"):
            self.bc_schedule = []
        self.bc_schedule.append({"time": tstr, "type": btype, "train": train, "enabled": True})
        self.refresh_sched_list_ui()
        ok = self._sched_save_to_file()
        self.set_status(f"已添加定时广播：{tstr} {btype} {train or '默认车次'}" + ("（已保存）" if ok else "（保存失败）"))
        self.sched_time_entry.delete(0, "end")

    def del_schedule(self):
        """删除选中定时任务"""
        sel = self.sched_tree.selection()
        if not sel:
            self.set_status("请先选中要删除的定时任务")
            return
        if not messagebox.askyesno("删除定时任务", "确定删除选中的定时任务吗？"):
            return
        idx = self.sched_tree.index(sel[0])
        self.bc_schedule.pop(idx)
        self.refresh_sched_list_ui()
        ok = self._sched_save_to_file()
        self.set_status(f"已删除定时任务（{'已保存' if ok else '保存失败'}）")

    def toggle_schedule(self, event=None):
        """启用/停用选中定时任务（双击列表也可）"""
        sel = self.sched_tree.selection()
        if not sel and event is not None:
            iid = self.sched_tree.identify_row(event.y)
            if iid:
                sel = (iid,)
        if not sel:
            self.set_status("请先选中定时任务（双击列表也可切换）")
            return
        idx = self.sched_tree.index(sel[0])
        self.bc_schedule[idx]["enabled"] = not self.bc_schedule[idx].get("enabled", True)
        self.refresh_sched_list_ui()
        # 重建后重新选中该行，方便连续切换
        children = self.sched_tree.get_children()
        if idx < len(children):
            self.sched_tree.selection_set(children[idx])
        ok = self._sched_save_to_file()
        st = "已启用" if self.bc_schedule[idx]["enabled"] else "已停用"
        self.set_status(f"定时任务{st}（{'已保存' if ok else '保存失败'}）")

    def clear_schedule(self):
        """清空全部定时任务"""
        if not getattr(self, "bc_schedule", []):
            self.set_status("当前没有定时任务")
            return
        if not messagebox.askyesno("清空定时任务", "确定清空全部定时任务吗？"):
            return
        self.bc_schedule = []
        self.refresh_sched_list_ui()
        ok = self._sched_save_to_file()
        self.set_status(f"已清空全部定时任务（{'已保存' if ok else '保存失败'}）")

    def _schedule_tick(self):
        """每秒轮询：到点且已启用 → 播放对应广播（当天同一任务只触发一次）"""
        try:
            now = time.strftime("%H:%M")
            day = time.strftime("%Y-%m-%d")
            last = getattr(self, "_last_sched", {})
            for s in getattr(self, "bc_schedule", []):
                if not s.get("enabled"):
                    continue
                if s.get("time") != now:
                    continue
                key = day + "|" + s["time"] + "|" + str(s.get("train", ""))
                if last.get(key):
                    continue
                self._last_sched = {key: True}
                self.schedule_play(s.get("type", "检票预告"), s.get("train", ""))
        except Exception:
            pass
        self.after(1000, self._schedule_tick)

    def schedule_play(self, btype, train_no):
        """定时触发：按指定车次播放指定类型广播"""
        train_no = (train_no or "").strip()
        found = False
        try:
            for c in self.bc_train_tree.get_children():
                vals = self.bc_train_tree.item(c)["values"]
                if str(vals[0]) == train_no:
                    self.current_train = {
                        "no": str(vals[0]),
                        "from": vals[2] if len(vals) > 2 else "",
                        "to": vals[3] if len(vals) > 3 else "",
                        "gate": vals[5] if len(vals) > 5 else "A1",
                        "platform": vals[6] if len(vals) > 6 else "",
                    }
                    found = True
                    break
        except Exception:
            pass
        if not found:
            self.current_train = {"no": train_no or "G1234", "from": "杭州东", "to": "宁波",
                                  "gate": "A1", "platform": "3"}
        self.set_status(f"⏰ 定时广播触发：{btype} {self.current_train['no']}")
        try:
            if hasattr(self, "bc_status_dot"):
                self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        except Exception:
            pass
        audio_list = self.build_audio_list_from_steps(btype)
        if audio_list:
            self.play_concat_audio(audio_list)
        else:
            self.set_status(f"定时广播 {btype} 没有可播放的音频")
            try:
                self.bc_status_dot.configure(text="● 系统就绪", text_color="#4d4")
            except Exception:
                pass

    def update_clock(self):
        now = time.strftime("%H:%M:%S")
        self.clock_label.configure(text=now)
        self.after(1000, self.update_clock)

    def connect_tcp(self):
        """连接后端 TCP"""
        try:
            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.settimeout(3)
            self.tcp_sock.connect((TCP_HOST, TCP_PORT))
            self.set_status("系统启动成功")
        except Exception as e:
            self.tcp_sock = None
            self.set_status("系统启动成功（未连接后端）")
        # 启动完成后播放音乐
        self.after(500, self.startup_play_music)

    def startup_play_music(self):
        """启动完成后播放启动音频（从广播设置读取，无配置用默认 tsy/tsy2.mp3，播完自动关闭）"""
        import threading
        import ctypes
        import time as _time

        # 读取广播设置里的启动音频
        audio_cfg = ""
        if hasattr(self, "startup_audio_entry"):
            audio_cfg = self.startup_audio_entry.get().strip()
        if not audio_cfg:
            audio_cfg = "tsy/tsy2.mp3"
        path = self.resolve_audio_path(audio_cfg)
        if path and not path.startswith(("http://", "https://")) and os.path.exists(path):
            def _play_and_close():
                try:
                    alias = "startup_music"
                    mci = ctypes.windll.winmm
                    mci.mciSendStringW(f'close {alias}', None, 0, None)
                    ret = mci.mciSendStringW(f'open "{path}" alias {alias}', None, 0, None)
                    if ret == 0:
                        mci.mciSendStringW(f"play {alias}", None, 0, None)
                        # 等播完自动关闭，避免占用音频设备
                        t0 = _time.time()
                        while _time.time() - t0 < 120:
                            # 停止标志：主界面点停止可中断启动音频
                            if getattr(self, "_stop_flag", False):
                                break
                            status = ctypes.create_unicode_buffer(255)
                            mci.mciSendStringW(f"status {alias} mode", status, 255, None)
                            if status.value != "playing":
                                break
                            _time.sleep(0.05)
                        mci.mciSendStringW(f'close {alias}', None, 0, None)
                except Exception:
                    pass

            self.set_status("系统启动成功，已播放启动音频")
            threading.Thread(target=_play_and_close, daemon=True).start()
        else:
            self.set_status("系统启动成功（启动音频未配置或文件不存在）")

    def show_broadcast_with_startup(self):
        """进入广播主界面（播放启动音频，5 秒内不重复）"""
        self.show_broadcast()
        now = time.time()
        last = getattr(self, "_last_startup_audio_ts", 0)
        if now - last > 5:
            self._last_startup_audio_ts = now
            self.startup_play_music()

    def send_request(self, cmd, params=None):
        """发送 TCP 请求"""
        if not self.tcp_sock:
            self.set_status("未连接")
            return None
        try:
            req = {"cmd": cmd}
            if params:
                req.update(params)
            data = json.dumps(req).encode("utf-8")
            self.tcp_sock.sendall(data)
            # 接收响应
            self.tcp_sock.settimeout(3)
            resp = self.tcp_sock.recv(4096)
            return json.loads(resp.decode("gbk"))
        except Exception as e:
            self.set_status(f"请求失败: {e}")
            return None

    def set_status(self, text):
        self.status_label.configure(text=text)

    def quick_broadcast(self, category):
        """快捷广播（映射到现有音频库，找不到则明确提示）"""
        self.set_status(f"快捷广播: {category}")
        audio_map = {
            "候车室广播": "media3/其他/各位旅客请注意.mp3",
            "检票口广播": "media3/其他/号检票口检票进站。.mp3",
            "晚点广播": "media3/紧急广播/列车晚点.mp3",
            "停止检票": "media3/紧急广播/停止检票.mp3",
        }
        audio_file = audio_map.get(category)
        if audio_file:
            self.play_audio_file(audio_file)
        else:
            self.set_status(f"快捷广播暂未配置音频：{category}")

    def play_audio_file(self, filename):
        """播放指定音频文件（子线程 MCI + 停止标志；中文路径用 GBK ANSI 版 MCI）"""
        import threading
        import ctypes
        import os
        import time
        import tempfile
        import shutil

        audio_path = os.path.join(AUDIO_DIR, filename)
        audio_path = os.path.abspath(audio_path)

        if not os.path.exists(audio_path):
            self.set_status(f"文件不存在: {filename}")
            return
        if getattr(self, "_playing", False):
            self.set_status("正在播放中，请稍候")
            return
        self._playing = True
        self._stop_flag = False

        def safe_after(ms, func):
            try:
                self.after(ms, func)
            except Exception:
                pass

        def do_play():
            try:
                mci = ctypes.windll.winmm
                alias = "bc_aud"

                # 关闭之前的
                mci.mciSendStringA(("close " + alias).encode("gbk"), None, 0, None)

                # 用 GBK 编码的路径打开（ANSI 版 MCI）
                open_cmd = 'open "%s" alias %s' % (audio_path, alias)
                ret = mci.mciSendStringA(open_cmd.encode("gbk"), None, 0, None)
                tmp_used = False

                if ret != 0:
                    # 失败了试试复制到临时目录
                    tmp_file = os.path.join(tempfile.gettempdir(), "bc_tmp.mp3")
                    try:
                        shutil.copy2(audio_path, tmp_file)
                        mci.mciSendStringW("close " + alias, None, 0, None)
                        ret = mci.mciSendStringW('open "%s" alias %s' % (tmp_file, alias), None, 0, None)
                        tmp_used = True
                    except Exception:
                        ret = 1

                if ret == 0:
                    mci.mciSendStringA(("play " + alias).encode("gbk"), None, 0, None)
                    safe_after(0, lambda: self.set_status(("播放(临时): " if tmp_used else "播放: ") + filename))
                    t0 = time.time()
                    while time.time() - t0 < 600:
                        # 停止标志：由播放线程自己退出并 close（停止立即生效）
                        if getattr(self, "_stop_flag", False):
                            break
                        status = ctypes.create_unicode_buffer(255)
                        mci.mciSendStringA(("status %s mode" % alias).encode("gbk"), status, 255, None)
                        if status.value != "playing":
                            break
                        time.sleep(0.05)
                    mci.mciSendStringW("close " + alias, None, 0, None)
                else:
                    safe_after(0, lambda: self.set_status("播放失败: " + filename))
            except Exception as e:
                safe_after(0, lambda e=e: self.set_status("播放错误: %s" % e))
            finally:
                self._playing = False

        threading.Thread(target=do_play, daemon=True).start()

    def play_concat_audio(self, audio_list):
        """拼接多个音频片段：解码→裁静音→统一采样率→合成一个完整音频再播放（绝对无缝）"""
        import threading
        import os
        import ctypes
        import tempfile
        import time

        root = AUDIO_DIR

        # 防并发：正在播放时忽略新请求
        if getattr(self, "_playing", False):
            self.set_status("正在播放中，请稍候")
            return
        self._playing = True
        self._stop_flag = False

        # ===== 主线程读取 Tkinter 控件快照（后台线程禁止访问控件，否则 RuntimeError）=====
        cfg_start_sound = self.start_sound_btn.cget("text") if hasattr(self, "start_sound_btn") else ""
        cfg_end_sound = self.end_sound_btn.cget("text") if hasattr(self, "end_sound_btn") else ""
        if cfg_end_sound == "无（点击选择）":
            cfg_end_sound = ""
        cfg_main_audio = self.main_audio_entry.get().strip() if hasattr(self, "main_audio_entry") else ""
        try:
            cfg_speed = float(self.speed_slider.get()) if hasattr(self, "speed_slider") else 1.0
        except Exception:
            cfg_speed = 1.0
        try:
            cfg_var_speed = float(self.var_speed_slider.get()) if hasattr(self, "var_speed_slider") else 1.0
        except Exception:
            cfg_var_speed = 1.0

        def safe_after(ms, func):
            try:
                self.after(ms, func)
            except Exception:
                pass

        def find_audio(subdir, filename):
            """按类型查找音频文件（增强版：补零/去字母/模糊匹配）"""
            return self.find_audio_file(subdir, filename)

        def trim_silence(data, sr, pad_ms=25):
            """裁剪首尾静音，让片段衔接紧凑"""
            if data is None or len(data) == 0:
                return data
            import numpy as np
            # 多声道统一转单声道
            if data.ndim > 1:
                data = data.mean(axis=1)
            absd = np.abs(data)
            peak = absd.max()
            if peak < 1e-6:
                return data
            threshold = max(peak * 0.02, 0.003)
            idx = np.where(absd > threshold)[0]
            if len(idx) == 0:
                return data
            start = max(0, idx[0] - int(sr * pad_ms / 1000))
            end = min(len(data), idx[-1] + int(sr * pad_ms / 1000))
            return data[start:end]

        def resample(data, src_sr, dst_sr=44100):
            if src_sr == dst_sr:
                return data
            import numpy as np
            # 多声道统一转单声道
            if data.ndim > 1:
                data = data.mean(axis=1)
            new_len = int(round(len(data) * dst_sr / src_sr))
            if new_len <= 1:
                return data
            x_old = np.linspace(0.0, 1.0, len(data), endpoint=False)
            x_new = np.linspace(0.0, 1.0, new_len, endpoint=False)
            return np.interp(x_new, x_old, data)

        def concat_and_play():
            import numpy as np
            import soundfile as sf

            def resample_len(arr, target_len):
                """把数组重采样到指定长度（变速核心）"""
                n = len(arr)
                if target_len <= 1 or target_len == n:
                    return arr
                x_old = np.linspace(0.0, 1.0, n, endpoint=False)
                x_new = np.linspace(0.0, 1.0, target_len, endpoint=False)
                return np.interp(x_new, x_old, arr)

            chunks = []
            missing = []

            # 使用主线程快照的配置（后台线程禁止访问 Tkinter 控件）
            if getattr(self, "_stop_flag", False):
                self._playing = False
                return
            start_sound = cfg_start_sound
            end_sound = cfg_end_sound
            main_audio = cfg_main_audio
            if main_audio:
                start_sound = main_audio

            # 开始音（默认提示音 tsy1）
            start_path = None
            if start_sound:
                sp = self.resolve_audio_path(start_sound)
                if sp and not sp.startswith(("http://", "https://")) and os.path.exists(sp):
                    start_path = sp
                else:
                    # 兼容 "提示音/tsy1.mp3" 等旧写法 → 自动在 tsy 目录找
                    s2 = start_sound.replace("\\", "/")
                    if "/" in s2:
                        sub, fn = s2.split("/", 1)
                        if sub in ("提示音", "tsy", "media2/提示音"):
                            start_path = find_audio("提示音", fn.replace(".mp3", ""))
            if not start_path:
                start_path = find_audio("提示音", "tsy1")
            if not start_path:
                start_path = find_audio("提示音", "广播开始音1")

            if start_path:
                try:
                    data, sr = sf.read(start_path)
                    data = trim_silence(data, sr)
                    if len(data) > 0:
                        # 开始音（广播提示音）保持原速，不随播放速度变速
                        chunks.append((data, sr))
                except Exception:
                    pass

            # 解码正文片段（每段：变量速度/本步速度 × 整体速度，变速不变调）
            for seg in audio_list:
                if getattr(self, "_stop_flag", False):
                    break
                subdir, filename = seg[0], seg[1]
                seg_speed = float(seg[2]) if len(seg) > 2 else 1.0
                seg_is_var = len(seg) > 3 and bool(seg[3])
                # 变量音频用"变量播放速度"，主语音用该步骤自己的速度；整体速度作为乘数
                eff_speed = cfg_speed * (cfg_var_speed if seg_is_var else seg_speed)
                if subdir == "__path__":
                    mp3_path = filename  # 完整路径直接播放
                else:
                    mp3_path = find_audio(subdir, filename)
                if not mp3_path:
                    missing.append(f"{subdir}/{filename}")
                    continue
                try:
                    data, sr = sf.read(mp3_path)
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    data = trim_silence(data, sr)
                    if len(data) > 0:
                        if abs(eff_speed - 1.0) > 0.001:
                            data = wsola_stretch(data, eff_speed, sr)
                        chunks.append((data, sr))
                except Exception as e:
                    missing.append(f"{subdir}/{filename}")

            # 结束音（界面设置的）
            if end_sound:
                ep = self.resolve_audio_path(end_sound)
                if ep and not ep.startswith(("http://", "https://")) and os.path.exists(ep):
                    try:
                        data, sr = sf.read(ep)
                        data = trim_silence(data, sr)
                        if len(data) > 0:
                            # 结束音保持原速，不随播放速度变速
                            chunks.append((data, sr))
                    except Exception:
                        pass
                else:
                    e2 = end_sound.replace("\\", "/")
                    if "/" in e2:
                        sub, fn = e2.split("/", 1)
                        if sub in ("提示音", "tsy", "media2/提示音"):
                            ep2 = find_audio("提示音", fn.replace(".mp3", ""))
                            if ep2:
                                try:
                                    data, sr = sf.read(ep2)
                                    data = trim_silence(data, sr)
                                    if len(data) > 0:
                                        # 结束音保持原速，不随播放速度变速
                                        chunks.append((data, sr))
                                except Exception:
                                    pass

            if not chunks:
                safe_after(0, lambda: self.set_status("没有找到音频文件"))
                self._playing = False
                return

            if missing:
                safe_after(0, lambda m=missing: self.set_status(f"缺音频: {'、'.join(m)}"))

            # 统一采样率；片段间交叉淡化拼接（防"叭叭叭"爆音）
            if getattr(self, "_stop_flag", False):
                safe_after(0, lambda: self.bc_status_dot.configure(text="● 系统就绪", text_color="#4d4"))
                safe_after(0, lambda: self._restore_train_state(getattr(self, "_active_bcast_train", None)))
                self._playing = False
                return
            fade_len = int(44100 * 0.025)
            parts = []
            for i, (data, sr) in enumerate(chunks):
                d = resample(data, sr, 44100)
                if len(d) > fade_len * 2:
                    # 首段开头短淡入（防止播放开始瞬间爆音）
                    if i == 0:
                        rampin = np.linspace(0.0, 1.0, fade_len)
                        d[:fade_len] = d[:fade_len] * rampin
                    # 非最后段：结尾短淡出，与下一段交叉（消除拼接处爆音）
                    if i < len(chunks) - 1:
                        rampout = np.linspace(1.0, 0.0, fade_len)
                        d[-fade_len:] = d[-fade_len:] * rampout
                parts.append(d)
            if len(parts) > 1:
                merged = parts[0]
                for nxt in parts[1:]:
                    if len(merged) >= fade_len and len(nxt) >= fade_len:
                        rampo = np.linspace(1.0, 0.0, fade_len)
                        rampi = np.linspace(0.0, 1.0, fade_len)
                        merged[-fade_len:] = merged[-fade_len:] * rampo + nxt[:fade_len] * rampi
                        merged = np.concatenate([merged, nxt[fade_len:]])
                    else:
                        merged = np.concatenate([merged, nxt])
            else:
                merged = parts[0] if parts else np.zeros(0)

            # 每段已在读取时按各自语速变速，此处不再整体变速
            # 末尾不整体淡出（自然播完，保持原音质）

            # 写入临时 wav（纯英文路径）
            out_wav = os.path.join(tempfile.gettempdir(), "bc_merged.wav")
            sf.write(out_wav, merged, 44100)

            # MCI 播放一个完整文件（绝对无缝）
            mci = ctypes.windll.winmm
            alias = "bc_merged"
            # 播放前先释放其他占用（如启动音频）
            mci.mciSendStringW("close startup_music", None, 0, None)
            mci.mciSendStringW(f'close {alias}', None, 0, None)
            ret = mci.mciSendStringW(f'open "{out_wav}" alias {alias}', None, 0, None)
            if ret == 0:
                mci.mciSendStringW(f"play {alias}", None, 0, None)
                # 超时保护：音频时长 + 20 秒，防卡死
                play_timeout = max(len(merged) / 44100.0 + 20.0, 30.0)
                t0 = time.time()
                while time.time() - t0 < play_timeout:
                    # 停止标志：由播放线程自己退出并 close（停止立即生效）
                    if getattr(self, "_stop_flag", False):
                        break
                    status = ctypes.create_unicode_buffer(255)
                    mci.mciSendStringW(f"status {alias} mode", status, 255, None)
                    if status.value != "playing":
                        break
                    time.sleep(0.05)
                mci.mciSendStringW(f'close {alias}', None, 0, None)

            safe_after(0, lambda: self.bc_status_dot.configure(text="● 系统就绪", text_color="#4d4"))
            safe_after(0, lambda: self._restore_train_state(getattr(self, "_active_bcast_train", None)))
            self._playing = False

        threading.Thread(target=concat_and_play, daemon=True).start()

    def send_broadcast(self):
        content = getattr(self, "bc_manual_entry", None)
        if not content:
            return
        text = content.get().strip()
        if not text:
            self.set_status("请输入广播内容")
            return
        # 语音合成功能已按需求移除，改为播放提示音并说明
        self.set_status(f"发送广播: {text}（语音合成已移除，请使用手动播放音频）")


    def play_audio(self):
        self.set_status("播放音频")

    def stop_audio(self):
        self.set_status("停止音频")

    def pause_audio(self):
        self.set_status("暂停音频")

    def resume_audio(self):
        self.set_status("恢复音频")

    def load_trains(self):
        """车辆管理面板：从主界面车次列表同步显示"""
        for item in self.train_tree.get_children():
            self.train_tree.delete(item)
        for c in self.bc_train_tree.get_children():
            vals = list(self.bc_train_tree.item(c)["values"])
            if len(vals) < 9:
                vals = vals + [""] * (9 - len(vals))
            # 9 列与主界面完全一致，支持到点/类型/检票口编辑
            self.train_tree.insert("", "end", values=tuple(vals[:9]))
        zebra(self.train_tree)

    def add_train(self):
        """车辆管理面板添加：弹出主界面添加对话框（数据同源）"""
        self.add_train_dialog()

    def update_train(self):
        """车辆管理面板更新：完整 9 列（车次/类型/发站/到站/开点/检票口/站台/状态/到点）并持久化"""
        sel = self.train_tree.selection()
        if not sel:
            self.set_status("请先选择要更新的车次")
            return
        no = self.train_fields["num"].get().strip()
        if not no:
            self.set_status("车次号不能为空")
            return
        row = (
            no,
            self.train_fields["typ"].get().strip() or "高铁",
            self.train_fields["dep"].get().strip(),
            self.train_fields["arr"].get().strip(),
            self.train_fields["dept"].get().strip(),
            self.train_fields["ckpt"].get().strip() or "A1",
            self.train_fields["plat"].get().strip(),
            self.status_cmb.get(),
            self.train_fields["arr_time"].get().strip() or "--:--",
        )
        self.train_tree.item(sel[0], values=row)
        self.sync_train_to_main()
        self.set_status(f"车次 {no} 已更新")

    def remove_train(self):
        """车辆管理面板移除：同步删除并持久化"""
        sel = self.train_tree.selection()
        if not sel:
            self.set_status("请先选择要移除的车次")
            return
        if not messagebox.askyesno("移除车次", "确定移除选中的车次吗？"):
            return
        no = self.train_tree.item(sel[0])["values"][0]
        # 同步删除主界面列表
        for c in self.bc_train_tree.get_children():
            if self.bc_train_tree.item(c)["values"][0] == no:
                self.bc_train_tree.delete(c)
                break
        zebra(self.bc_train_tree)
        self.save_trains_data()
        self.train_tree.delete(sel)
        self.set_status(f"已移除车次：{no}")

    def sync_train_to_main(self):
        """把车辆管理面板的 train_tree 同步到主界面 bc_train_tree 并持久化"""
        for c in self.bc_train_tree.get_children():
            self.bc_train_tree.delete(c)
        for c in self.train_tree.get_children():
            vals = list(self.train_tree.item(c)["values"])
            if len(vals) < 9:
                vals = vals + [""] * (9 - len(vals))
            self.bc_train_tree.insert("", "end", values=tuple(vals[:9]))
        zebra(self.bc_train_tree)
        self.save_trains_data()

    def logout(self):
        self.set_status("退出登录")
        self.destroy()

    def quit_app(self):
        self.set_status("关闭系统")
        self.quit()

if __name__ == "__main__":
    app = BroadcastApp(username="admin")
    app.mainloop()