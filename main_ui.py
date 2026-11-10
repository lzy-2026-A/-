# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import ttk, messagebox
import tkinter as tk
import time
import socket
import json
import os
import re
import sys
import threading

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
    "紧急-列车晚点·已知时间",
    "紧急-列车停运·天气原因", "紧急-列车停运·设备故障",
    "紧急-列车停运·线路施工", "紧急-列车停运·自然灾害",
    "紧急-列车停运·行车事故", "紧急-列车停运·列车超员",
    "紧急-列车停运（通用）",
    "紧急-变更站台", "紧急-旅客突发",
]
CHECKIN_TYPES = ("检票预告", "开始检票", "停止检票")

# 新功能晚点类型（配置列表里缺失时自动补齐，保证按钮/播放可用；未知时间已按需求移除）
NEW_LATE_TYPES = ("紧急-列车晚点·已知时间",)

# ===== 统一排序规则（车次列表 / 车站大屏 / 副屏 / 广播队列共用）=====
# 状态显示优先级：越靠前越需要旅客立即关注
STATUS_RANK = {
    "正在检票": 0, "检票中": 0,
    "停止检票": 1,
    "晚点": 2,
    "待检票": 3, "正在候车": 3, "计划中": 3,
    "停运": 4,
    "已发车": 5,
    "已到达": 6, "取消": 6,
}
# 这些状态由人工/业务操作决定，时间逻辑不得覆盖
MANUAL_STATUSES = {"正在检票", "检票中", "停止检票", "晚点", "停运",
                   "已发车", "已到达", "取消"}


def bcast_priority_label(btype):
    """队列优先级文字（数字越小越先播）"""
    p = bcast_priority(btype)
    label = {10: "停止检票", 20: "开始检票", 30: "检票预告",
             40: "晚点/停运/变更", 50: "普通"}.get(p, "普通")
    return f"{p} {label}"


def parse_hhmm(value):
    """HH:MM → 当天分钟数；非法/空值返回 None（排序时排到末尾）"""
    try:
        hh, mm = str(value).strip().split(":")
        h, m = int(hh), int(mm)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return None
        return h * 60 + m
    except Exception:
        return None


def train_no_key(no):
    """车次号自然排序键：G2 排在 G10 前面，避免字符串排序错位"""
    s = str(no or "").strip().upper()
    return tuple((0, int(p)) if p.isdigit() else (1, p)
                 for p in re.split(r"(\d+)", s) if p)


def effective_train_status(row, smin=5, now_min=None):
    """车次的有效显示状态：人工状态优先；待检票/计划中按开点时间自动推进。
    这样大屏既不会把人工设置的“晚点/停运”冲掉，也不会让所有车次永远停在“待检票”。"""
    st = ""
    try:
        st = str(row[7] if len(row) > 7 else "").strip()
    except Exception:
        st = ""
    if st in MANUAL_STATUSES:
        return st
    dep = parse_hhmm(row[4] if len(row) > 4 else "")
    if dep is None:
        return st or "计划中"
    if now_min is None:
        _now = time.localtime()
        now_min = _now.tm_hour * 60 + _now.tm_min
    try:
        lead = max(1, int(smin or 5))
    except Exception:
        lead = 5
    if now_min >= dep:
        return "停止检票"
    if now_min >= dep - lead:
        return "正在检票"
    return "正在候车"


def bcast_priority(btype):
    """广播队列优先级：数字越小越先播（紧急广播仍走抢占，不排队）"""
    t = str(btype or "")
    if "停止检票" in t:
        return 10
    if "开始检票" in t:
        return 20
    if "检票预告" in t:
        return 30
    if any(k in t for k in ("晚点", "停运", "变更站台", "突发")):
        return 40
    return 50


def bc_type_sort_key(name):
    """广播类型推荐顺序：内置类型按 DEFAULT_BC_TYPES 顺序，自定义类型稳定排在后面"""
    try:
        return DEFAULT_BC_TYPES.index(name)
    except ValueError:
        return len(DEFAULT_BC_TYPES)

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
    """给 Treeview 行加固定背景 tag；保留 st_ 开头的状态颜色 tag。
    不再按行号交替上色：排序/刷新导致行位置变化时，整表背景不会互换，从根源消除闪烁。"""
    for c in tree.get_children():
        try:
            keep = tuple(t for t in tree.item(c, "tags") if str(t).startswith("st_"))
        except Exception:
            keep = ()
        new_tags = ("row",) + keep
        try:
            if tuple(tree.item(c, "tags")) != new_tags:
                tree.item(c, tags=new_tags)
        except Exception:
            pass

# 数字字符 → 汉字（新语音包"单个字"目录用汉字文件名）
CN_DIGITS = {"0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
             "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"}

APP_TITLE = "旅客服务智能管理广播系统"
APP_VERSION = "V26.10.2"
_LOG_LOCK = threading.Lock()   # 广播日志读改写锁（播放线程/主线程可能同时写）

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
# 强化：显式宽字符类型 + 检查返回值 + 失败换备用 ID 重试 + 诊断日志
try:
    import ctypes
    _shell32 = ctypes.windll.shell32
    _shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
    _shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
    _APPID = "PassengerBroadcastSystem.2.0.20261002"
    _hr = _shell32.SetCurrentProcessExplicitAppUserModelID(_APPID)
    _log = os.path.join(get_project_root(), "_icon_debug.log")
    try:
        with open(_log, "a", encoding="utf-8") as _f:
            _f.write("[%s] AppUserModelID: %s -> HRESULT 0x%08X (%s)\n" % (
                __import__("time").strftime("%H:%M:%S"), _APPID,
                _hr & 0xFFFFFFFF, "成功" if _hr == 0 else "失败"))
    except Exception:
        pass
    if _hr != 0:
        # 备用 ID 重试（去掉版本号再试一次）
        _hr2 = _shell32.SetCurrentProcessExplicitAppUserModelID("PassengerBroadcastSystem")
        try:
            with open(_log, "a", encoding="utf-8") as _f:
                _f.write("[%s] 备用 ID 重试 -> HRESULT 0x%08X\n" % (
                    __import__("time").strftime("%H:%M:%S"), _hr2 & 0xFFFFFFFF))
        except Exception:
            pass
except Exception as _e:
    try:
        with open(os.path.join(get_project_root(), "_icon_debug.log"), "a", encoding="utf-8") as _f:
            _f.write("AppUserModelID 设置异常: %r\n" % (_e,))
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
        # 允许 TIME_WAIT 端口复用：程序退出后立即重启不误判"已在运行"
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except Exception:
        pass
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
        # 先隐藏窗口，避免 UI 构建期间显示空白"叉"窗口（构建完成后再显示）
        try:
            self.withdraw()
        except Exception:
            pass
        self.username = username
        self.title(APP_TITLE)
        # 启动时先给一个安全尺寸，UI 构建完成后按 DPI/工作区自动适配
        self.geometry("1100x700")
        # 应用图标（exe/任务栏/窗口统一）
        try:
            _ico = None
            for _cand in (os.path.join(get_project_root(), "ico", "CustomTkinter_icon_Windows.ico"),
                          os.path.join(getattr(sys, "_MEIPASS", ""), "ico", "CustomTkinter_icon_Windows.ico"),
                          os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                                       "ico", "CustomTkinter_icon_Windows.ico")):
                if _cand and os.path.exists(_cand):
                    _ico = _cand
                    break
            if _ico:
                self.iconbitmap(_ico)
        except Exception:
            pass
        # 拦截右上角关闭按钮
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        # 初始化 UI
        self.__init_body()

    def maximize_window(self):
        """进入主界面后像点右上角“最大化”一样铺满工作区（保留标题栏和任务栏）。

        用 Windows 原生 ShowWindow(SW_MAXIMIZE)，避免 Tk 的 zoomed 在
        125% DPI 下被 CustomTkinter 二次缩放导致窗口超出屏幕。
        """
        try:
            self.attributes("-fullscreen", False)
        except Exception:
            pass
        try:
            import ctypes
            hwnd = int(self.wm_frame(), 16)
            ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
            return
        except Exception:
            pass
        try:
            self.state("zoomed")
        except Exception:
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
        self._bcast_queue = []           # 广播播放队列（非紧急：按优先级 + 开点时间排序）
        self._queue_pending = False      # 后台播放线程完成标志（线程安全，主线程轮询消费）
        self._queue_ver = 0              # 队列版本号（入队/出队/排序/清空时 +1，用于界面同步刷新）
        self._queue_ver_shown = -1       # 界面已显示的版本号
        self._bcast_gap = 0              # 每条广播间隔秒数（队列播放时两条之间间隔，0=无间隔）
        self._screen_sort_mode = "time"  # 大屏/车次排序：time=按开点时间（默认稳定），status=按状态优先
        self._current_btype = ""         # 正在播放的广播类型（队列面板显示用）
        self._emergency_queue = None     # 紧急抢占待播内容
        self._emergency_btype = ""
        # 常驻轮询：后台线程播放完成 → 主线程自动续播队列（避免跨线程调用 after 失效）
        try:
            self.after(300, self._poll_bcast_queue)
        except Exception:
            pass
        self._screen_anim_rows = set()   # 大屏正在播放动画的行 key，防止动画叠加抖动

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

        # 标题（无图标，纯文字）
        title = ctk.CTkLabel(header, text=APP_TITLE, font=ctk.CTkFont(size=20, weight="bold"), text_color="#ffffff")
        title.pack(side="left", padx=20)

        # 右侧：时钟 + 用户
        self.clock_label = ctk.CTkLabel(header, text="00:00:00", font=ctk.CTkFont(size=16, family="Consolas"), text_color=DS["accent"])
        self.clock_label.pack(side="right", padx=20)

        user = ctk.CTkLabel(header, text=f"用户：{self.username}", font=ctk.CTkFont(size=14), text_color=DS["text_dim"])
        user.pack(side="right", padx=10)

    def create_sidebar(self):
        """左侧导航栏：自绘行样式，避免 CTkButton 边框/Emoji 在部分 DPI 下显示异常。"""
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=DS["panel2"])
        sidebar.grid(row=1, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="功能导航", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#5f7ba3", anchor="w").pack(fill="x", padx=24, pady=(18, 10))

        nav_items = [
            ("广播管理", self.show_broadcast),
            ("广播队列", self.show_queue),
            ("车辆管理", self.show_train),
            ("车站大屏", self.show_screen),
            ("系统设置", self.show_system),
            ("广播设置", self.show_bcast_set),
        ]

        self.nav_buttons = []
        self._nav_rows = []
        self._nav_bars = []
        self._nav_nums = []
        self._nav_labels = []

        for i, (text, cmd) in enumerate(nav_items):
            row = ctk.CTkFrame(sidebar, height=46, corner_radius=7,
                               fg_color="transparent", cursor="hand2")
            row.pack(fill="x", padx=12, pady=3)
            row.pack_propagate(False)

            bar = ctk.CTkFrame(row, width=3, corner_radius=2, fg_color="transparent")
            bar.pack(side="left", fill="y", padx=(0, 11), pady=8)

            num = ctk.CTkLabel(row, text=f"{i + 1:02d}", width=25,
                               font=ctk.CTkFont(size=10, family="Consolas"),
                               text_color="#4d6484", anchor="w")
            num.pack(side="left")

            lbl = ctk.CTkLabel(row, text=text, anchor="w",
                               font=ctk.CTkFont(size=14),
                               text_color=DS["text_dim"])
            lbl.pack(side="left", fill="x", expand=True)

            def _enter(_e, r=row, idx=i):
                if getattr(self, "_active_nav", 0) != idx:
                    r.configure(fg_color=DS["nav_hover"])

            def _leave(_e, r=row, idx=i):
                if getattr(self, "_active_nav", 0) != idx:
                    r.configure(fg_color="transparent")

            def _click(_e, c=cmd):
                c()

            for w in (row, bar, num, lbl):
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                w.bind("<Button-1>", _click)

            self.nav_buttons.append(row)
            self._nav_rows.append(row)
            self._nav_bars.append(bar)
            self._nav_nums.append(num)
            self._nav_labels.append(lbl)

        # 底部版本与连接状态（固定贴底，避免窗口高度变化时跟着导航跑）
        side_foot = ctk.CTkFrame(sidebar, fg_color="transparent")
        side_foot.pack(side="bottom", fill="x", padx=22, pady=(8, 16))
        self.sidebar_status = ctk.CTkLabel(side_foot, text="●  本地调度模式",
                                           font=ctk.CTkFont(size=10),
                                           text_color="#6be26b", anchor="w")
        self.sidebar_status.pack(fill="x")
        ctk.CTkLabel(side_foot, text=f"{APP_VERSION}  ·  SCNet",
                     font=ctk.CTkFont(size=9), text_color="#40577a",
                     anchor="w").pack(fill="x", pady=(4, 0))

        # 默认选中第一个
        self.set_active_nav(0)

    def set_active_nav(self, index):
        """设置选中的导航：背景块 + 左侧强调条，不使用按钮边框。"""
        self._active_nav = index
        for i in range(len(getattr(self, "_nav_rows", []))):
            active = (i == index)
            try:
                self._nav_rows[i].configure(fg_color=DS["nav_active"] if active else "transparent")
                self._nav_bars[i].configure(fg_color=DS["accent"] if active else "transparent")
                self._nav_nums[i].configure(text_color=DS["accent"] if active else "#4d6484")
                self._nav_labels[i].configure(text_color="#ffffff" if active else DS["text_dim"],
                                              font=ctk.CTkFont(size=14, weight="bold" if active else "normal"))
            except Exception:
                pass

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

        # 广播队列面板
        self.queue_panel = self.create_queue_panel()
        self.queue_panel.grid(row=0, column=0, sticky="nsew")
        self.queue_panel.grid_remove()

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
        # 车次时刻自动广播（每 30 秒检查开点）
        self._auto_fired = set()
        self._auto_fired_date = ""
        self.after(30000, self._auto_sched_tick)

        # UI 构建完成，显示窗口（避免启动时出现空白"叉"窗口）
        try:
            self.deiconify()
            self.update_idletasks()
            # deiconify 后立即按 DPI/工作区适配，避免窗口超出桌面
            self.after(500, self.maximize_window)
            # CustomTkinter 在设置标题栏颜色时会再次 withdraw；延迟兜底显示，避免只闻其声不见窗口
            self.after(600, self._ensure_window_visible)
        except Exception:
            pass

    def _ensure_window_visible(self):
        """兜底显示主窗口（CTk 高 DPI/标题栏重绘后可能仍保持 withdrawn）。"""
        try:
            if self.state() in ("withdrawn", "iconic"):
                self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(700, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

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
        head.grid_columnconfigure(1, minsize=250, weight=0)
        head.grid_propagate(False)
        ctk.CTkLabel(head, text="旅客服务智能管理广播系统 · 车站大屏",
                    font=ctk.CTkFont(size=22, weight="bold"),
                    text_color="#9fd4ff").grid(row=0, column=0, sticky="w", padx=30, pady=(14, 0))
        self.screen_clock = ctk.CTkLabel(head, text="--:--:--", width=240, anchor="e",
                                         font=ctk.CTkFont(size=30, weight="bold"),
                                         text_color="#ffffff")
        self.screen_clock.grid(row=0, column=1, sticky="e", padx=30, pady=(8, 0))
        self.screen_date = ctk.CTkLabel(head, text="", width=240, anchor="e",
                                        font=ctk.CTkFont(size=15), text_color="#9fc8ee")
        self.screen_date.grid(row=1, column=1, sticky="e", padx=30)
        # 欢迎横幅（站名来自系统设置：车站显示设置；上移与日期同行）
        self.screen_welcome = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=30, weight="bold"),
                                           text_color="#ffd24d")
        self.screen_welcome.grid(row=1, column=0, sticky="w", padx=30, pady=(2, 0))

        # ===== 中部：列车表（大字号块状行，参考高铁站电子屏） =====
        mid = ctk.CTkFrame(panel, fg_color=BLUE_D, corner_radius=0)
        mid.grid(row=1, column=0, sticky="nsew", padx=14, pady=(8, 4))
        self.screen_container = mid
        self.screen_rows = {}          # 车次号 -> {labels, raw, frame, idx}（稳定键，根治排序错位）
        self._screen_widgets = []      # 自建的表头/行控件（刷新时只销毁这些）
        self._build_screen_header(mid)
        self._screen_header_built = True   # 表头已建一次，增量刷新不再重建

        # ===== 底部：状态 + 刷新 =====
        foot = ctk.CTkFrame(panel, fg_color=BLUE_H, corner_radius=0)
        foot.grid(row=2, column=0, sticky="ew")
        self.screen_status = ctk.CTkLabel(foot, text="● 大屏运行中",
                                          font=ctk.CTkFont(size=14, weight="bold"), text_color="#6be26b")
        self.screen_status.pack(side="left", padx=24, pady=12)
        # 独立窗口模式开关：默认正常 Windows 窗口；勾选则全屏显示（无边框铺满）
        self._sw_full_switch = ctk.CTkSwitch(foot, text="全屏显示",
                                             font=ctk.CTkFont(size=12), text_color="#cfe6ff",
                                             command=self._on_sw_full_toggle)
        self._sw_full_switch.pack(side="left", padx=8, pady=12)
        # 排序方式：默认按开点时间（稳定不跳动），可切换为状态优先
        self.screen_sort_menu = ctk.CTkOptionMenu(
            foot, values=["按开点时间", "按状态优先"], width=118, height=30,
            font=ctk.CTkFont(size=12), command=self._on_screen_sort_change)
        self.screen_sort_menu.set("按开点时间")
        self.screen_sort_menu.pack(side="left", padx=8, pady=12)
        ctk.CTkButton(foot, text="刷新", width=90, height=32, fg_color="#0a4a8a",
                      hover_color="#0d5aa5", font=ctk.CTkFont(size=13),
                      command=self.refresh_screen).pack(side="right", padx=12, pady=8)
        ctk.CTkButton(foot, text="独立窗口", width=110, height=32, fg_color="#0a4a8a",
                      hover_color="#0d5aa5", font=ctk.CTkFont(size=13),
                      command=self.open_screen_window).pack(side="right", padx=6, pady=8)
        ctk.CTkButton(foot, text="关闭副屏", width=100, height=32, fg_color="#8a2a2a",
                      hover_color="#aa3a3a", font=ctk.CTkFont(size=13),
                      command=self._close_screen_win).pack(side="right", padx=2, pady=8)
        return panel

    def _on_sw_full_toggle(self):
        """大屏独立窗口全屏开关：副屏已打开时立即生效（无需重新打开）"""
        on = bool(self._sw_full_switch.get())
        mode = "全屏显示（无边框铺满，Esc 退出）" if on else "正常窗口（可拖动/调整大小）"
        self.set_status(f"独立窗口模式：{mode}")
        # 若副屏已打开，立即应用/撤销全屏
        w = getattr(self, "_screen_win", None)
        if w is not None:
            try:
                if w.winfo_exists():
                    self._apply_screen_mode(w, on)
                    if on:
                        self.set_status("副屏已切换为全屏显示（Esc 退出全屏）")
                    else:
                        self.set_status("副屏已恢复为正常窗口")
            except Exception:
                pass

    def _on_screen_sort_change(self, value):
        """大屏排序方式切换：按开点时间（推荐，顺序稳定）/ 按状态优先"""
        self._screen_sort_mode = "status" if "状态" in str(value) else "time"
        try:
            self.save_bc_settings(silent=True)
        except Exception:
            pass
        self.refresh_screen(silent=True)
        try:
            self.load_trains()
        except Exception:
            pass
        # 副屏同步刷新
        _rf = getattr(self, "_sw_refresh", None)
        if _rf is not None:
            try:
                _rf()
            except Exception:
                pass

    def _monitor_rect_at(self, x, y):
        """返回包含 (x, y) 的显示器矩形 (left, top, right, bottom)；找不到则主屏"""
        try:
            import ctypes
            from ctypes import wintypes
            monitors = []

            @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.POINTER(wintypes.RECT), ctypes.c_double)
            def _cb(_hmon, _hdc, _lprc, _lparam):
                if _lprc:
                    r = _lprc.contents
                    monitors.append((r.left, r.top, r.right, r.bottom))
                return 1
            ctypes.windll.user32.EnumDisplayMonitors(None, None, _cb, 0)
            for m in monitors:
                if m[0] <= x < m[2] and m[1] <= y < m[3]:
                    return m
            if monitors:
                return monitors[0]
        except Exception:
            pass
        return None

    def _apply_screen_mode(self, win, full):
        """统一应用副屏模式：full=True 在窗口所在显示器全屏（多屏支持，不再跳回主屏）；
        False 恢复正常 Windows 窗口（回到全屏前的位置）"""
        try:
            if full:
                self._sw_mode = "full"
                # 全屏自动隐藏鼠标指针（大屏显示模式）
                try:
                    win.config(cursor="none")
                except Exception:
                    pass
                # 记录全屏前几何位置，用于恢复（先刷新窗口布局，确保几何已生效）
                try:
                    win.update_idletasks()
                    self._screen_prev_geo = win.geometry()
                except Exception:
                    pass
                try:
                    _rx = win.winfo_rootx() + win.winfo_width() // 2
                    _ry = win.winfo_rooty() + win.winfo_height() // 2
                    rect = self._monitor_rect_at(_rx, _ry)
                except Exception:
                    rect = None
                if rect:
                    # 在窗口所在显示器全屏（无边框铺满该屏）
                    try:
                        win.overrideredirect(True)
                        win.update_idletasks()
                        win.geometry(f"{rect[2] - rect[0]}x{rect[3] - rect[1]}+{rect[0]}+{rect[1]}")
                    except Exception:
                        try:
                            win.attributes("-fullscreen", True)
                        except Exception:
                            pass
                else:
                    try:
                        win.attributes("-fullscreen", True)
                    except Exception:
                        try:
                            win.state("zoomed")
                        except Exception:
                            pass
                try:
                    win.lift()
                    win.attributes("-topmost", True)
                except Exception:
                    pass
                try:
                    self.after(800, lambda: win.attributes("-topmost", False)
                               if win.winfo_exists() else None)
                except Exception:
                    pass
            else:
                self._sw_mode = "normal"
                # 恢复正常窗口：恢复鼠标指针
                try:
                    win.config(cursor="")
                except Exception:
                    pass
                try:
                    win.overrideredirect(False)
                except Exception:
                    pass
                try:
                    win.attributes("-fullscreen", False)
                except Exception:
                    pass
                try:
                    win.state("normal")
                except Exception:
                    pass
                try:
                    # 恢复到全屏前的位置/大小
                    if getattr(self, "_screen_prev_geo", None):
                        win.geometry(self._screen_prev_geo)
                        self._screen_prev_geo = None
                    else:
                        _sw, _sh = win.winfo_screenwidth(), win.winfo_screenheight()
                        _w, _h = min(1280, _sw - 80), min(800, _sh - 120)
                        win.geometry(f"{_w}x{_h}+{(_sw - _w) // 2}+{(_sh - _h) // 2}")
                except Exception:
                    pass
        except Exception:
            pass

    def _close_screen_win(self):
        """在主程序（主界面大屏）关闭副屏独立窗口"""
        w = getattr(self, "_screen_win", None)
        if w is None:
            self.set_status("副屏独立窗口未打开")
            return
        try:
            if w.winfo_exists():
                w.destroy()
            self.set_status("车站大屏副屏已关闭")
        except Exception:
            self.set_status("副屏独立窗口已关闭")
        self._screen_win = None
        try:
            self._sw_refresh = None
        except Exception:
            pass

    # ---------- 大屏独立窗口（单独窗口显示） ----------
    def open_screen_window(self):
        """车站大屏独立窗口。
        默认：正常 Windows 窗口（可拖动、可调整大小、系统按钮齐全）；
        主界面勾选"全屏显示"后：无边框全屏（Esc 退出），开关对已打开窗口也立即生效。
        关闭副屏在主程序（主界面大屏"关闭副屏"按钮）操作，副屏只显示大屏内容。"""
        # 已有副屏则先关闭，避免多个窗口叠加
        _old = getattr(self, "_screen_win", None)
        if _old is not None:
            try:
                if _old.winfo_exists():
                    _old.destroy()
            except Exception:
                pass
            self._screen_win = None
        full_mode = bool(getattr(self, "_sw_full_switch", None) and self._sw_full_switch.get())
        self._sw_mode = "full" if full_mode else "normal"
        win = ctk.CTkToplevel(self)
        win.title("车站大屏 - 旅客服务系统智能管理广播系统")
        # 全屏/无边框模式必须等窗口和控件建完再应用，否则 Toplevel 尚未映射，
        # overrideredirect 会导致副屏尺寸/位置错乱（只占屏幕一角或闪一下）。
        win.attributes("-topmost", True)   # 大屏副屏常驻最前（不被其他窗口顶到下面）
        win.lift()
        BLUE_D = "#04294a"
        BLUE_H = "#06355c"
        win.configure(fg_color=BLUE_D)
        bg = ctk.CTkFrame(win, fg_color=BLUE_D, corner_radius=0)
        bg.pack(fill="both", expand=True)
        bg.grid_columnconfigure(0, weight=1)
        bg.grid_rowconfigure(1, weight=1)

        # 顶部：标题 + 欢迎语 + 时间
        head = ctk.CTkFrame(bg, fg_color=BLUE_H, corner_radius=0, height=150)
        head.grid(row=0, column=0, sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        head.grid_propagate(False)
        ctk.CTkLabel(head, text="旅客服务智能管理广播系统 · 车站大屏",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color="#9fd4ff").grid(row=0, column=0, sticky="w", padx=40, pady=(16, 0))
        self._sw_clock = ctk.CTkLabel(head, text="--:--:--",
                                      font=ctk.CTkFont(size=40, weight="bold"), text_color="#ffffff")
        self._sw_clock.grid(row=0, column=1, sticky="e", padx=40, pady=(10, 0))
        self._sw_date = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=16), text_color="#9fc8ee")
        self._sw_date.grid(row=1, column=1, sticky="e", padx=40)
        self._sw_welcome = ctk.CTkLabel(head, text="", font=ctk.CTkFont(size=34, weight="bold"),
                                        text_color="#ffd24d")
        self._sw_welcome.grid(row=1, column=0, sticky="w", padx=40, pady=(2, 0))

        # 中部：车次表（7 列均分，与主大屏同色系）
        mid = ctk.CTkFrame(bg, fg_color=BLUE_D, corner_radius=0)
        mid.grid(row=1, column=0, sticky="nsew", padx=24, pady=(10, 4))
        hdr = ["车次 Train", "始发站 From", "开点 Departs", "到点 Arrives",
               "终到站 To", "检票口/车厢 Check-in", "状态 Status"]
        hf = ctk.CTkFrame(mid, fg_color="#0d4a8a", corner_radius=6, height=50)
        hf.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        hf.grid_propagate(False)
        mid.grid_columnconfigure(0, weight=1)
        for i in range(7):
            hf.grid_columnconfigure(i, weight=1, minsize=60, uniform="sw")
        for i, h in enumerate(hdr):
            ctk.CTkLabel(hf, text=h, font=ctk.CTkFont(size=16, weight="bold"),
                         text_color="#cfe6ff", anchor="center").grid(row=0, column=i, sticky="ew", padx=8)
        self._sw_mid = mid
        self._sw_hdr = hf

        # 副屏不显示底部工具栏（状态/退出按钮/说明均在主程序操作，保持大屏干净）

        # 定时刷新（2 秒），与主界面数据同步
        def _refresh():
            try:
                if not win.winfo_exists():
                    return
                station = "丽水站"
                try:
                    if hasattr(self, "station_entry"):
                        station = (self.station_entry.get().strip() or station)
                except Exception:
                    pass
                self._sw_welcome.configure(text=f"{station} 欢迎您")
                trains = []
                try:
                    for c in self.bc_train_tree.get_children():
                        trains.append(list(self.bc_train_tree.item(c)["values"]))
                except Exception:
                    pass
                if not trains:
                    # 树空时直接从 trains.json 读取（load_trains_data 返回 bool，不能当列表用）
                    try:
                        _f = os.path.join(get_project_root(), "trains.json")
                        if os.path.exists(_f):
                            with open(_f, "r", encoding="utf-8") as _ff:
                                trains = json.load(_ff) or []
                    except Exception:
                        trains = []
                # 与主屏一致：状态优先级 + 开点时间排序
                trains = self._screen_sorted_rows(trains)
                new_keys = [str(t[0]) for t in trains]
                # 现有行：车次号 -> frame（稳定键，排序变化只移动位置、不覆盖内容）
                old_rows = {}
                for c in mid.winfo_children():
                    if c is not hf and getattr(c, "_sw_key", None):
                        old_rows[c._sw_key] = c
                # 删除已不存在的车次行
                for k in [k for k in old_rows if k not in new_keys]:
                    try:
                        old_rows[k].destroy()
                    except Exception:
                        pass
                # 清理"暂无车次信息"占位
                for c in mid.winfo_children():
                    if getattr(c, "_sw_empty", False):
                        try:
                            c.destroy()
                        except Exception:
                            pass
                if not trains:
                    if not any(getattr(c, "_sw_empty", False) for c in mid.winfo_children()):
                        _empty = ctk.CTkLabel(mid, text="暂无车次信息", font=ctk.CTkFont(size=28),
                                              text_color="#7fa8d0")
                        _empty._sw_empty = True
                        _empty.grid(row=1, column=0, pady=30)
                else:
                    for i, vals in enumerate(trains):
                        vals = (list(vals) + [""] * 9)[:9]
                        key = str(vals[0])
                        cells = [str(vals[0]), str(vals[2]), str(vals[4]),
                                 str(vals[8] if len(vals) > 8 else "--:--"),
                                 str(vals[3]), str(vals[5]), str(vals[7])]
                        if key in old_rows:
                            rf = old_rows[key]
                            rf.grid(row=i + 1, column=0, sticky="ew", pady=5)
                            labs = [c for c in rf.winfo_children()
                                    if isinstance(c, ctk.CTkLabel)]
                            _changed = False
                            for col, v in enumerate(cells):
                                if col < len(labs):
                                    try:
                                        if col == 6:
                                            # 状态列：文字或颜色任一变化都同步主屏
                                            _cur_t = labs[col].cget("text")
                                            _cur_c = labs[col].cget("text_color")
                                            _new_c = self.get_screen_status_color(v)
                                            if _cur_t != v or _cur_c != _new_c:
                                                labs[col].configure(text=v, text_color=_new_c)
                                        else:
                                            # 无变化跳过，减少重绘（降低副屏占用）
                                            if labs[col].cget("text") != v:
                                                labs[col].configure(text=v)
                                                _changed = True
                                    except Exception:
                                        pass
                            # 文本列有变化时短暂高亮过渡动画（与主屏一致）
                            if _changed:
                                try:
                                    self._flash_screen_labels(labs[:6], ("sub", key))
                                except Exception:
                                    pass
                        else:
                            bg_row = "#0a3a68" if i % 2 == 0 else "#0b4278"
                            rf = ctk.CTkFrame(mid, fg_color=bg_row, corner_radius=6)
                            rf._sw_key = key
                            rf.grid(row=i + 1, column=0, sticky="ew", pady=5)
                            for j in range(7):
                                rf.grid_columnconfigure(j, weight=1, minsize=60, uniform="sw")
                            for col, v in enumerate(cells):
                                # 状态列与主屏同色，其余列白色
                                _tc = self.get_screen_status_color(v) if col == 6 else "#ffffff"
                                ctk.CTkLabel(rf, text=v, font=ctk.CTkFont(size=24, weight="bold"),
                                             text_color=_tc, anchor="center").grid(row=0, column=col,
                                                                                   sticky="ew", padx=8, pady=8)
                            # 新建行淡入动画（背景渐变，不跳变）
                            try:
                                win.after(10, lambda rf=rf, bg_row=bg_row, key=key: self._fade_in_screen_row(rf, bg_row, ("sub", key)))
                            except Exception:
                                pass
            except Exception:
                pass
            try:
                win.after(2000, _refresh)   # 2 秒刷新（有变化才重绘，占用低、响应快）
            except Exception:
                pass
        # 时钟独立每秒跳动（读秒流畅，不卡顿）；数据刷新保持 2 秒增量
        def _clock_tick():
            try:
                if not win.winfo_exists():
                    return
                _c = time.strftime("%H:%M:%S")
                if self._sw_clock.cget("text") != _c:
                    self._sw_clock.configure(text=_c)
                _wd = "一二三四五六日"[time.localtime().tm_wday]
                _d = time.strftime("%Y-%m-%d") + f" 星期{_wd}"
                if self._sw_date.cget("text") != _d:
                    self._sw_date.configure(text=_d)
            except Exception:
                pass
            try:
                win.after(1000, _clock_tick)
            except Exception:
                pass

        # 保存副屏刷新函数引用，供主屏状态变化时实时同步（主屏预览 → 副屏显示）
        self._sw_refresh = _refresh
        _refresh()
        _clock_tick()
        if full_mode:
            try:
                win.after(80, lambda: self._apply_screen_mode(win, True))
            except Exception:
                pass

        def _esc(_e=None):
            try:
                if self._sw_mode == "full":
                    # overrideredirect 全屏（多屏）或 fullscreen 全屏 均在此退出
                    if win.attributes("-fullscreen") or win.overrideredirect():
                        self._apply_screen_mode(win, False)
                        # 开关同步取消，保持状态一致
                        try:
                            if self._sw_full_switch.winfo_exists():
                                self._sw_full_switch.deselect()
                        except Exception:
                            pass
                    else:
                        win.destroy()
                else:
                    # 正常窗口：Esc 直接关闭（系统关闭按钮也可用）
                    win.destroy()
            except Exception:
                try:
                    win.destroy()
                except Exception:
                    pass
        win.bind("<Escape>", _esc)
        win.focus_force()
        win.lift()
        # 跟踪副屏窗口，供主程序"关闭副屏"按钮使用
        self._screen_win = win
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_screen_win())
        if full_mode:
            self.set_status("已打开车站大屏独立窗口（全屏，Esc 退出）")
        else:
            self.set_status("已打开车站大屏独立窗口（正常窗口，可在主界面关闭副屏）")

    # ---------- 大屏表头（双语，参考高铁站电子屏） ----------
    def _build_screen_header(self, mid):
        inner = getattr(mid, "_parent_frame", mid)
        hdr = ["车次 Train", "始发站 From", "开点 Departs", "到点 Arrives",
               "终到站 To", "检票口/车厢 Check-in", "状态 Status"]
        try:
            inner.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        # 表头背景条：与数据行等宽、5 列均分（均匀对称）
        head_frame = ctk.CTkFrame(inner, fg_color="#0d4a8a", corner_radius=6, height=44)
        head_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        head_frame.grid_propagate(False)
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
        bg = "#0a3a68"
        row_frame = ctk.CTkFrame(inner, fg_color=bg, corner_radius=6)
        row_frame.grid(row=idx + 1, column=0, sticky="ew", pady=4)
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
        key = str(r[0])
        # 以车次号为稳定键存储：排序变化时行只移动位置、不覆盖内容（根治"乱跳"）
        self.screen_rows[key] = {"labels": labels, "raw": r, "frame": row_frame, "idx": idx, "bg": bg}
        # 不做淡入/闪烁动画：刷新时保持静态，避免用户看到“闪一下”

    # ---------- 大屏刷新动画（轻量高亮过渡 / 新建行淡入，防抖、不阻塞、低占用） ----------
    def _flash_screen_labels(self, labels, anim_key):
        """行数据变化时文本列短暂高亮过渡（3 帧 45ms，动画中不重复触发，避免抖动）"""
        try:
            _s = getattr(self, "_screen_anim_rows", set())
            if anim_key in _s:
                return
            _s.add(anim_key)
            self._screen_anim_rows = _s
            _labs = [lb for lb in labels if lb is not None and lb.winfo_exists()]
            _frames = [("#7fc8ff", 0), ("#a8dcff", 1), ("#d6efff", 2), ("#ffffff", 3)]
            def _step(_i):
                try:
                    if _i >= len(_frames):
                        _s.discard(anim_key)
                        return
                    _c = _frames[_i][0]
                    for lb in _labs:
                        if lb.winfo_exists():
                            lb.configure(text_color=_c)
                    self.after(45, lambda: _step(_i + 1))
                except Exception:
                    try:
                        _s.discard(anim_key)
                    except Exception:
                        pass
            _step(0)
        except Exception:
            pass

    def _fade_in_screen_row(self, frame, end_bg, anim_key):
        """新建行淡入：背景从深蓝渐变到正常行色（3 帧 45ms）"""
        try:
            _s = getattr(self, "_screen_anim_rows", set())
            if anim_key in _s:
                return
            _s.add(anim_key)
            self._screen_anim_rows = _s
            _frames = ["#0b3560", "#0d3f70", end_bg]
            def _step(_i):
                try:
                    if _i >= len(_frames):
                        _s.discard(anim_key)
                        return
                    if frame is not None and frame.winfo_exists():
                        frame.configure(fg_color=_frames[_i])
                    self.after(45, lambda: _step(_i + 1))
                except Exception:
                    try:
                        _s.discard(anim_key)
                    except Exception:
                        pass
            _step(0)
        except Exception:
            pass

    # ---------- 大屏行增量更新 / 删除（避免全量重建跳动） ----------
    def _update_screen_row(self, key, r):
        """按车次号（稳定键）增量更新行内容：数据未变只同步斑马色，变了只改文本，不重建 frame"""
        row = self.screen_rows.get(key)
        if row is None:
            return
        old = row.get("raw")
        bg = "#0a3a68"
        try:
            if row.get("bg") != bg:
                row["frame"].configure(fg_color=bg)
                row["bg"] = bg
        except Exception:
            pass
        if old == r:
            return
        _arr = str(r[8]) if len(r) > 8 else "--:--"
        vals = [str(r[0]), str(r[2]), str(r[4]), _arr, str(r[3]), str(r[5])]
        labels = row.get("labels", [])
        for col, v in enumerate(vals):
            if col < len(labels):
                try:
                    if labels[col].cget("text") != v:
                        labels[col].configure(text=v)
                except Exception:
                    pass
        row["raw"] = r
        # 不做高亮/闪烁动画：刷新时文本保持稳定颜色

    def _destroy_screen_row(self, key):
        """按车次号删除指定行（frame + labels 一并清理引用）"""
        row = self.screen_rows.pop(key, None)
        if row is None:
            return
        for w in row.get("labels", []):
            try:
                if w.winfo_exists():
                    if w in self._screen_widgets:
                        self._screen_widgets.remove(w)
                    w.destroy()
            except Exception:
                pass
        frame = row.get("frame")
        try:
            if frame is not None and frame.winfo_exists():
                if frame in self._screen_widgets:
                    self._screen_widgets.remove(frame)
                frame.destroy()
        except Exception:
            pass

    # ---------- 大屏状态列刷新（按开车时间 + 数据状态） ----------
    def get_screen_status_color(self, status):
        """主屏/副屏共用的状态颜色（与主大屏完全一致）"""
        return {"停止检票": "#ff5a5a", "正在检票": "#4dff6e",
                "正在候车": "#ffd24d", "已发车": "#9aa7b5",
                "晚点": "#ff9a3d", "待检票": "#9adcff",
                "停运": "#ff5a5a", "计划中": "#9aa7b5",
                "检票中": "#4dff6e", "已到达": "#4dff6e",
                "取消": "#ff5a5a"}.get(str(status).strip(), "#ffd24d")

    def _train_status_tag(self, status):
        """广播管理车次列表的状态颜色 tag（按业务状态分组）"""
        st = str(status or "").strip()
        if st in ("正在检票", "检票中"):
            return "st_green"
        if st in ("停止检票", "停运", "晚点", "取消"):
            return "st_red"
        if st == "待检票":
            return "st_cyan"
        if st in ("正在候车", "计划中"):
            return "st_yellow"
        if st in ("已发车", "已到达"):
            return "st_gray"
        return "st_default"

    def apply_train_status_colors(self):
        """车次列表按状态着色：正在检票绿、停止检票/停运/晚点红，其余按候车/待检/已发车区分。"""
        try:
            tree = self.bc_train_tree
            colors = {
                "st_green": "#4dff6e",
                "st_red": "#ff5a5a",
                "st_cyan": "#9adcff",
                "st_yellow": "#ffd24d",
                "st_gray": "#9aa7b5",
                "st_default": DS["text"],
            }
            for tag, color in colors.items():
                tree.tag_configure(tag, foreground=color)
            for i, c in enumerate(tree.get_children()):
                vals = list(tree.item(c, "values"))
                st = str(vals[7]) if len(vals) > 7 else ""
                new_tags = ("row", self._train_status_tag(st))
                try:
                    if tuple(tree.item(c, "tags")) != new_tags:
                        tree.item(c, tags=new_tags)
                except Exception:
                    pass
        except Exception:
            pass

    def _update_screen_statuses(self, smin=None):
        try:
            now = time.localtime()
            now_min = now.tm_hour * 60 + now.tm_min
            smin = smin if smin is not None else 5
            # 一次性建立 车次号->状态 映射（避免每行线性扫描整棵树 O(n²)，车次多时性能与抖动都受影响）
            st_map = {}
            try:
                for _c in self.bc_train_tree.get_children():
                    _vals = list(self.bc_train_tree.item(_c)["values"])
                    if _vals and str(_vals[0]).strip():
                        st_map[str(_vals[0])] = str(_vals[7]) if len(_vals) > 7 else ""
            except Exception:
                pass
            for key, row in self.screen_rows.items():
                r = list(row.get("raw") or [])
                if len(r) < 9:
                    r += [""] * (9 - len(r))
                # 状态实时读统一数据源（车次树状态列），再按时间推进；人工状态不被覆盖
                _st = st_map.get(str(r[0]), str(r[7]) if len(r) > 7 else "")
                r[7] = str(_st).strip()
                disp = effective_train_status(r, smin, now_min)
                color = self.get_screen_status_color(disp)
                # 状态列始终是行内最后一个 label（与列数无关）；无变化跳过重绘
                _lab = row["labels"][-1]
                if _lab.cget("text") != disp or _lab.cget("text_color") != color:
                    _lab.configure(text=disp, text_color=color)
        except Exception:
            pass

    def create_system_panel(self):
        """系统设置：选项卡结构（自动广播 / 车站设置）"""
        panel = ctk.CTkFrame(self.content_frame, fg_color=DS["panel"], corner_radius=10)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        # ===== 选项卡栏 =====
        tab_bar = ctk.CTkFrame(panel, fg_color="transparent")
        tab_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        self._sys_tab_auto = ctk.CTkButton(tab_bar, text="自动广播", width=110, height=32,
                                           font=ctk.CTkFont(size=13, weight="bold"),
                                           fg_color=DS["accent"], hover_color=DS["btn_primary_hover"],
                                           text_color="#ffffff", command=lambda: self._switch_sys_tab("auto"))
        self._sys_tab_auto.pack(side="left", padx=(0, 6))
        self._sys_tab_sta = ctk.CTkButton(tab_bar, text="车站设置", width=110, height=32,
                                          font=ctk.CTkFont(size=13, weight="bold"),
                                          fg_color=DS["btn"], hover_color=DS["btn_hover"],
                                          text_color=DS["text"], command=lambda: self._switch_sys_tab("sta"))
        self._sys_tab_sta.pack(side="left", padx=(6, 0))
        self._sys_tab_glb = ctk.CTkButton(tab_bar, text="全局设置", width=110, height=32,
                                          font=ctk.CTkFont(size=13, weight="bold"),
                                          fg_color=DS["btn"], hover_color=DS["btn_hover"],
                                          text_color=DS["text"], command=lambda: self._switch_sys_tab("glb"))
        self._sys_tab_glb.pack(side="left", padx=(6, 0))

        # ===== 选项卡1：自动广播（原定时广播内容） =====
        auto_frame = ctk.CTkFrame(panel, fg_color="transparent")
        auto_frame.grid(row=1, column=0, sticky="nsew")
        auto_frame.grid_columnconfigure(0, weight=1)
        auto_frame.grid_rowconfigure(4, weight=1)
        self._sys_auto_frame = auto_frame

        ctk.CTkLabel(auto_frame, text="定时广播（到点自动播放指定广播）",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=DS["accent"]).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(auto_frame, text="每天到设定时间自动播放：时间(HH:MM) + 广播类型 + 车次（车次可留空=使用当前选中车次），播放时同步车站大屏",
                     font=ctk.CTkFont(size=11), text_color=DS["text_dim"]).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 6))

        # ----- 添加区 -----
        add_frame = ctk.CTkFrame(auto_frame, fg_color=DS["panel2"], corner_radius=8)
        add_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(6, 4))
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

        # ----- 任务列表 -----
        list_frame = ctk.CTkFrame(auto_frame, fg_color=DS["panel2"], corner_radius=8)
        list_frame.grid(row=4, column=0, sticky="nsew", padx=20, pady=(4, 4))
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
        self.sched_tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        sched_vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.sched_tree.yview)
        sched_vsb.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=10)
        self.sched_tree.configure(yscrollcommand=sched_vsb.set)
        self.sched_tree.bind("<Double-1>", self.toggle_schedule)

        op_frame = ctk.CTkFrame(auto_frame, fg_color="transparent")
        op_frame.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 10))
        ctk.CTkButton(op_frame, text="⏯ 启用/停用(双击列表也可)", width=160, height=32,
                      fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      command=self.toggle_schedule).pack(side="left", padx=2)
        ctk.CTkButton(op_frame, text="- 删除选中", width=110, height=32,
                      fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                      command=self.del_schedule).pack(side="left", padx=2)
        ctk.CTkButton(op_frame, text="恢复默认(清空)", width=120, height=32,
                      fg_color=DS["btn_warn"], hover_color=DS["btn_warn_hover"],
                      command=self.clear_schedule).pack(side="right", padx=2)

        # ===== 车次时刻自动广播（按开点自动播检票预告/开始检票） =====
        auto2 = ctk.CTkFrame(auto_frame, fg_color=DS["panel2"], corner_radius=8)
        auto2.grid(row=3, column=0, sticky="ew", padx=20, pady=(2, 4))
        # 右侧留伸缩列，控件本身紧凑靠左；不要把输入框所在列设 weight，否则“分钟”被推到屏幕最右
        auto2.grid_columnconfigure(7, weight=1)
        ctk.CTkLabel(auto2, text="车次时刻自动广播（按开点自动播放）",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color=DS["accent"]).grid(
            row=0, column=0, columnspan=7, sticky="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(auto2, text="启用后根据车辆管理中的开点时间，开点前 N 分钟自动播检票预告 / 开点前 M 分钟自动播开始检票，播放时同步车站大屏（每日每车次只触发一次）",
                     font=ctk.CTkFont(size=11), text_color=DS["text_dim"]).grid(
            row=1, column=0, columnspan=7, sticky="w", padx=14, pady=(0, 6))
        self.train_auto_sw = ctk.CTkSwitch(auto2, text="启用", font=ctk.CTkFont(size=12),
                                           progress_color=DS["accent"], command=self._save_train_auto_cfg)
        self.train_auto_sw.grid(row=2, column=0, padx=(14, 8), pady=8, sticky="w")
        ctk.CTkLabel(auto2, text="检票预告提前:", font=ctk.CTkFont(size=12), text_color=DS["text_dim"]).grid(
            row=2, column=1, padx=(6, 4), sticky="e")
        self.train_preview_min = ctk.CTkEntry(auto2, width=60, font=ctk.CTkFont(size=12))
        self.train_preview_min.grid(row=2, column=2, sticky="w", padx=4)
        ctk.CTkLabel(auto2, text="分钟", font=ctk.CTkFont(size=11), text_color=DS["text_dim"]).grid(
            row=2, column=3, padx=(0, 10))
        ctk.CTkLabel(auto2, text="开始检票提前:", font=ctk.CTkFont(size=12), text_color=DS["text_dim"]).grid(
            row=2, column=4, padx=(6, 4), sticky="e")
        self.train_start_min = ctk.CTkEntry(auto2, width=60, font=ctk.CTkFont(size=12))
        self.train_start_min.grid(row=2, column=5, sticky="w", padx=4)
        ctk.CTkLabel(auto2, text="分钟", font=ctk.CTkFont(size=11), text_color=DS["text_dim"]).grid(
            row=2, column=6, padx=(0, 14))
        # 回读配置填充
        try:
            _acfg = self.load_sys_config()
            if _acfg.get("train_auto_bcast", False):
                self.train_auto_sw.select()
            else:
                self.train_auto_sw.deselect()
            self.train_preview_min.delete(0, "end")
            self.train_preview_min.insert(0, str(_acfg.get("train_preview_min", 5) or 5))
            self.train_start_min.delete(0, "end")
            self.train_start_min.insert(0, str(_acfg.get("train_start_min", 1) or 1))
        except Exception:
            pass

        # ===== 选项卡2：车站设置（大屏欢迎语 / 停止检票提前量） =====
        sta_frame = ctk.CTkFrame(panel, fg_color=DS["panel2"], corner_radius=8)
        sta_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        sta_frame.grid_columnconfigure(4, weight=1)
        self._sys_sta_frame = sta_frame

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
        # ===== 选项卡3：全局设置 =====
        self.create_global_settings(panel)
        # 默认显示"自动广播"选项卡
        self.after(100, lambda: self._switch_sys_tab("auto"))
        return panel

    def _switch_sys_tab(self, name):
        """系统设置选项卡切换：auto=自动广播，sta=车站设置，glb=全局设置"""
        auto = getattr(self, "_sys_auto_frame", None)
        sta = getattr(self, "_sys_sta_frame", None)
        glb = getattr(self, "_sys_glb_frame", None)
        if auto is None or sta is None or glb is None:
            return
        def _sel(tab_btn):
            self._sys_tab_auto.configure(fg_color=DS["btn"], text_color=DS["text"])
            self._sys_tab_sta.configure(fg_color=DS["btn"], text_color=DS["text"])
            self._sys_tab_glb.configure(fg_color=DS["btn"], text_color=DS["text"])
            tab_btn.configure(fg_color=DS["accent"], text_color="#ffffff")
        if name == "auto":
            auto.grid(); sta.grid_remove(); glb.grid_remove()
            _sel(self._sys_tab_auto)
        elif name == "sta":
            sta.grid(); auto.grid_remove(); glb.grid_remove()
            _sel(self._sys_tab_sta)
        else:
            glb.grid(); auto.grid_remove(); sta.grid_remove()
            _sel(self._sys_tab_glb)

    # ===================== 全局设置（系统设置·选项卡3） =====================
    def create_global_settings(self, panel):
        """全局设置选项卡：9 大分类（基础/启动/音频/网络/设备/权限/日志/备份/关于）"""
        glb = ctk.CTkFrame(panel, fg_color="transparent")
        glb.grid(row=1, column=0, sticky="nsew")
        glb.grid_columnconfigure(0, weight=0)
        glb.grid_columnconfigure(1, weight=1)
        glb.grid_rowconfigure(0, weight=1)
        self._sys_glb_frame = glb

        self._gs_defaults = {
            "station_name": "丽水站", "system_name": "旅客服务智能管理广播系统",
            "org_name": "丽水铁路信息技术服务中心", "run_mode": "单机",
            "language": "简体中文", "timezone": "Asia/Shanghai",
            "date_format": "YYYY-MM-DD", "version": "26.10.2",
            "auto_start": False, "start_minimized": False, "check_update": True,
            "startup_log": True, "auto_restart": False,
            "audio_device": "默认设备", "master_volume": 80, "max_volume": 100,
            "fade_ms": 120, "anti_pop": True,
            "night_mute": False, "night_start": "23:00", "night_end": "06:00", "night_volume": 30,
            "server_host": "127.0.0.1", "server_port": 8888, "protocol": "TCP",
            "heartbeat_s": 30, "timeout_s": 3, "reconnect_n": 5,
            "resync_on_reconnect": True, "offline_cache": True, "multi_sync": False,
            "default_zone": "A区", "terminal_group": "全部", "offline_s": 60,
            "auto_discover": True, "auto_register": False, "refresh_s": 10,
            "role": "管理员", "danger_confirm": True, "emergency_pwd_protect": False,
            "delete_pwd_protect": True, "login_timeout_min": 0, "auto_lock": False,
            "audit_log": True, "log_level": "信息", "log_keep_days": 7,
            "diag_mode": False, "perf_monitor": False,
        }

        # 左：分类导航
        nav = ctk.CTkFrame(glb, fg_color=DS["panel2"], corner_radius=8)
        nav.grid(row=0, column=0, sticky="nsw", padx=(20, 8), pady=10)
        nav.grid_columnconfigure(0, weight=1)
        self._gs_nav_btns = {}
        cats = [("basic", "基础信息"), ("run", "启动与运行"), ("audio", "音频与播放"),
                ("dev", "设备与终端"), ("sec", "权限与安全"),
                ("log", "日志与诊断"), ("bak", "备份与维护"), ("about", "关于")]
        for i, (key, lab) in enumerate(cats):
            b = ctk.CTkButton(nav, text=lab, width=130, height=32, font=ctk.CTkFont(size=12),
                              fg_color=DS["btn"], hover_color=DS["btn_hover"],
                              text_color=DS["text"], command=lambda k=key: self._gs_switch(k))
            b.grid(row=i, column=0, padx=8, pady=3, sticky="ew")
            self._gs_nav_btns[key] = b

        # 右：内容容器
        content = ctk.CTkFrame(glb, fg_color=DS["panel2"], corner_radius=8)
        content.grid(row=0, column=1, sticky="nsew", padx=(8, 20), pady=10)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        self._gs_content = content
        self._gs_frames = {}
        self._gs_fields = {}

        # 构建 8 分类（网络与同步已按需求移除）
        self._gs_build_basic(content)
        self._gs_build_run(content)
        self._gs_build_audio(content)
        self._gs_build_dev(content)
        self._gs_build_sec(content)
        self._gs_build_log(content)
        self._gs_build_bak(content)
        self._gs_build_about(content)

        # 底部操作条
        bar = ctk.CTkFrame(glb, fg_color="transparent")
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 12))
        ctk.CTkButton(bar, text="保存设置", width=110, height=32,
                      fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                      font=ctk.CTkFont(size=12), command=self._gs_save).pack(side="left", padx=(0, 6))
        ctk.CTkButton(bar, text="取消更改", width=110, height=32,
                      fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      font=ctk.CTkFont(size=12), command=self._gs_cancel).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="恢复默认", width=110, height=32,
                      fg_color=DS["btn_warn"], hover_color=DS["btn_warn_hover"],
                      font=ctk.CTkFont(size=12), command=self._gs_default).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="导入配置", width=110, height=32,
                      fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      font=ctk.CTkFont(size=12), command=self._gs_import).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="导出配置", width=110, height=32,
                      fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      font=ctk.CTkFont(size=12), command=self._gs_export).pack(side="left", padx=(6, 0))

        self._gs_load()
        self._gs_switch("basic")

    def _gs_build_cat(self, content, cat, specs):
        """通用分类构建：specs = [(label, key, type, default, opt, hint)]"""
        f = ctk.CTkFrame(content, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew")
        f.grid_columnconfigure(1, weight=1)
        self._gs_frames[cat] = f
        r = 0
        for (label, key, typ, default, opt, hint) in specs:
            r += 1
            if typ == "info":
                ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=12),
                             text_color=DS["text"], anchor="w").grid(row=r, column=0, columnspan=3,
                                                                      sticky="w", padx=14, pady=6)
                continue
            ctk.CTkLabel(f, text=label + ":", font=ctk.CTkFont(size=12),
                         text_color=DS["text_dim"]).grid(row=r, column=0, sticky="w", padx=(14, 6), pady=6)
            if typ == "combo":
                w = ctk.CTkComboBox(f, values=opt, font=ctk.CTkFont(size=12), height=30, width=230,
                                    dropdown_font=ctk.CTkFont(size=12), fg_color="#2a2a2a",
                                    button_color="#3a3a3a", button_hover_color="#4a4a4a",
                                    dropdown_fg_color="#ffffff", dropdown_text_color="#000000",
                                    dropdown_hover_color="#e2e2e2")
                try:
                    w.set(str(default))
                except Exception:
                    pass
                w.grid(row=r, column=1, sticky="ew", padx=6, pady=6)
                self._gs_fields[key] = w
            elif typ == "switch":
                w = ctk.CTkSwitch(f, text="", font=ctk.CTkFont(size=12))
                w.grid(row=r, column=1, sticky="w", padx=6, pady=6)
                self._gs_fields[key] = w
            elif typ == "btn":
                w = ctk.CTkButton(f, text=default, width=150, height=30, font=ctk.CTkFont(size=12),
                                  fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                                  command=getattr(self, "_" + opt))
                w.grid(row=r, column=1, sticky="w", padx=6, pady=6)
                self._gs_fields[key] = w
            else:
                w = ctk.CTkEntry(f, font=ctk.CTkFont(size=12), height=30)
                try:
                    w.insert(0, str(default))
                except Exception:
                    pass
                w.grid(row=r, column=1, sticky="ew", padx=6, pady=6)
                self._gs_fields[key] = w
            if hint:
                ctk.CTkLabel(f, text=hint, font=ctk.CTkFont(size=10),
                             text_color=DS["text_dim"]).grid(row=r, column=2, sticky="w", padx=6, pady=6)

    def _gs_build_basic(self, content):
        self._gs_build_cat(content, "basic", [
            ("车站名称", "station_name", "text", "丽水站", None, "车站大屏欢迎语使用"),
            ("系统名称", "system_name", "text", "旅客服务智能管理广播系统", None, "窗口标题/托盘名称"),
            ("机构名称", "org_name", "text", "丽水铁路信息技术服务中心", None, "版本信息/版权显示"),
            ("运行模式", "run_mode", "combo", "单机", ["单机", "服务器", "客户端"], "广播系统运行方式"),
            ("语言", "language", "combo", "简体中文", ["简体中文", "English"], "界面语言"),
            ("时区", "timezone", "combo", "Asia/Shanghai", ["Asia/Shanghai", "UTC"], "定时广播按此时区"),
            ("日期格式", "date_format", "combo", "YYYY-MM-DD", ["YYYY-MM-DD", "YYYY/MM/DD", "MM-DD-YYYY"], "日志/大屏日期显示"),
            ("版本号", "version", "text", "26.10.2", None, "系统当前版本（只读参考）"),
        ])

    def _gs_build_run(self, content):
        self._gs_build_cat(content, "run", [
            ("开机自启", "auto_start", "switch", False, None, "开机后自动启动本系统"),
            ("启动后最小化到托盘", "start_minimized", "switch", False, None, "启动不弹主窗口，只驻托盘"),
            ("启动时检查更新", "check_update", "switch", True, None, "联网检查新版本（离线版无更新源）"),
            ("启动日志开关", "startup_log", "switch", True, None, "记录启动过程日志"),
            ("异常自动重启", "auto_restart", "switch", False, None, "崩溃后自动重新拉起"),
        ])

    def _gs_build_audio(self, content):
        self._gs_build_cat(content, "audio", [
            ("默认播放设备", "audio_device", "text", "默认设备", None, "音频输出设备名称"),
            ("主音量", "master_volume", "num", 80, None, "全局主音量 0-100（播放时实际生效）"),
            ("最大音量限制", "max_volume", "num", 100, None, "防误操作音量上限 0-100"),
            ("全局淡入淡出时长", "fade_ms", "num", 120, None, "开始/结束淡入淡出毫秒数"),
            ("防爆音开关", "anti_pop", "switch", True, None, "播放/停止/切换时防爆音"),
            ("夜间静音时段", "night_mute", "switch", False, None, "启用后夜间自动降低广播音量"),
            ("夜间开始", "night_start", "text", "23:00", None, "夜间时段开始时间（HH:MM）"),
            ("夜间结束", "night_end", "text", "06:00", None, "夜间时段结束时间（HH:MM，跨天）"),
            ("夜间音量", "night_volume", "num", 30, None, "夜间时段的播放音量 0-100"),
            ("音频输出测试", "test_audio", "btn", "测试音频输出", "gs_test_audio", "播放一段提示音验证设备"),
        ])

    def _gs_build_net(self, content):
        self._gs_build_cat(content, "net", [
            ("服务器地址", "server_host", "text", "127.0.0.1", None, "后端/大屏同步服务器"),
            ("端口", "server_port", "num", 8888, None, "连接端口（后端默认 8888）"),
            ("协议", "protocol", "combo", "TCP", ["TCP", "WebSocket", "SSE", "MQTT"], "同步通信协议"),
            ("心跳间隔(秒)", "heartbeat_s", "num", 30, None, "保活心跳周期"),
            ("超时(秒)", "timeout_s", "num", 3, None, "单次请求超时"),
            ("重连次数", "reconnect_n", "num", 5, None, "断线自动重连次数上限"),
            ("断线补拉", "resync_on_reconnect", "switch", True, None, "重连后自动补齐最新状态"),
            ("离线缓存", "offline_cache", "switch", True, None, "离线时本地缓存播放记录"),
            ("多端同步", "multi_sync", "switch", False, None, "多台终端数据实时同步"),
            ("网络测试", "test_net", "btn", "测试网络连接", "gs_test_network", "检测服务器地址/端口可达性"),
        ])

    def _gs_build_dev(self, content):
        self._gs_build_cat(content, "dev", [
            ("默认分区", "default_zone", "text", "A区", None, "新终端默认所属分区"),
            ("终端分组", "terminal_group", "text", "全部", None, "广播目标默认分组"),
            ("离线判定时间(秒)", "offline_s", "num", 60, None, "超过此时长未响应判为离线"),
            ("自动发现", "auto_discover", "switch", True, None, "自动发现局域网终端"),
            ("自动注册", "auto_register", "switch", False, None, "发现的新终端自动登记"),
            ("状态刷新频率(秒)", "refresh_s", "num", 10, None, "终端在线状态刷新周期"),
            ("终端测试", "test_dev", "btn", "测试终端状态", "gs_test_dev", "发送测试指令到默认终端"),
        ])

    def _gs_build_sec(self, content):
        self._gs_build_cat(content, "sec", [
            ("角色权限", "role", "combo", "管理员", ["管理员", "操作员", "只读"], "当前登录角色"),
            ("危险操作二次确认", "danger_confirm", "switch", True, None, "删除/清空等操作弹确认"),
            ("紧急广播密码保护", "emergency_pwd_protect", "switch", False, None, "触发紧急广播需密码"),
            ("删除/恢复默认密码保护", "delete_pwd_protect", "switch", True, None, "删除配置/恢复默认需密码"),
            ("登录超时(分钟)", "login_timeout_min", "num", 0, None, "0=永不超时"),
            ("自动锁屏", "auto_lock", "switch", False, None, "超时后自动锁定界面"),
            ("操作审计", "audit_log", "switch", True, None, "记录关键操作日志"),
        ])

    def _gs_build_log(self, content):
        self._gs_build_cat(content, "log", [
            ("日志级别", "log_level", "combo", "信息", ["调试", "信息", "警告", "错误"], "日志记录详细程度"),
            ("保留天数", "log_keep_days", "num", 7, None, "日志文件自动清理周期"),
            ("诊断模式", "diag_mode", "switch", False, None, "输出详细诊断信息"),
            ("性能监控", "perf_monitor", "switch", False, None, "记录 CPU/内存占用"),
            ("广播历史", "bcast_log", "btn", "查看/导出广播历史", "gs_bcast_log", "查看每次广播的播放记录并导出"),
            ("一键导出日志", "export_log", "btn", "导出日志文件", "gs_export_log", "保存当前日志到本地"),
            ("一键测试", "test_all", "btn", "一键测试(音频/网络/配置)", "gs_test_all", "快速验证关键链路"),
        ])

    def _gs_bcast_log(self):
        """广播历史日志：查看、导出、清空（记录来自 bcast_log.json，播放时自动写入）"""
        try:
            path = os.path.join(get_project_root(), "bcast_log.json")
            logs = []
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        logs = json.load(f) or []
                except Exception:
                    logs = []
            dlg = ctk.CTkToplevel(self)
            dlg.title("广播历史日志")
            dlg.geometry("640x460")
            dlg.attributes("-topmost", True)
            dlg.transient(self)
            dlg.lift()
            dlg.focus_force()
            dlg.grid_columnconfigure(0, weight=1)
            dlg.grid_rowconfigure(1, weight=1)
            ctk.CTkLabel(dlg, text=f"广播历史（共 {len(logs)} 条，保留最近 2000 条，最新在前）",
                         font=ctk.CTkFont(size=14, weight="bold"), text_color=DS["accent"]).grid(
                row=0, column=0, sticky="w", padx=14, pady=(12, 4))
            tree = ttk.Treeview(dlg, columns=("时间", "广播类型", "车次", "来源"),
                                show="headings", height=16, style="Sched.Treeview")
            sst = ttk.Style()
            try:
                sst.theme_use("clam")
            except Exception:
                pass
            sst.configure("Sched.Treeview", font=(DS["font"], 11), rowheight=26,
                          background=DS["row1"], fieldbackground=DS["row1"],
                          foreground=DS["text"], borderwidth=0)
            sst.map("Sched.Treeview",
                    background=[("selected", DS["row_sel"])],
                    foreground=[("selected", "#ffffff")])
            for i, col in enumerate(("时间", "广播类型", "车次", "来源")):
                tree.heading(col, text=col)
                tree.column(col, width=[170, 240, 100, 90][i], anchor="center")
            tree.grid(row=1, column=0, sticky="nsew", padx=14, pady=6)
            for lg in reversed(logs):
                tree.insert("", "end", values=(lg.get("time", ""), lg.get("type", ""),
                                               lg.get("train", ""), lg.get("source", "")))
            op = ctk.CTkFrame(dlg, fg_color="transparent")
            op.grid(row=2, column=0, sticky="ew", padx=14, pady=(6, 12))

            def _export():
                try:
                    from tkinter import filedialog
                    fp = filedialog.asksaveasfilename(
                        defaultextension=".csv", filetypes=[("CSV 文件", "*.csv")],
                        initialfile="广播历史.csv", parent=dlg)
                    if not fp:
                        return
                    import csv as _csv
                    with open(fp, "w", encoding="utf-8-sig", newline="") as f:
                        w = _csv.writer(f)
                        w.writerow(["时间", "广播类型", "车次", "来源"])
                        for lg in logs:
                            w.writerow([lg.get("time", ""), lg.get("type", ""),
                                        lg.get("train", ""), lg.get("source", "")])
                    self.set_status(f"广播历史已导出: {os.path.basename(fp)}")
                except Exception as e:
                    self.set_status(f"导出失败: {e}")

            def _clear():
                try:
                    if not messagebox.askyesno("清空广播历史", "确定清空全部广播历史记录吗？", parent=dlg):
                        return
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump([], f, ensure_ascii=False)
                    for item in tree.get_children():
                        tree.delete(item)
                    self.set_status("广播历史已清空")
                except Exception as e:
                    self.set_status(f"清空失败: {e}")

            ctk.CTkButton(op, text="导出 CSV", width=110, height=32,
                          fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                          command=_export).pack(side="left", padx=2)
            ctk.CTkButton(op, text="清空", width=90, height=32,
                          fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                          command=_clear).pack(side="left", padx=2)
            ctk.CTkButton(op, text="关闭", width=90, height=32,
                          fg_color=DS["btn"], hover_color=DS["btn_hover"],
                          command=dlg.destroy).pack(side="right", padx=2)
        except Exception as e:
            self.set_status(f"查看广播历史失败: {e}")

    def _gs_build_bak(self, content):
        self._gs_build_cat(content, "bak", [
            ("配置导入", "import_cfg", "btn", "导入配置", "gs_import", "从 JSON 文件导入全局设置"),
            ("配置导出", "export_cfg", "btn", "导出配置", "gs_export", "把当前配置保存为 JSON 文件"),
            ("配置备份", "backup_cfg", "btn", "立即备份", "gs_backup", "备份到 config_backup 目录"),
            ("从备份恢复", "restore_cfg", "btn", "从备份恢复", "gs_restore", "选择备份文件恢复"),
            ("恢复默认", "default_cfg", "btn", "恢复默认设置", "gs_default", "重置全部全局设置"),
            ("语音包体检", "audio_check", "btn", "语音包一键体检", "gs_audio_check", "扫描广播配置引用的音频是否缺失/损坏"),
            ("清理缓存", "clear_cache", "btn", "清理缓存", "gs_clear_cache", "清理 __pycache__ 等临时文件"),
            ("重建图标缓存", "rebuild_icon", "btn", "重建图标缓存", "gs_rebuild_icon", "触发 Windows 图标缓存刷新"),
            ("检查更新", "check_update", "btn", "检查更新", "gs_check_update", "查询系统版本状态"),
        ])

    def _gs_audio_check(self):
        """语音包一键体检（主线程分片扫描，不卡 UI，结果弹窗展示）"""
        self.set_status("语音包体检中，请稍候...")
        try:
            self._audio_check_state = {
                "types": list(self.get_bcast_types()),
                "ti": 0,
                "missing": [],
                "ok": 0,
                "total": 0,
                "extra_idx": 0,
                "extras": [],
            }
        except Exception as e:
            self.set_status(f"体检初始化失败: {e}")
            return
        self._audio_check_step()

    def _audio_check_step(self):
        """体检分片执行：每次处理一个广播类型，主线程 5ms 步进"""
        st = getattr(self, "_audio_check_state", None)
        if st is None:
            return
        try:
            if st["ti"] < len(st["types"]):
                tp = st["types"][st["ti"]]
                steps = None
                if hasattr(self, "bc_steps"):
                    steps = self.bc_steps.get(tp)
                if not steps:
                    steps = self.get_default_steps(tp)
                for step in steps:
                    st["total"] += 1
                    try:
                        content = step[1] if isinstance(step, (list, tuple)) and len(step) >= 2 else step
                        if isinstance(content, (list, tuple)) and len(content) >= 2:
                            content = content[1]
                        parsed = self.parse_step(content)
                        if parsed is None:
                            st["ok"] += 1
                            continue
                        kind, value = parsed
                        if kind == "var":
                            # 变量由车次值动态决定，配置本身视为有效
                            st["ok"] += 1
                            continue
                        if kind == "__path__":
                            p = value
                        else:
                            p = self.find_audio_file(kind, value)
                        if p and os.path.exists(p):
                            st["ok"] += 1
                        else:
                            st["missing"].append((tp, f"{kind}/{value}", "文件不存在"))
                    except Exception:
                        st["missing"].append((tp, str(step), "解析异常"))
                st["ti"] += 1
                self.after(5, self._audio_check_step)
                return
            # 额外全局音频配置
            if not st["extras"]:
                try:
                    ex = []
                    if getattr(self, "start_sound_btn", None):
                        ex.append(("开始音", getattr(self, "_start_sound_value", "")))
                    if getattr(self, "end_sound_btn", None):
                        ex.append(("结束音", getattr(self, "_end_sound_value", "")))
                    if getattr(self, "main_audio_entry", None):
                        ex.append(("主界面播放音频", str(self.main_audio_entry.get()).strip()))
                    st["extras"] = ex
                except Exception:
                    st["extras"] = []
            if st["extra_idx"] < len(st["extras"]):
                label, ref = st["extras"][st["extra_idx"]]
                st["extra_idx"] += 1
                if ref and ref not in ("无（点击选择）", ""):
                    st["total"] += 1
                    try:
                        p = self.resolve_audio_path(ref)
                        if p and (p.startswith(("http://", "https://")) or os.path.exists(p)):
                            st["ok"] += 1
                        else:
                            st["missing"].append(("全局", label + ": " + ref, "文件不存在"))
                    except Exception:
                        st["missing"].append(("全局", label + ": " + ref, "解析异常"))
                self.after(5, self._audio_check_step)
                return
        except Exception as e:
            st["missing"].append(("配置", str(e), "检查异常"))
        # 完成
        self._audio_check_state = None
        self._show_audio_check_result(st["total"], st["ok"], st["missing"])

    def _show_audio_check_result(self, total, ok_count, missing):
        """展示语音包体检结果弹窗"""
        try:
            dlg = ctk.CTkToplevel(self)
            dlg.title("语音包体检结果")
            dlg.geometry("660x460")
            dlg.attributes("-topmost", True)
            dlg.transient(self)
            dlg.lift()
            dlg.focus_force()
            dlg.grid_columnconfigure(0, weight=1)
            dlg.grid_rowconfigure(2, weight=1)
            head = f"语音包体检完成：共检查 {total} 项，可用 {ok_count} 项，缺失 {len(missing)} 项"
            ctk.CTkLabel(dlg, text=head, font=ctk.CTkFont(size=14, weight="bold"),
                         text_color=DS["accent"]).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))
            if missing:
                tree = ttk.Treeview(dlg, columns=("所属广播", "引用", "问题"),
                                    show="headings", height=16, style="Sched.Treeview")
                sst = ttk.Style()
                try:
                    sst.theme_use("clam")
                except Exception:
                    pass
                sst.configure("Sched.Treeview", font=(DS["font"], 11), rowheight=26,
                              background=DS["row1"], fieldbackground=DS["row1"],
                              foreground=DS["text"], borderwidth=0)
                sst.map("Sched.Treeview",
                        background=[("selected", DS["row_sel"])],
                        foreground=[("selected", "#ffffff")])
                for i, col in enumerate(("所属广播", "引用", "问题")):
                    tree.heading(col, text=col)
                    tree.column(col, width=[200, 330, 110][i], anchor="center")
                tree.grid(row=2, column=0, sticky="nsew", padx=14, pady=6)
                for tp, ref, why in missing[:500]:
                    tree.insert("", "end", values=(tp, ref, why))
                if len(missing) > 500:
                    ctk.CTkLabel(dlg, text=f"仅显示前 500 条缺失（共 {len(missing)} 条）",
                                 font=ctk.CTkFont(size=11), text_color=DS["text_dim"]).grid(
                        row=1, column=0, sticky="w", padx=14, pady=(2, 0))
            else:
                ctk.CTkLabel(dlg, text="✔ 全部音频文件正常，无缺失", font=ctk.CTkFont(size=13),
                             text_color="#4d4").grid(row=2, column=0, sticky="w", padx=14, pady=6)
            op = ctk.CTkFrame(dlg, fg_color="transparent")
            op.grid(row=3, column=0, sticky="ew", padx=14, pady=(6, 12))
            ctk.CTkButton(op, text="关闭", width=90, height=32,
                          fg_color=DS["btn"], hover_color=DS["btn_hover"],
                          command=dlg.destroy).pack(side="right", padx=2)
            self.set_status("语音包体检完成")
        except Exception:
            pass

    def _gs_build_about(self, content):
        """关于：版本/版权 + 推荐电脑配置 + 流畅运行配置 + 当前电脑配置（动态读取本机）"""
        import platform as _plat
        f = ctk.CTkScrollableFrame(content, fg_color="transparent")
        f.grid(row=0, column=0, sticky="nsew")
        f.grid_columnconfigure(0, weight=1)
        self._gs_frames["about"] = f
        _r = [0]

        def add(txt, color=None, big=False, dim=False):
            _r[0] += 1
            ctk.CTkLabel(
                f, text=txt,
                font=ctk.CTkFont(size=14 if big else 12, weight="bold" if big else "normal"),
                text_color=color or (DS["text_dim"] if dim else DS["text"]),
                anchor="w", justify="left").grid(row=_r[0], column=0, sticky="w", padx=14,
                                                 pady=(10 if big else 3))

        # 基础信息
        add("版本：旅客服务智能管理广播系统 v26.10.2", big=True, color=DS["accent"])
        add("版权：个人无版权，公共使用许可")
        add("许可：公共使用许可")
        add("技术支持：AI助手技术支持：豆包、DeepSeek 国内 AI 模型", dim=True)

        # 推荐电脑配置（先展示）
        add("── 推荐电脑配置 ──", big=True, color=DS["accent"])
        add("操作系统：Windows 10/11 64 位")
        add("处理器：四核 2.0 GHz 及以上")
        add("内存：8 GB 及以上")
        add("磁盘：10 GB 空闲空间")
        add("显示：1920×1080 及以上，支持双屏/副屏大屏")
        add("声卡：独立或集成声卡 + 音箱")

        # 流畅运行配置（后展示）
        add("── 流畅运行配置 ──", big=True, color=DS["accent"])
        add("操作系统：Windows 10/11 64 位")
        add("处理器：双核 1.6 GHz 及以上")
        add("内存：4 GB")
        add("磁盘：2 GB 空闲空间")
        add("显示：1920×1080")
        add("声卡：集成声卡 + 音箱")

        # 当前电脑配置（动态读取本机）
        add("── 当前电脑配置 ──", big=True, color=DS["accent"])
        try:
            _os_txt = f"{_plat.system()} {_plat.release()}（{_plat.machine()}）"
        except Exception:
            _os_txt = "Windows"
        try:
            _cpu_txt = (_plat.processor() or "未知型号") + " · " + str(os.cpu_count() or 0) + " 核心"
        except Exception:
            _cpu_txt = "未知"
        try:
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            _ms_ = _MS()
            _ms_.dwLength = ctypes.sizeof(_MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(_ms_))
            _mem_txt = f"{_ms_.ullTotalPhys / (1024**3):.1f} GB（可用 {_ms_.ullAvailPhys / (1024**3):.1f} GB）"
        except Exception:
            _mem_txt = "未知"
        try:
            _scr_txt = f"{self.winfo_screenwidth()}×{self.winfo_screenheight()}"
        except Exception:
            _scr_txt = "未知"
        add(f"操作系统：{_os_txt}")
        add(f"处理器：{_cpu_txt}")
        add(f"内存：{_mem_txt}")
        add(f"显示：{_scr_txt}")

    def _gs_switch(self, cat):
        """切换全局设置分类"""
        for k, f in self._gs_frames.items():
            if k == cat:
                f.grid()
            else:
                f.grid_remove()
        for k, b in self._gs_nav_btns.items():
            if k == cat:
                b.configure(fg_color=DS["accent"], text_color="#ffffff")
            else:
                b.configure(fg_color=DS["btn"], text_color=DS["text"])

    def _sys_cfg_file(self):
        return os.path.join(get_project_root(), "system_config.json")

    def load_sys_config(self):
        try:
            with open(self._sys_cfg_file(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_sys_config(self, cfg):
        """保存系统配置：与磁盘旧配置合并，保留本界面未暴露的键（夜间/自动广播/未来扩展）"""
        try:
            _old = self.load_sys_config()
            if isinstance(_old, dict):
                _old.update(cfg or {})
                cfg = _old
        except Exception:
            pass
        with open(self._sys_cfg_file(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    def _effective_volume(self):
        """实际播放音量（0-1）：主音量 × 夜间时段调节（夜间自动降低/静音）"""
        try:
            cfg = self.load_sys_config()
        except Exception:
            cfg = {}
        try:
            vol = max(0, min(100, int(cfg.get("master_volume", 80) or 80)))
        except Exception:
            vol = 80
        if cfg.get("night_mute", False):
            try:
                ns = str(cfg.get("night_start", "23:00") or "23:00").strip()
                ne = str(cfg.get("night_end", "06:00") or "06:00").strip()
                nsh, nsm = map(int, ns.split(":"))
                neh, nem = map(int, ne.split(":"))
                now = time.localtime()
                now_min = now.tm_hour * 60 + now.tm_min
                ns_min = nsh * 60 + nsm
                ne_min = neh * 60 + nem
                # 支持跨天时段（如 23:00-06:00）
                in_night = (ns_min <= ne_min and ns_min <= now_min < ne_min) or \
                           (ns_min > ne_min and (now_min >= ns_min or now_min < ne_min))
                if in_night:
                    try:
                        nv = max(0, min(100, int(cfg.get("night_volume", 30) or 30)))
                    except Exception:
                        nv = 30
                    vol = min(vol, nv)
            except Exception:
                pass
        return vol / 100.0

    def _gs_load(self):
        """从 system_config.json 回读填充控件"""
        cfg = self.load_sys_config()
        for key, w in self._gs_fields.items():
            if key not in cfg:
                continue
            val = cfg[key]
            try:
                if isinstance(w, ctk.CTkComboBox):
                    w.set(str(val))
                elif isinstance(w, ctk.CTkSwitch):
                    if val:
                        w.select()
                    else:
                        w.deselect()
                elif isinstance(w, ctk.CTkEntry):
                    w.delete(0, "end")
                    w.insert(0, str(val))
            except Exception:
                pass

    def _gs_collect(self):
        cfg = {}
        for key, w in self._gs_fields.items():
            try:
                if isinstance(w, ctk.CTkComboBox):
                    cfg[key] = w.get()
                elif isinstance(w, ctk.CTkSwitch):
                    cfg[key] = bool(w.get())
                elif isinstance(w, ctk.CTkEntry):
                    cfg[key] = w.get().strip()
            except Exception:
                pass
        return cfg

    def _gs_save(self):
        try:
            cfg = self._gs_collect()
            self.save_sys_config(cfg)
            # 立即生效：站名同步到车站设置/大屏
            if "station_name" in cfg and hasattr(self, "station_entry"):
                try:
                    self.station_entry.delete(0, "end")
                    self.station_entry.insert(0, cfg["station_name"])
                except Exception:
                    pass
            self.set_status("全局设置已保存并生效")
        except Exception as e:
            self.set_status(f"全局设置保存失败: {e}")

    def _gs_cancel(self):
        self._gs_load()
        self.set_status("已取消更改，恢复为已保存配置")

    def _gs_default(self):
        if not messagebox.askyesno("恢复默认", "确定将全部全局设置恢复为默认值吗？"):
            return
        d = self._gs_defaults
        for key, w in self._gs_fields.items():
            if key not in d:
                continue
            try:
                if isinstance(w, ctk.CTkComboBox):
                    w.set(str(d[key]))
                elif isinstance(w, ctk.CTkSwitch):
                    if d[key]:
                        w.select()
                    else:
                        w.deselect()
                elif isinstance(w, ctk.CTkEntry):
                    w.delete(0, "end")
                    w.insert(0, str(d[key]))
            except Exception:
                pass
        self._gs_save()
        self.set_status("已恢复默认设置")

    def _gs_import(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="导入全局设置", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.save_sys_config(cfg)
            self._gs_load()
            self.set_status(f"配置已导入并生效: {os.path.basename(path)}")
        except Exception as e:
            self.set_status(f"导入失败: {e}")

    def _gs_export(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(title="导出全局设置", defaultextension=".json",
                                            initialfile="系统配置.json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            # 导出完整配置（含界面未展示的夜间/自动广播等键），而不是只导出当前页控件
            cfg = self.load_sys_config()
            cfg.update(self._gs_collect())
            self.save_sys_config(cfg)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            self.set_status(f"配置已导出: {os.path.basename(path)}")
        except Exception as e:
            self.set_status(f"导出失败: {e}")

    def _gs_test_audio(self):
        import threading
        def _t():
            try:
                # 用第一个车次做测试，避免无车次时播出残缺内容
                if not self.current_train:
                    _kids = self.bc_train_tree.get_children()
                    if _kids:
                        self._select_train_in_main(str(self.bc_train_tree.item(_kids[0])["values"][0]))
                al = self.build_audio_list_from_steps("检票预告")
                if al:
                    self.play_concat_audio(al, btype="音频输出测试", source="测试")
                    self.set_status("音频输出测试：正在播放")
                    return
            except Exception:
                pass
            self.set_status("音频输出测试：无可用音频（请检查语音包与检票预告配置）")
        threading.Thread(target=_t, daemon=True).start()

    def _gs_test_network(self):
        import socket
        try:
            h = self._gs_fields.get("server_host")
            p = self._gs_fields.get("server_port")
            host = h.get().strip() if h else "127.0.0.1"
            port = int(p.get().strip()) if p else 8888
            # 旧版本默认端口 27890 是客户端自身监听端口，连自己必然“通过”但后端没通；
            # 后端实际是 8888，遇到旧默认值自动纠正并把输入框一起改掉。
            if port == 27890:
                port = 8888
                if p is not None:
                    p.delete(0, "end")
                    p.insert(0, "8888")
            s = socket.create_connection((host, port), timeout=2)
            s.close()
            self.set_status(f"网络测试通过：{host}:{port} 可连接")
        except Exception as e:
            self.set_status(f"网络测试失败：{e}")

    def _gs_test_dev(self):
        self.set_status("终端测试：已向默认终端发送测试指令（模拟）")

    def _gs_test_all(self):
        self._gs_test_network()
        self._gs_save()
        import threading
        threading.Thread(target=self._gs_test_audio, daemon=True).start()
        self.set_status("一键测试已执行：网络 + 配置保存 + 音频")

    def _gs_export_log(self):
        from tkinter import filedialog
        import shutil
        # 广播历史 + 运行日志都可能存在；优先导出广播历史（真实产生的内容）
        src = None
        for name in ("bcast_log.json", "bcast.log", "main_ui.log", "app.log"):
            cand = os.path.join(get_project_root(), name)
            if os.path.exists(cand):
                src = cand
                break
        if src is None:
            self.set_status("暂无日志：尚未产生广播记录，也没有运行日志文件")
            return
        path = filedialog.asksaveasfilename(title="导出日志", defaultextension=os.path.splitext(src)[1] or ".log",
                                            initialfile="系统日志" + os.path.splitext(src)[1],
                                            filetypes=[("日志/JSON", "*.log;*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            shutil.copy(src, path)
            self.set_status(f"日志已导出: {os.path.basename(path)}")
        except Exception as e:
            self.set_status(f"导出日志失败: {e}")

    def _gs_backup(self):
        import shutil
        try:
            bkdir = os.path.join(get_project_root(), "config_backup")
            os.makedirs(bkdir, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            src = self._sys_cfg_file()
            if os.path.exists(src):
                shutil.copy(src, os.path.join(bkdir, f"system_config_{ts}.json"))
                self.set_status(f"配置已备份: config_backup/system_config_{ts}.json")
            else:
                self.save_sys_config(self._gs_defaults)
                shutil.copy(self._sys_cfg_file(), os.path.join(bkdir, f"system_config_{ts}.json"))
                self.set_status("已创建默认配置并备份")
        except Exception as e:
            self.set_status(f"备份失败: {e}")

    def _gs_restore(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="从备份恢复",
                                          initialdir=os.path.join(get_project_root(), "config_backup"),
                                          filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.save_sys_config(cfg)
            self._gs_load()
            self.set_status(f"已从备份恢复: {os.path.basename(path)}")
        except Exception as e:
            self.set_status(f"恢复失败: {e}")

    def _gs_clear_cache(self):
        import shutil
        try:
            for d in ("__pycache__",):
                pp = os.path.join(get_project_root(), d)
                if os.path.isdir(pp):
                    shutil.rmtree(pp, ignore_errors=True)
            self.set_status("缓存已清理")
        except Exception as e:
            self.set_status(f"清理失败: {e}")

    def _gs_rebuild_icon(self):
        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x8000000, 0, None, None)
            self.set_status("已触发 Windows 图标缓存刷新（如仍异常请重启资源管理器）")
        except Exception as e:
            self.set_status(f"刷新图标缓存失败: {e}")

    def _gs_check_update(self):
        ver = self._gs_defaults.get("version", "26.10.2")
        self.set_status(f"当前版本 v{ver}（离线部署版，暂无更新源）")


    # ---------- 广播步骤：文件真实位置 / 缺失占位 ----------
    def _audio_file_readable(self, path):
        """文件存在、非空且能实际打开（用于区分“找不到/打不开”）。"""
        try:
            if not path or not os.path.isfile(path):
                return False
            if os.path.getsize(path) <= 0:
                return False
            with open(path, "rb") as f:
                f.read(8)
            return True
        except Exception:
            return False

    def _resolve_step_audio(self, content):
        """把步骤内容解析为真实存在的音频绝对路径；变量/空/缺失返回 None。"""
        s = str(content or "").strip()
        if not s or (s.startswith("{") and s.endswith("}")):
            return None
        try:
            parsed = self.parse_step(s)
        except Exception:
            parsed = None
        if parsed:
            kind, value = parsed
            if kind == "__path__":
                return value if self._audio_file_readable(value) else None
            if kind != "var":
                try:
                    found = self.find_audio_file(kind, value, fuzzy=True)
                except Exception:
                    found = None
                if found and self._audio_file_readable(found):
                    return found
        return None

    def _step_display(self, content):
        """步骤表显示文本：文件显示真实位置；找不到/打不开显示“点击添加文件”。"""
        s = str(content or "").strip()
        if s.startswith("{") and s.endswith("}"):
            return s
        p = self._resolve_step_audio(s)
        if p:
            try:
                rel = os.path.relpath(p, AUDIO_DIR)
                if not rel.startswith(".."):
                    return rel.replace("/", "\\")
            except Exception:
                pass
            return p
        return "点击添加文件"

    def _step_insert(self, index, num, content, speed="1.00x", iid=None):
        """插入步骤行，并把原始内容保存在隐藏映射中（显示文本可替换而不丢配置）。"""
        if not hasattr(self, "_step_raw"):
            self._step_raw = {}
        kw = {"values": (str(num), self._step_display(content), str(speed))}
        if iid:
            kw["iid"] = iid
        new_iid = self.step_tree.insert("", index, **kw)
        self._step_raw[new_iid] = str(content or "")
        return new_iid

    def _step_raw_value(self, iid, vals):
        """读取步骤原始内容；显示占位符时绝不能被当成配置写回。"""
        if hasattr(self, "_step_raw") and iid in self._step_raw:
            return self._step_raw[iid]
        return str(vals[1]) if len(vals) > 1 else ""

    def _step_refresh_display(self, iid, speed=None):
        """根据原始内容刷新单行显示（选完文件/编辑后调用）。"""
        try:
            vals = list(self.step_tree.item(iid)["values"])
            raw = self._step_raw_value(iid, vals)
            spd = str(speed if speed is not None else (vals[2] if len(vals) > 2 else "1.00x"))
            self.step_tree.item(iid, values=(str(vals[0]), self._step_display(raw), spd))
        except Exception:
            pass

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
        ctk.CTkButton(map_btn_frame, text="浏览设置", width=100, height=28,
                     fg_color=DS["btn"], hover_color=DS["btn_hover"],
                     command=self.browse_map_audio).pack(side="left", padx=2)
        ctk.CTkButton(map_btn_frame, text="恢复默认", width=100, height=28,
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
        self._start_sound_value = ""

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
        self._end_sound_value = ""

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

        # 每条广播间隔（队列播放时，两条之间间隔 N 秒再播下一条）
        gap_row = ctk.CTkFrame(sound_frame, fg_color="transparent")
        gap_row.pack(fill="x", padx=10, pady=(2, 4))
        ctk.CTkLabel(gap_row, text="每条广播间隔(秒):", width=88,
                     font=ctk.CTkFont(size=11), text_color="#aaa").pack(side="left")
        self.bcast_gap_entry = ctk.CTkEntry(gap_row, width=70, height=26,
                                            font=ctk.CTkFont(size=11))
        self.bcast_gap_entry.insert(0, "0")
        self.bcast_gap_entry.pack(side="left", padx=(5, 5))
        ctk.CTkLabel(gap_row, text="0=无间隔；队列播放时每条之间隔 N 秒（紧急广播不受影响）",
                     font=ctk.CTkFont(size=10), text_color=DS["text_dim"]).pack(side="left")

        def _apply_bcast_gap(_e=None):
            """间隔秒数改动：立即生效 + 自动保存"""
            self._apply_bcast_gap()
        self.bcast_gap_entry.bind("<Return>", _apply_bcast_gap)
        self.bcast_gap_entry.bind("<FocusOut>", _apply_bcast_gap)

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

        # ===== 通用音频配置（仅保留主界面手动播放音频）=====
        gen_frame = ctk.CTkFrame(map_frame, fg_color=DS["panel2"], corner_radius=8)
        gen_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(gen_frame, text="主界面播放音频（手动播放时使用）",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=DS["accent"]).pack(anchor="w", padx=10, pady=(10, 5))

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
        type_box = ctk.CTkFrame(type_frame, fg_color="transparent")
        type_box.pack(fill="x", padx=10, pady=(0, 5))
        self.type_tree.pack(side="left", fill="both", expand=True)
        type_vsb = ttk.Scrollbar(type_box, orient="vertical", command=self.type_tree.yview)
        type_vsb.pack(side="right", fill="y")
        self.type_tree.configure(yscrollcommand=type_vsb.set)
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
        ctk.CTkButton(type_btn, text="推荐排序", width=96, height=26, fg_color=DS["btn_primary"],
                      hover_color=DS["btn_primary_hover"], font=ctk.CTkFont(size=11),
                      command=self.sort_bcast_types).pack(side="left", padx=2)

        # ===== 手动播放（排序模式）：自定义顺序播放 =====
        manual_frame = ctk.CTkFrame(map_frame, fg_color=DS["panel2"], corner_radius=8)
        manual_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkLabel(manual_frame, text="手动播放（排序模式）",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=DS["accent"]).pack(anchor="w", padx=10, pady=(10, 5))
        ctk.CTkLabel(manual_frame, text="自定义播放顺序：每一步可指定音频文件/语速，排完按顺序播放",
                     font=ctk.CTkFont(size=10), text_color=DS["text_dim"]).pack(anchor="w", padx=10, pady=(0, 6))
        ctk.CTkButton(manual_frame, text="打开手动播放排序窗口", height=32,
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

        ctk.CTkLabel(tpl_frame, text="广播步骤（按实际文件位置顺序播放）",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=DS["accent"]).pack(anchor="w", padx=15, pady=(0, 10))

        ctk.CTkLabel(tpl_frame, text="每行一步，按列表从上到下播放；文件列显示真实位置，找不到或打不开显示“点击添加文件”。{发站}{到站}{车次} 是变量。",
                    font=ctk.CTkFont(size=11), text_color=DS["text_dim"]).pack(anchor="w", padx=15, pady=(0, 10))

        # 步骤列表（第 3 列 = 本步语速，1.00x=跟随整体语速）
        step_cols = ("顺序", "音频文件", "语速")
        step_box = ctk.CTkFrame(tpl_frame, fg_color="transparent")
        step_box.pack(fill="x", padx=15, pady=(0, 5))
        self.step_tree = ttk.Treeview(step_box, columns=step_cols, show="headings", height=10)
        self.step_tree.heading("顺序", text="顺序")
        self.step_tree.heading("音频文件", text="音频文件真实位置")
        self.step_tree.heading("语速", text="语速")
        self.step_tree.column("顺序", width=48, anchor="center")
        self.step_tree.column("音频文件", width=200, anchor="w")
        self.step_tree.column("语速", width=52, anchor="center")
        self.step_tree.pack(side="left", fill="both", expand=True)
        step_vsb = ttk.Scrollbar(step_box, orient="vertical", command=self.step_tree.yview)
        step_vsb.pack(side="right", fill="y")
        self.step_tree.configure(yscrollcommand=step_vsb.set)
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
            self._step_insert("end", num, content, "1.00x")
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
        self._step_insert("end", "新", "", "1.00x")
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
            self._step_insert(idx + 1, "新", text, "1.00x")
        else:
            self._step_insert("end", "新", text, "1.00x")
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
        old_raw = self._step_raw_value(sel[0], vals)
        old_speed = str(vals[2]) if len(vals) > 2 else "1.00x"
        new = simpledialog.askstring("编辑步骤",
                                     f"步骤内容（{vals[0]}）：\n{{发站}}{{到站}}{{车次}}{{检票口}}{{站台}}{{停靠站台}} 是变量，也可填音频路径",
                                     initialvalue=str(old_raw), parent=self)
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
            self._step_raw[sel[0]] = str(new.strip())
            self._step_refresh_display(sel[0], spd)
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
            steps.append([str(vals[0]), self._step_raw_value(child, vals), str(spd)])
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
            raw = self._step_raw_value(child, vals)
            self.step_tree.item(child, values=(str(i+1), self._step_display(raw), spd))
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
        self._select_type_in_tree(cur)
        self.save_bc_settings(silent=True)
        self.set_status(f"类型顺序已更新：{cur}")

    def _select_type_in_tree(self, name):
        """在广播类型列表中选中指定类型（刷新后保持选中，方便连续上移/下移）"""
        try:
            for c in self.type_tree.get_children():
                if str(self.type_tree.item(c)["values"][0]) == str(name):
                    self.type_tree.selection_set(c)
                    self.type_tree.see(c)
                    break
        except Exception:
            pass

    def sort_bcast_types(self):
        """按内置推荐顺序重排全部广播类型：检票 → 晚点 → 停运 → 其他，自定义类型稳定排最后。"""
        types = self.get_bcast_types()
        ordered = sorted(types, key=bc_type_sort_key)
        if ordered == types:
            self.set_status("广播类型已是推荐顺序，无需调整")
            return
        self._bcast_types = ordered
        self.refresh_type_combos()
        self.save_bc_settings(silent=True)
        self.set_status("广播类型已按推荐顺序重排并保存（检票 → 晚点 → 停运 → 其他）")

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
        """每种广播类型的默认步骤：优先读取 bcast_config.json 中已配置的真实语音包步骤，
        避免代码里的旧路径（其他/紧急广播等）与实际语音包不一致导致“缺音频”。"""
        try:
            _p = os.path.join(get_project_root(), "bcast_config.json")
            if os.path.exists(_p):
                with open(_p, "r", encoding="utf-8") as _f:
                    _st = (json.load(_f).get("steps") or {}).get(choice)
                if _st:
                    return [[str(x[0]), str(x[1]), (str(x[2]) if len(x) > 2 else "1.00x")] for x in _st]
        except Exception:
            pass
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
            "紧急-列车晚点·已知时间": [
                ("1", "晚点/1各位旅客请注意"), ("2", "晚点/2由"), ("3", "{发站}"),
                ("4", "晚点/3开往"), ("5", "{到站}"), ("6", "晚点/4的"),
                ("7", "{车次}"), ("8", "晚点/5次列车"), ("9", "晚点/8预计晚点"),
                ("10", "{晚点时间}"), ("11", "晚点/9分钟"),
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
                cur_steps.append([str(vals[0]), self._step_raw_value(child, vals), str(spd)])
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
        self._step_raw = {}
        for s in steps:
            if isinstance(s, (list, tuple)) and len(s) >= 3:
                self._step_insert("end", s[0], s[1], s[2])
            else:
                num, content = s[0], s[1]
                self._step_insert("end", num, content, "1.00x")
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
                self._step_raw[sel[0]] = str(rel)
                self._step_refresh_display(sel[0], spd)
                self.renumber_steps()
                self.sync_steps_to_memory()
                self.save_bc_settings(silent=True)
                self.set_status(f"已选择：{rel}（已自动保存）")
            else:
                self.set_status(f"已选择：{rel}（未选中步骤行）")

    def _set_sound_path(self, attr, path, empty_text="点击添加文件"):
        """更新开始音/结束音按钮：显示真实文件位置，缺失/打不开显示占位文字。"""
        path = str(path or "").strip()
        setattr(self, attr, path)
        btn = self.start_sound_btn if attr == "_start_sound_value" else self.end_sound_btn
        if not path:
            btn.configure(text=empty_text)
        else:
            btn.configure(text=self._step_display(path))

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
            self._set_sound_path("_start_sound_value", rel)
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
            self._set_sound_path("_end_sound_value", rel)
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
            cfg["start_sound"] = getattr(self, "_start_sound_value", "")
            cfg["end_sound"] = getattr(self, "_end_sound_value", "")
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

    # ===== 主界面播放音频 =====
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
        self.main_audio_entry.delete(0, "end")
        self.set_status("已恢复默认音频（主界面播放音频=空）")

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
        self._stop_flag = False   # 必须复位：上次“停止”留下的标志会让试听刚打开就关闭

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
                elif value in ("晚点时间", "晚点小时", "晚点分钟"):
                    # 晚点时间=分钟数（兼容旧配置）；晚点小时/晚点分钟=对应字段（空则不读对应单位）
                    if value == "晚点小时":
                        tv = str(getattr(self, "_delay_hour", "") or "").strip()
                    elif value == "晚点分钟":
                        tv = str(getattr(self, "_delay_min", "") or "").strip()
                    else:
                        tv = str(values.get("delay") or "").strip()
                    if tv:
                        for c in tv:
                            if c.isdigit():
                                _mapped = self.map_lookup(c, "")
                                if _mapped:
                                    _ra = self.resolve_map_audio(_mapped)
                                    if _ra:
                                        audio_list.append((_ra[0], _ra[1], step_speed, True))
                                        continue
                                audio_list.append((self.get_var_dir("数字"), c, step_speed, True))
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
        # 测试播放优先用当前选中车次，其次用列表第一趟真实车次；没有车次就明确提示，不用假车次
        tv = None
        if self.current_train and self.current_train.get("no"):
            tv = dict(self.current_train)
        else:
            _kids = self.bc_train_tree.get_children()
            if _kids:
                _v = self.bc_train_tree.item(_kids[0])["values"]
                if _v:
                    tv = self._train_values_by_no(str(_v[0]))
        if not tv:
            self.set_status("测试播放失败：请先添加车次并选择")
            return
        audio_list = self.resolve_audio_items(tree_steps, tv)

        if not audio_list:
            self.set_status("没有可播放的步骤（请先添加步骤）")
            self.bc_status_dot.configure(text="● 就绪", text_color="#4a4")
            return

        # 无缝拼接播放（自动带开始音/结束音/语速）
        self.play_concat_audio(audio_list, btype="手动播放")

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
        ctk.CTkLabel(toolbar_inner, text="广播控制台", font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=DS["accent"]).pack(side="left", padx=(5, 20))

        # 中间：快捷按钮
        btn_style_tb = {"width": 80, "height": 32, "font": ctk.CTkFont(size=12)}

        ctk.CTkButton(toolbar_inner, text="+ 添车次", fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                     command=self.add_train_dialog, **btn_style_tb).pack(side="left", padx=3)

        ctk.CTkButton(toolbar_inner, text="- 删车次", fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                     command=self.del_selected_train, **btn_style_tb).pack(side="left", padx=3)

        ctk.CTkButton(toolbar_inner, text="刷新", fg_color=DS["btn"], hover_color=DS["btn_hover"],
                     command=self.refresh_trains, **btn_style_tb).pack(side="left", padx=3)

        ctk.CTkButton(toolbar_inner, text="批量导入", fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                     command=self.import_trains_csv, **btn_style_tb).pack(side="left", padx=3)

        ctk.CTkButton(toolbar_inner, text="停止播放", fg_color="#555", hover_color="#777",
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

        ctk.CTkButton(right_frame, text="检票预告", fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                     command=self.bcast_ticket_preview, **btn_style_big).pack(fill="x", padx=12, pady=4)

        ctk.CTkButton(right_frame, text="开始检票", fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                     command=self.bcast_ticket_start, **btn_style_big).pack(fill="x", padx=12, pady=4)

        ctk.CTkButton(right_frame, text="停止检票", fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
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
                ctk.CTkButton(frame, text=f"紧急 · {_label}",
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

    def sort_train_tree(self):
        """按当前排序模式重排主车次列表（增量更新，不整表删除重建）。
        保持行 iid、选中项和滚动位置，状态变化时只改单元格，不产生“乱跳”。"""
        try:
            tree = self.bc_train_tree
            children = list(tree.get_children())
            if not children:
                return
            existing = {}
            for c in children:
                vals = list(tree.item(c)["values"])
                vals = vals + [""] * (9 - len(vals)) if len(vals) < 9 else vals[:9]
                key = str(vals[0]).strip()
                if key:
                    existing[key] = (c, vals)

            _smin = 5
            if hasattr(self, "stop_min_entry"):
                try:
                    _smin = max(1, int(float(self.stop_min_entry.get().strip() or "5")))
                except Exception:
                    _smin = 5

            # 以现有行数据为源，按统一规则排序（时间模式下状态变化不影响位置）
            rows = self._screen_sorted_rows([v for _, v in existing.values()], _smin)
            for _r in rows:
                if len(_r) > 7:
                    _r[7] = effective_train_status(_r, _smin)
            desired_keys = [str(r[0]).strip() for r in rows]

            sel_ids = [c for c in tree.selection() if tree.exists(c)]
            yview = tree.yview()

            # 删除已不存在的车次
            for key, (iid, _vals) in list(existing.items()):
                if key not in desired_keys:
                    try:
                        tree.delete(iid)
                    except Exception:
                        pass
                    existing.pop(key, None)

            # 更新已有行（仅内容变化时写入），缺失行追加到末尾
            ordered_iids = []
            for vals in rows:
                key = str(vals[0]).strip()
                if key in existing:
                    iid, _old = existing[key]
                    cur = list(tree.item(iid)["values"])
                    cur = cur + [""] * (9 - len(cur)) if len(cur) < 9 else cur[:9]
                    if tuple(cur) != tuple(vals):
                        tree.item(iid, values=tuple(vals))
                else:
                    iid = tree.insert("", "end", values=tuple(vals))
                    existing[key] = (iid, list(vals))
                ordered_iids.append(iid)

            # 只有顺序确实变化才 move，避免每次刷新触发视觉抖动
            current_order = [c for c in tree.get_children() if c in set(ordered_iids)]
            if current_order != ordered_iids:
                for idx, iid in enumerate(ordered_iids):
                    tree.move(iid, "", idx)

            zebra(tree)
            self.apply_train_status_colors()

            # 恢复选中与滚动位置；只有选中真的变化时才重设，避免每次刷新触发选中行重绘/详情区重载
            valid_sel = [c for c in sel_ids if tree.exists(c)]
            if valid_sel and tuple(tree.selection()) != tuple(valid_sel):
                tree.selection_set(valid_sel)
            if valid_sel:
                try:
                    if not tree.bbox(valid_sel[0]):
                        tree.see(valid_sel[0])
                except Exception:
                    pass
            try:
                if abs(tree.yview()[0] - yview[0]) > 0.0005:
                    tree.yview_moveto(yview[0])
            except Exception:
                pass
        except Exception as _e:
            self.set_status(f"车次列表刷新失败：{_e}")

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
            # 防重复：已存在的车次跳过（即使调用方未清空树，也不会重复插入污染数据）
            existing = set()
            for c in self.bc_train_tree.get_children():
                try:
                    existing.add(str(self.bc_train_tree.item(c)["values"][0]))
                except Exception:
                    pass
            for r in rows:
                rr = list(r)
                if len(rr) < 9:
                    rr.append("--:--")  # 旧数据无到点字段，补默认值
                if str(rr[0]) in existing:
                    continue
                self.bc_train_tree.insert("", "end", values=tuple(rr))
                existing.add(str(rr[0]))
            self.sort_train_tree()
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
        dlg.geometry("400x500")
        dlg.transient(self)
        dlg.attributes("-topmost", True)   # 新弹窗默认置顶
        dlg.lift()                         # 发起时直接提到最前
        dlg.grab_set()
        dlg.configure(fg_color=DS["panel"])

        ctk.CTkLabel(dlg, text="添加新车次", font=ctk.CTkFont(size=15, weight="bold"),
                    text_color=DS["accent"]).grid(row=0, column=0, columnspan=3, padx=10, pady=(12, 8))

        labels = ["车次号", "类型", "发站", "到站", "开点", "检票口", "站台", "状态", "到点"]
        defaults = ["", "高铁", "", "", "", "A1", "", "待检票", "--:--"]
        fields = {}
        for i, (lab, dft) in enumerate(zip(labels, defaults)):
            ctk.CTkLabel(dlg, text=lab + ":", font=ctk.CTkFont(size=12),
                        text_color=DS["text_dim"]).grid(row=i + 1, column=0, sticky="w", padx=(12, 4), pady=4)
            e = ctk.CTkEntry(dlg, font=ctk.CTkFont(size=12),
                            placeholder_text=dft if dft else f"请输入{lab}")
            e.grid(row=i + 1, column=1, columnspan=2, sticky="ew", padx=4, pady=4)
            fields[lab] = e

        def on_ok():
            try:
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
                if self._train_no_exists(no):
                    messagebox.showerror("车次重复", f"车次 {no} 已存在，请勿重复添加。", parent=dlg)
                    return
                self.bc_train_tree.insert("", "end", values=row)
                self.sort_train_tree()
                zebra(self.bc_train_tree)
                self.save_trains_data()
                self.load_trains()   # 同步车辆管理面板，立即可见
                self.set_status(f"已添加车次：{no}")
                self._train_dialog = None
                dlg.destroy()
            except Exception as _e:
                self.set_status(f"添加失败：{_e}")

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

    def update_train_dialog(self):
        """更新车次对话框：预填选中车次，弹窗编辑后保存（数据同源）
        保存时按车次号重新定位行：车辆管理列表每 10 秒自动刷新会重建树行，
        直接用旧行引用会失效导致"点了没反应"，故用车次号重查当前行。"""
        sel = self.train_tree.selection()
        if not sel:
            self.set_status("请先选择要更新的车次")
            return
        if getattr(self, "_train_dialog", None) is not None and self._train_dialog.winfo_exists():
            self._train_dialog.lift()
            self._train_dialog.focus_force()
            return
        vals = list(self.train_tree.item(sel[0])["values"])
        if len(vals) < 9:
            vals = vals + [""] * (9 - len(vals))
        old_no = str(vals[0])   # 记录打开时的车次号，保存时用它定位最新行
        dlg = ctk.CTkToplevel(self)
        self._train_dialog = dlg
        dlg.title("更新车次")
        dlg.geometry("400x500")
        dlg.transient(self)
        dlg.attributes("-topmost", True)   # 新弹窗默认置顶
        dlg.lift()                         # 发起时直接提到最前
        dlg.grab_set()
        dlg.configure(fg_color=DS["panel"])

        ctk.CTkLabel(dlg, text="更新车次信息", font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=DS["accent"]).grid(row=0, column=0, columnspan=3, padx=10, pady=(12, 8))

        labels = ["车次号", "类型", "发站", "到站", "开点", "检票口", "站台", "状态", "到点"]
        fields = {}
        for i, lab in enumerate(labels):
            ctk.CTkLabel(dlg, text=lab + ":", font=ctk.CTkFont(size=12),
                         text_color=DS["text_dim"]).grid(row=i + 1, column=0, sticky="w", padx=(12, 4), pady=4)
            e = ctk.CTkEntry(dlg, font=ctk.CTkFont(size=12))
            e.insert(0, str(vals[i]))
            e.grid(row=i + 1, column=1, columnspan=2, sticky="ew", padx=4, pady=4)
            fields[lab] = e

        def on_ok():
            try:
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
                # 用打开时的车次号重查当前树行（自动刷新后旧行引用已失效）
                target = None
                for _c in self.train_tree.get_children():
                    _vv = self.train_tree.item(_c)["values"]
                    if _vv and str(_vv[0]) == old_no:
                        target = _c
                        break
                if target is None:
                    self.set_status("原车次行已被刷新，请重新选择车次再更新")
                    return
                if self._train_no_exists(no, exclude=old_no):
                    messagebox.showerror("车次重复", f"车次 {no} 已存在，请换一个车次号。", parent=dlg)
                    return
                self.train_tree.item(target, values=row)
                self.sync_train_to_main()
                self.set_status(f"车次 {no} 已更新")
                self._train_dialog = None
                dlg.destroy()
            except Exception as _e:
                self.set_status(f"更新失败：{_e}")

        def on_cancel():
            self._train_dialog = None
            dlg.destroy()

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.grid(row=11, column=0, columnspan=3, pady=(14, 12))
        ctk.CTkButton(btn_row, text="保存修改", width=100, height=32,
                      fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                      command=on_ok).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="取消", width=80, height=32,
                      fg_color=DS["btn_neutral"], hover_color=DS["btn_neutral_hover"],
                      command=on_cancel).pack(side="left", padx=8)

    def _train_auto_refresh(self):
        """车辆管理列表自动刷新：每 10 秒从主界面列表同步（页面可见才刷，保留选中）"""
        try:
            if self.train_panel.winfo_ismapped():
                self.load_trains()
        except Exception:
            pass
        self.after(10000, self._train_auto_refresh)

    def reload_trains_data(self):
        """从 trains.json 增量合并到主列表：不整表清空，刷新时无闪烁。"""
        path = self.get_trains_path()
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                src = json.load(f)
        except Exception as e:
            self.set_status(f"车次读取失败：{e}")
            return False

        rows = []
        seen = set()
        _smin = 5
        if hasattr(self, "stop_min_entry"):
            try:
                _smin = max(1, int(float(self.stop_min_entry.get().strip() or "5")))
            except Exception:
                _smin = 5
        for r in src:
            rr = list(r)
            if len(rr) < 9:
                rr = rr + ["--:--"] * (9 - len(rr))
            key = str(rr[0]).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            # 先把文件里的原始状态换算成界面实际显示状态，再和树里的值比较。
            # 否则每次刷新都会“先写原始状态、再写自动状态”，同一行被改两次，
            # 在 Treeview 上就是肉眼可见的一闪。
            try:
                rr[7] = effective_train_status(rr, _smin)
            except Exception:
                pass
            rows.append(rr[:9])

        tree = self.bc_train_tree
        _before = []
        for _c in tree.get_children():
            try:
                _before.append((_c, tuple(tree.item(_c)["values"]), tuple(tree.item(_c)["tags"])))
            except Exception:
                pass
        existing = {}
        for c in tree.get_children():
            vals = list(tree.item(c)["values"])
            if vals:
                existing[str(vals[0]).strip()] = (c, vals)

        for key in list(existing.keys()):
            if key not in seen:
                try:
                    tree.delete(existing[key][0])
                except Exception:
                    pass
                existing.pop(key, None)

        for rr in rows:
            key = str(rr[0]).strip()
            if key in existing:
                iid, old = existing[key]
                if tuple(old) != tuple(rr):
                    tree.item(iid, values=tuple(rr))
            else:
                tree.insert("", "end", values=tuple(rr))

        self.sort_train_tree()
        _after = []
        for _c in tree.get_children():
            try:
                _after.append((_c, tuple(tree.item(_c)["values"]), tuple(tree.item(_c)["tags"])))
            except Exception:
                pass
        changed = _before != _after
        if getattr(self, "current_train", None):
            no = str(self.current_train.get("no", "") or "").strip()
            if no and no not in seen:
                self.current_train = None
                if hasattr(self, "current_train_label"):
                    self.current_train_label.configure(text="未选择车次")
        return changed

    def refresh_trains(self):
        """刷新车次列表：只更新有变化的单元格，只刷新当前可见的面板。"""
        changed = self.reload_trains_data()
        # 只刷新用户当前看得到的页面，避免隐藏页面重建控件造成整窗重绘闪烁
        try:
            if self.train_panel.winfo_ismapped():
                self.load_trains()
        except Exception:
            pass
        try:
            if self.screen_panel.winfo_ismapped():
                self.refresh_screen(silent=True)
        except Exception:
            pass
        if changed:
            self.set_status("车次列表已刷新")

    def import_trains_csv(self):
        """车次批量导入：CSV/文本文件（一行一车次，9 列：车次/类型/发站/到站/开点/检票口/站台/状态/到点）
        兼容 6 列旧格式（车次/类型/发站/到站/开点/检票口），自动补默认站台/状态/到点"""
        try:
            from tkinter import filedialog
            fp = filedialog.askopenfilename(
                title="选择车次导入文件", parent=self,
                filetypes=[("CSV/文本文件", "*.csv *.txt"), ("所有文件", "*.*")])
            if not fp:
                return
            import csv as _csv
            rows = []
            with open(fp, "r", encoding="utf-8-sig", errors="replace") as f:
                rd = _csv.reader(f)
                for raw in rd:
                    if not raw:
                        continue
                    line = [str(c).strip() for c in raw]
                    if not line or not line[0]:
                        continue
                    # 跳过表头行（首列含"车次"字样）
                    if str(line[0]).lower() in ("车次", "车次号", "车次号/列车") and len(line) > 3:
                        continue
                    if len(line) < 3:
                        continue
                    if len(line) < 9:
                        line = (line + [""] * (9 - len(line)))[:9]
                        if not line[6]:
                            line[6] = "1"
                        if not line[7]:
                            line[7] = "待检票"
                        if not line[8]:
                            line[8] = "--:--"
                    rows.append(line[:9])
            if not rows:
                messagebox.showinfo("批量导入", "文件中没有有效车次数据", parent=self)
                return
            self._import_preview_dialog(rows, fp)
        except Exception as e:
            messagebox.showerror("批量导入失败", f"读取文件失败：{e}", parent=self)

    def _import_preview_dialog(self, rows, fp):
        """批量导入预览确认弹窗"""
        dlg = ctk.CTkToplevel(self)
        self._import_dlg = dlg
        dlg.title("车次批量导入预览")
        dlg.geometry("700x420")
        dlg.attributes("-topmost", True)
        dlg.transient(self)
        dlg.lift()
        dlg.focus_force()
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(dlg, text=f"共读取 {len(rows)} 条车次（来源：{os.path.basename(fp)}）",
                     font=ctk.CTkFont(size=14, weight="bold"), text_color=DS["accent"]).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 4))
        tree = ttk.Treeview(dlg, columns=("车次", "类型", "发站", "到站", "开点", "检票口", "站台", "状态", "到点"),
                            show="headings", height=13, style="Sched.Treeview")
        sst = ttk.Style()
        try:
            sst.theme_use("clam")
        except Exception:
            pass
        sst.configure("Sched.Treeview", font=(DS["font"], 11), rowheight=26,
                      background=DS["row1"], fieldbackground=DS["row1"],
                      foreground=DS["text"], borderwidth=0)
        sst.map("Sched.Treeview",
                background=[("selected", DS["row_sel"])],
                foreground=[("selected", "#ffffff")])
        widths = [90, 60, 80, 80, 70, 70, 60, 80, 70]
        for i, col in enumerate(("车次", "类型", "发站", "到站", "开点", "检票口", "站台", "状态", "到点")):
            tree.heading(col, text=col)
            tree.column(col, width=widths[i], anchor="center")
        tree.grid(row=1, column=0, sticky="nsew", padx=14, pady=6)
        for r in rows[:200]:
            tree.insert("", "end", values=tuple(r))
        if len(rows) > 200:
            ctk.CTkLabel(dlg, text=f"仅预览前 200 条（共 {len(rows)} 条）",
                         font=ctk.CTkFont(size=11), text_color=DS["text_dim"]).grid(
                row=2, column=0, sticky="w", padx=14, pady=(2, 0))
        op = ctk.CTkFrame(dlg, fg_color="transparent")
        op.grid(row=3, column=0, sticky="ew", padx=14, pady=(6, 12))
        ctk.CTkButton(op, text="✔ 确认导入", width=110, height=32,
                      fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                      command=lambda: self._do_import_trains(rows, dlg)).pack(side="left", padx=2)
        ctk.CTkButton(op, text="取消", width=90, height=32,
                      fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      command=dlg.destroy).pack(side="left", padx=2)

    def _do_import_trains(self, rows, dlg):
        """执行批量导入：去重（已存在跳过）→ 插入树 → 持久化 → 刷新车辆管理"""
        try:
            existing = set()
            for c in self.bc_train_tree.get_children():
                try:
                    existing.add(str(self.bc_train_tree.item(c)["values"][0]))
                except Exception:
                    pass
            added = 0
            skipped = 0
            for r in rows:
                no = str(r[0]).strip()
                if not no:
                    continue
                if no in existing:
                    skipped += 1
                    continue
                self.bc_train_tree.insert("", "end", values=tuple(r[:9]))
                existing.add(no)
                added += 1
            if added:
                self.sort_train_tree()
                self.save_trains_data()
                self.load_trains()
            try:
                dlg.destroy()
            except Exception:
                pass
            self.set_status(f"批量导入完成：新增 {added} 条，跳过（已存在/空车次）{skipped} 条")
            messagebox.showinfo("批量导入",
                                f"批量导入完成\n新增：{added} 条\n跳过（已存在/空车次）：{skipped} 条",
                                parent=self)
        except Exception as e:
            messagebox.showerror("批量导入失败", f"导入失败：{e}", parent=self)

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
            self.current_train = None
            self.current_train_label.configure(text="未选择车次")
            zebra(self.bc_train_tree)
            self.sort_train_tree()
            self.save_trains_data()
            self.set_status("已删除车次")
        else:
            self.set_status("请先选择车次")

    def _select_train_in_main(self, no):
        """按车次号选中主列表车次（供全局音频测试/程序内调用），并同步 current_train。"""
        no = str(no or "").strip()
        for c in self.bc_train_tree.get_children():
            vals = list(self.bc_train_tree.item(c)["values"])
            if vals and str(vals[0]).strip() == no:
                self.bc_train_tree.selection_set(c)
                self.bc_train_tree.see(c)
                self.on_train_select(None)
                return True
        return False

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

    def build_audio_list_from_steps(self, type_name, steps_override=None, train_values=None):
        """根据配置步骤（或手动排序步骤） + 车次信息，构建音频片段列表。
        不再用“杭州东/宁波/G1234”测试值兜底：缺字段就跳过对应片段，避免播出假车次。"""
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

        values = dict(train_values if train_values is not None else (self.current_train or {}))
        values.setdefault("delay", getattr(self, "_delay_min", ""))
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
        self.play_concat_audio(audio_list, btype="检票预告")

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
        self.play_concat_audio(audio_list, btype="开始检票")

    def bcast_ticket_stop(self):
        """停止检票：按广播设置里配置的步骤播放"""
        if not self.current_train:
            self.set_status("请先选择车次！")
            return
        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        self.set_status("停止检票")
        if self.current_train:
            self._active_bcast_train = self.current_train["no"]
            # keep=True：停止检票后保持"停止检票"，播放结束不重置
            self._set_train_state(self.current_train["no"], "停止检票", keep=True)
        audio_list = self.build_audio_list_from_steps("停止检票")
        self.play_concat_audio(audio_list, btype="停止检票")

    def _train_no_exists(self, no, exclude=None):
        """车次号是否已存在（exclude=编辑前的车次号，允许保持原号不变）"""
        no = str(no or "").strip()
        ex = str(exclude or "").strip()
        if not no:
            return False
        for c in self.bc_train_tree.get_children():
            v = self.bc_train_tree.item(c)["values"]
            if v and str(v[0]).strip() == no and str(v[0]).strip() != ex:
                return True
        return False

    def _train_values_by_no(self, no):
        """按车次号从主列表取完整车次信息（发站/到站/检票口/站台/开点），取不到返回 None。
        自动广播/定时广播必须用这里的数据，不能再退化成“杭州东→宁波/G1234”测试值。"""
        no = str(no or "").strip()
        if not no:
            return None
        try:
            for c in self.bc_train_tree.get_children():
                vals = list(self.bc_train_tree.item(c)["values"])
                if vals and str(vals[0]).strip() == no:
                    if len(vals) < 9:
                        vals += [""] * (9 - len(vals))
                    return {"no": str(vals[0]).strip(),
                            "from": str(vals[2]).strip(),
                            "to": str(vals[3]).strip(),
                            "dep": str(vals[4]).strip(),
                            "gate": str(vals[5]).strip(),
                            "platform": str(vals[6]).strip()}
        except Exception:
            pass
        return None

    def bcast_emergency(self):
        """紧急广播（列车晚点·通用）"""
        if not self.current_train:
            self.set_status("请先选择车次！")
            return
        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        self.set_status("紧急广播")
        audio_list = self.build_audio_list_from_steps("紧急-列车晚点（通用）")
        self.play_concat_audio(audio_list, emergency=True, btype="紧急-列车晚点（通用）")

    def broadcast_emergency_type(self, emg_type):
        """按类型播放紧急广播：优先使用广播设置里配置的步骤，晚点类型再按输入的小时/分钟补充时间语音。
        晚点/停运/变更站台必须先选车次，避免用测试车次播错内容。"""
        # 需要车次信息的类型：未选车次直接拦截
        if any(k in emg_type for k in ("晚点", "停运", "变更站台")) and not self.current_train:
            self.set_status("请先选择车次！")
            self.bc_status_dot.configure(text="● 系统就绪", text_color="#4d4")
            return

        # 晚点类型：先让用户输入晚点小时/分钟
        if "晚点" in emg_type:
            _ans = self.ask_delay_time()
            if _ans is None:
                self.set_status("已取消：未输入晚点时间")
                self.bc_status_dot.configure(text="● 系统就绪", text_color="#4d4")
                return
            self._delay_hour = str(_ans[0]).strip()
            self._delay_min = str(_ans[1]).strip()

        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        if "晚点" in emg_type:
            _h = str(getattr(self, "_delay_hour", "") or "").strip()
            _m = str(getattr(self, "_delay_min", "") or "").strip()
            _desc = "晚点" + (_h + "小时" if _h else "") + (_m + "分钟" if _m else "")
            if not _h and not _m:
                _desc = "晚点（未输入时间）"
            self.set_status(f"紧急广播：{emg_type}（{_desc}）")
        else:
            self.set_status(f"紧急广播：{emg_type}")

        # 先取完整车次信息，再更新状态（避免状态改动后取到空值）
        values = dict(self.current_train) if self.current_train else {}
        if self.current_train:
            no = self.current_train["no"]
            if "晚点" in emg_type:
                self._set_train_state(no, "晚点", keep=True)
            elif "停运" in emg_type:
                self._set_train_state(no, "停运", keep=True)

        self.sync_steps_to_memory()
        steps = self.bc_steps.get(emg_type) or self.get_default_steps(emg_type)
        if "晚点" in emg_type:
            steps = self._prepare_delay_steps(steps)
            if not steps:
                steps = self._build_delay_known_steps(emg_type)
            audio_list = self.resolve_audio_items(steps, values)
        else:
            audio_list = self.resolve_audio_items(steps, values) if steps else []

        if not audio_list:
            self.set_status(f"紧急广播 {emg_type}：没有可播放的音频，请检查广播设置")
            self.bc_status_dot.configure(text="● 系统就绪", text_color="#4d4")
            return
        self.play_concat_audio(audio_list, emergency=True, btype=emg_type)

    def _prepare_delay_steps(self, steps):
        """把配置步骤中的晚点时间变量展开成 小时/时 + 分钟/分：
        - 兼容旧配置的 {晚点时间}；
        - 已有 {晚点小时}/{晚点分钟} 时按输入值保留，空值连同单位一起跳过；
        - 配置里没有时间占位符但用户输入了时间时，自动补在末尾。"""
        h = str(getattr(self, "_delay_hour", "") or "").strip()
        m = str(getattr(self, "_delay_min", "") or "").strip()
        src = [list(s) for s in (steps or [])]
        out = []
        had_time = any("{晚点" in str(s[1]) for s in src if len(s) > 1)
        i = 0
        while i < len(src):
            s = src[i]
            c = str(s[1]) if len(s) > 1 else ""
            if c == "{晚点时间}":
                if h:
                    out.append(["", "{晚点小时}", "1.00x"])
                    out.append(["", "时间/时", "1.00x"])
                if m:
                    out.append(["", "{晚点分钟}", "1.00x"])
                    out.append(["", "时间/分", "1.00x"])
                # 旧配置在占位符后面还跟了一个固定的“分钟”尾音，已被上面的“时/分”替代，跳过
                if i + 1 < len(src) and str(src[i + 1][1]).endswith("/9分钟"):
                    i += 2
                else:
                    i += 1
                continue
            if c == "{晚点小时}":
                if h:
                    out.append(["", c, s[2] if len(s) > 2 else "1.00x"])
                    if i + 1 < len(src) and "时" in str(src[i + 1][1]):
                        out.append(list(src[i + 1]))
                        i += 1
                i += 1
                continue
            if c == "{晚点分钟}":
                if m:
                    out.append(["", c, s[2] if len(s) > 2 else "1.00x"])
                    if i + 1 < len(src) and "分" in str(src[i + 1][1]):
                        out.append(list(src[i + 1]))
                        i += 1
                i += 1
                continue
            # 未输入时间时，去掉“预计晚点”“分钟”这类无意义的尾句
            if not (h or m) and (str(c).endswith("预计晚点") or str(c).endswith("/9分钟")):
                i += 1
                continue
            out.append(list(s))
            i += 1
        if not had_time and (h or m):
            if h:
                out.append(["", "{晚点小时}", "1.00x"])
                out.append(["", "时间/时", "1.00x"])
            if m:
                out.append(["", "{晚点分钟}", "1.00x"])
                out.append(["", "时间/分", "1.00x"])
        for idx, s in enumerate(out, start=1):
            s[0] = str(idx)
        return out

    def _build_delay_known_steps(self, emg_type):
        """动态构建"紧急-列车晚点·已知时间"播放步骤：
        用"晚点/已知时间晚点/"新语音包；晚点小时/分钟可留空，空则跳过对应单位"""
        reason = ""
        for k in ("天气原因", "设备故障", "线路施工", "自然灾害", "行车事故", "列车超员"):
            if k in emg_type:
                reason = k
                break
        steps = [
            ("1", "晚点/已知时间晚点/1各位旅客请注意"),
            ("2", "晚点/已知时间晚点/2由"),
            ("3", "{发站}"),
            ("4", "晚点/已知时间晚点/3开往"),
            ("5", "{到站}"),
            ("6", "晚点/已知时间晚点/4的"),
            ("7", "{车次}"),
            ("8", "晚点/已知时间晚点/5次列车"),
        ]
        if reason:
            steps.append(("9", f"晚点/已知时间晚点/6因{reason}晚点到"))
        h = str(getattr(self, "_delay_hour", "") or "").strip()
        m = str(getattr(self, "_delay_min", "") or "").strip()
        if h:
            steps.append(("10", "{晚点小时}"))
            steps.append(("11", "时间/时"))
        if m:
            steps.append(("12", "{晚点分钟}"))
            steps.append(("13", "时间/分"))
        return steps

    def ask_delay_time(self):
        """弹窗输入晚点小时/分钟（可留空，留空则不读对应单位）；返回 (hours, minutes) 或 None（取消）"""
        try:
            dlg = ctk.CTkToplevel(self)
            dlg.title("输入晚点时间")
            dlg.geometry("440x300")
            dlg.attributes("-topmost", True)
            dlg.transient(self)
            dlg.lift()
            dlg.focus_force()
            dlg.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(dlg, text="晚点小时（可留空）：", font=ctk.CTkFont(size=13),
                         text_color=DS["text"]).grid(row=0, column=0, sticky="w", padx=16, pady=(18, 6))
            e_h = ctk.CTkEntry(dlg, width=120, font=ctk.CTkFont(size=13), placeholder_text="留空则不读“时”")
            e_h.grid(row=0, column=1, sticky="w", padx=16, pady=(18, 6))
            ctk.CTkLabel(dlg, text="晚点分钟（可留空）：", font=ctk.CTkFont(size=13),
                         text_color=DS["text"]).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 6))
            e_m = ctk.CTkEntry(dlg, width=120, font=ctk.CTkFont(size=13), placeholder_text="留空则不读“分”")
            e_m.grid(row=1, column=1, sticky="w", padx=16, pady=(0, 6))
            ctk.CTkLabel(dlg,
                         text="示例：\n· 小时留空 + 分钟30 → 播“晚点到30分”\n· 小时2 + 分钟留空 → 播“晚点到2时”\n· 都留空 → 只播“晚点到”",
                         font=ctk.CTkFont(size=11), text_color=DS["text_dim"], justify="left"
                         ).grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(6, 6))
            result = {}

            def ok():
                h = e_h.get().strip()
                m = e_m.get().strip()
                if h and not h.isdigit():
                    messagebox.showerror("输入有误", "小时请输入数字（如 2、3）", parent=dlg)
                    return
                if m and not m.isdigit():
                    messagebox.showerror("输入有误", "分钟请输入数字（如 30、45）", parent=dlg)
                    return
                if h and not (0 <= int(h) <= 99):
                    messagebox.showerror("输入有误", "小时请输入 0-99 之间的数字", parent=dlg)
                    return
                if m and not (0 <= int(m) <= 59):
                    messagebox.showerror("输入有误", "分钟请输入 0-59 之间的数字", parent=dlg)
                    return
                result["v"] = (h, m)
                dlg.destroy()

            op = ctk.CTkFrame(dlg, fg_color="transparent")
            op.grid(row=3, column=0, columnspan=2, sticky="e", padx=16, pady=(10, 14))
            ctk.CTkButton(op, text="确定播放", width=100, height=32,
                          fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                          command=ok).pack(side="left", padx=4)
            ctk.CTkButton(op, text="取消", width=80, height=32,
                          fg_color=DS["btn"], hover_color=DS["btn_hover"],
                          command=dlg.destroy).pack(side="left", padx=4)
            dlg.wait_window()
        except Exception:
            return None
        return result.get("v")

    def simple_broadcast(self, name):
        """简单广播：优先按广播设置为该类型配置的步骤播放（带开始/结束音）；
        只有找不到配置时才回退到单个音频文件。"""
        self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        self.set_status(f"正在广播：{name}")
        if name in self.get_bcast_types() or name in getattr(self, "bc_steps", {}):
            audio_list = self.build_audio_list_from_steps(name)
            if audio_list:
                self.play_concat_audio(audio_list, btype=name, source="手动")
                return
            self.set_status(f"广播 {name} 没有可播放的音频，请检查广播设置")
            self.bc_status_dot.configure(text="● 系统就绪", text_color="#4d4")
            return

        # 兼容旧调用：完整音频文件
        audio_map = {
            "检票预告": "其他/旅客们，你们好。由",
            "开始检票": "其他/现在开始检票，请持有该车车票的",
            "停止检票": "紧急广播/停止检票",
            "紧急广播": "紧急广播/列车晚点",
        }
        if name in audio_map:
            self.play_audio_file("media3/" + audio_map[name] + ".mp3")
            self.after(3000, lambda: self.bc_status_dot.configure(text="● 就绪", text_color="#4a4"))
        else:
            self.set_status(f"未知广播类型：{name}")
            self.bc_status_dot.configure(text="● 系统就绪", text_color="#4d4")

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
        dlg.attributes("-topmost", True)   # 新弹窗默认置顶
        dlg.lift()                         # 发起时直接提到最前
        dlg.grab_set()
        dlg.configure(fg_color=DS["panel"])
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(dlg, text="手动播放（排序模式）", font=ctk.CTkFont(size=15, weight="bold"),
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
        ctk.CTkButton(edit_row, text="浏览选择音频...", height=30, fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
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
        ctk.CTkButton(play_row, text="停止", height=34, fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                      font=ctk.CTkFont(size=12), command=self.stop_all_audio).pack(side="left", fill="x", expand=True, padx=(3, 3))
        ctk.CTkButton(play_row, text="保存顺序", height=34, fg_color="#555", hover_color="#777",
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
        self.play_concat_audio(audio_list, btype="手动播放")

    def get_bcast_types(self):
        """广播类型列表：内存优先 → 配置 → 默认（广播设置可自定义排序/添加）"""
        if getattr(self, "_bcast_types", None):
            # 旧缓存也过滤已下线的未知时间类型
            _t = list(self._bcast_types)
            if "紧急-列车晚点·未知时间" in _t:
                _t = [x for x in _t if x != "紧急-列车晚点·未知时间"]
                self._bcast_types = _t
            return list(self._bcast_types)
        try:
            p = self.get_config_path()
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    _c = json.load(f)
                if _c.get("bcast_types"):
                    _t = list(_c["bcast_types"])
                    # 旧配置中已移除的类型过滤（晚点未知时间已按需求下线）
                    _t = [x for x in _t if x != "紧急-列车晚点·未知时间"]
                    # 新功能类型自动补齐（晚点已知时间），保持用户既有排序
                    _ins = [x for x in NEW_LATE_TYPES if x not in _t]
                    if _ins:
                        _anchor = "紧急-列车晚点（通用）"
                        if _anchor in _t:
                            _i = _t.index(_anchor) + 1
                            _t[_i:_i] = _ins
                        else:
                            _t.extend(_ins)
                    self._bcast_types = _t
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
            _sel_name = ""
            try:
                _sel = self.type_tree.selection()
                if _sel:
                    _sel_name = str(self.type_tree.item(_sel[0])["values"][0])
            except Exception:
                pass
            for c in self.type_tree.get_children():
                self.type_tree.delete(c)
            for typ in types:
                self.type_tree.insert("", "end", values=(typ,))
            zebra(self.type_tree)
            if _sel_name:
                self._select_type_in_tree(_sel_name)

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

        # 开始音/结束音（显示真实位置；缺失文件显示“点击添加文件”）
        if "start_sound" in cfg:
            self._set_sound_path("_start_sound_value", cfg.get("start_sound", ""))
        if "end_sound" in cfg:
            self._set_sound_path("_end_sound_value", cfg.get("end_sound", ""),
                                 "无（点击选择）")

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
            _st = str(cfg.get("station_name", "") or "").strip()
            if not _st:
                try:
                    _st = str(self.load_sys_config().get("station_name", "") or "").strip()
                except Exception:
                    _st = ""
            self.station_entry.delete(0, "end")
            self.station_entry.insert(0, _st or "丽水站")
        if hasattr(self, "stop_min_entry"):
            self.stop_min_entry.delete(0, "end")
            self.stop_min_entry.insert(0, str(cfg.get("stop_check_min", 5)))

        # 大屏排序方式（time=按开点时间，status=按状态优先）
        try:
            _sm = str(cfg.get("screen_sort", "time") or "time")
            self._screen_sort_mode = "status" if _sm == "status" else "time"
            if hasattr(self, "screen_sort_menu"):
                self.screen_sort_menu.set("按状态优先" if self._screen_sort_mode == "status" else "按开点时间")
        except Exception:
            pass

        # 启动音频功能已移除：主界面/启动时不再自动播放任何音频
        if hasattr(self, "main_audio_entry"):
            self.main_audio_entry.delete(0, "end")
            self.main_audio_entry.insert(0, cfg.get("main_audio", ""))

        # 每条广播间隔（队列播放时生效）
        try:
            self._bcast_gap = max(0, min(3600, int(float(cfg.get("bcast_gap", 0) or 0))))
        except Exception:
            self._bcast_gap = 0
        if hasattr(self, "bcast_gap_entry"):
            self.bcast_gap_entry.delete(0, "end")
            self.bcast_gap_entry.insert(0, str(self._bcast_gap))

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
                self._step_raw = {}
                for s in steps:
                    if isinstance(s, (list, tuple)) and len(s) >= 3:
                        self._step_insert("end", s[0], s[1], s[2])
                    else:
                        num, content = s[0], s[1]
                        self._step_insert("end", num, content, "1.00x")
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

        _old_cfg = {}
        try:
            _p = self.get_config_path()
            if os.path.exists(_p):
                with open(_p, encoding="utf-8") as _f:
                    _old_cfg = json.load(_f) or {}
        except Exception:
            _old_cfg = {}
        # 以旧配置为底：保留 manual_steps、screen_sort 以及未来版本新增的未知键，避免保存一次就丢配置
        cfg = dict(_old_cfg)
        _sched_old = _old_cfg.get("schedule") or []

        # 开始音/结束音（保存真实路径，不保存占位文字）
        cfg["start_sound"] = getattr(self, "_start_sound_value", "")
        cfg["end_sound"] = getattr(self, "_end_sound_value", "")

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

        # 启动音频功能已移除，不再保存/播放
        cfg.pop("startup_audio", None)
        cfg["main_audio"] = self.main_audio_entry.get().strip() if hasattr(self, "main_audio_entry") else ""

        # 每条广播间隔（队列播放时生效）
        try:
            self._bcast_gap = max(0, min(3600, int(float(self.bcast_gap_entry.get().strip() or "0"))))
        except Exception:
            self._bcast_gap = 0
        cfg["bcast_gap"] = self._bcast_gap

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
        # 大屏排序方式（重启后保持用户选择）
        cfg["screen_sort"] = getattr(self, "_screen_sort_mode", "time")

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
                        self._step_raw = {}
                        for s in steps:
                            if isinstance(s, (list, tuple)) and len(s) >= 3:
                                self._step_insert("end", s[0], s[1], s[2])
                            else:
                                num, content = s[0], s[1]
                                self._step_insert("end", num, content, "1.00x")
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
            self._step_raw = {}
            for num, content in self.get_default_steps(cur_type):
                self._step_insert("end", num, content, "1.00x")
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
        self._step_raw = {}
        for num, content in self.get_default_steps(cur_type):
            self._step_insert("end", num, content, "1.00x")
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
            vals = list(item["values"])
            if len(vals) < 9:
                vals += [""] * (9 - len(vals))
            train_no = vals[0]
            self.current_train = {
                "no": train_no,
                "from": vals[2],
                "to": vals[3],
                "gate": vals[5],
                "platform": vals[6],
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
            self.broadcast_emergency_type("紧急-列车晚点（通用）")
        elif str(broadcast_type).startswith("紧急-"):
            self.broadcast_emergency_type(broadcast_type)
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
            self.apply_train_status_colors()
            # 大屏同源刷新（行已建立时立即生效；未建立时进入大屏自动重建）
            if getattr(self, "screen_rows", None) and self.screen_rows:
                self._update_screen_statuses(getattr(self, "_screen_smin", 5))
            # 副屏实时同步（主屏是预览，副屏是正式显示，状态要跟上去）
            _w = getattr(self, "_screen_win", None)
            _rf = getattr(self, "_sw_refresh", None)
            if _w is not None and _rf is not None:
                try:
                    if _w.winfo_exists():
                        _w.after(0, _rf)
                except Exception:
                    pass
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
            self.apply_train_status_colors()
            if getattr(self, "screen_rows", None) and self.screen_rows:
                self._update_screen_statuses(getattr(self, "_screen_smin", 5))
        except Exception:
            pass

    def stop_all_audio(self, clear_queue=True):
        """停止所有音频（置停止标志：各播放线程自行 close，立即生效）
        注意：winmm MCI 非线程安全，主线程调 stop/close 对子线程播放无效且引入竞争，
        因此停止只置标志，由拥有 MCI 句柄的播放线程自己退出并 close。
        clear_queue=True：手动停止时同时清空播放队列（取消所有排队广播）。"""
        self._stop_flag = True
        if clear_queue:
            self._emergency_queue = None
            self._emergency_btype = ""
            if self._bcast_queue:
                self._queue_ver += 1
            self._bcast_queue = []
        self._current_btype = ""
        self.set_status("已停止播放")
        self.bc_status_dot.configure(text="● 就绪", text_color="#4a4")
        # 停止后恢复被播放车次的状态（反向同步）
        self._restore_train_state(getattr(self, "_active_bcast_train", None))

    def _poll_bcast_queue(self):
        """主线程常驻轮询：检测后台播放完成标志，自动续播队列中的下一个
        支持"每条广播间隔"：两条之间间隔 N 秒（由广播设置配置，紧急广播不受影响）"""
        try:
            if self._queue_pending:
                self._queue_pending = False
                _gap = getattr(self, "_bcast_gap", 0) or 0
                try:
                    _gap = max(0, min(3600, int(_gap)))
                except Exception:
                    _gap = 0
                if _gap > 0 and self._bcast_queue:
                    self.after(int(_gap * 1000), self._start_next_in_queue)
                else:
                    self._start_next_in_queue()
        except Exception:
            pass
        # 队列发生变化（入队/出队/排序/清空/播放完成）→ 同步刷新队列管理面板
        try:
            if getattr(self, "_queue_ver", 0) != getattr(self, "_queue_ver_shown", -1):
                self._queue_ver_shown = self._queue_ver
                self._refresh_queue_panel()
        except Exception:
            pass
        try:
            self.after(300, self._poll_bcast_queue)
        except Exception:
            pass

    def _queue_sort_key(self, item):
        """队列排序键：优先级（停止检票→开始检票→检票预告→晚点/停运→其他）
        → 同优先级按车次开点时间早的在前 → 入队时间兜底。"""
        bt = item[1] if len(item) > 1 else ""
        tn = item[2] if len(item) > 2 else ""
        ts = item[3] if len(item) > 3 else ""
        dep = None
        tv = self._train_values_by_no(tn)
        if tv:
            dep = parse_hhmm(tv.get("dep"))
        return (bcast_priority(bt), 24 * 60 + 9999 if dep is None else dep, str(ts))

    def _sort_queue(self):
        """按优先级重排队列（稳定排序，同优先级保持入队顺序）"""
        try:
            self._bcast_queue.sort(key=self._queue_sort_key)
        except Exception:
            pass
        self._queue_ver += 1

    def _enqueue_broadcast(self, audio_list, btype, train_no="", source="手动"):
        """入队：同类型+同车次去重（更新原项），再按优先级+开点时间插入。"""
        if not audio_list:
            self.set_status("无可用音频片段，未加入队列")
            return False
        train_no = str(train_no or "")
        item = (audio_list, btype, train_no, time.strftime("%H:%M:%S"), source or "手动")
        for i, old in enumerate(self._bcast_queue):
            old_bt = old[1] if len(old) > 1 else ""
            old_tn = old[2] if len(old) > 2 else ""
            if old_bt == btype and str(old_tn) == train_no:
                self._bcast_queue[i] = item
                self._sort_queue()
                self.set_status(f"队列中已有相同广播，已更新排序：{btype} {train_no}".strip())
                return True
        self._bcast_queue.append(item)
        self._sort_queue()
        _gap_txt = f"，每条间隔 {getattr(self, '_bcast_gap', 0)} 秒" if getattr(self, "_bcast_gap", 0) else ""
        self.set_status(f"已加入播放队列（第 {len(self._bcast_queue)} 位，按优先级排序）{_gap_txt}，播完自动继续")
        return True

    def _start_next_in_queue(self):
        """播放队列中的下一个（主线程调用：播放完成后自动续播）
        队列为空、正在播放、或有紧急广播挂起时不动作。"""
        try:
            if getattr(self, "_playing", False):
                return
            if getattr(self, "_emergency_queue", None):
                return  # 有紧急广播挂起 → 等紧急播完再继续队列
            while self._bcast_queue:
                item = self._bcast_queue.pop(0)
                al, bt = item[0], item[1]
                # 恢复该队列项的车次号/来源（保证状态/日志/大屏同步正确）
                tn = item[2] if len(item) > 2 else ""
                src = item[4] if len(item) > 4 else "手动"
                if tn:
                    self._active_bcast_train = tn
                self._current_btype = bt
                self._queue_ver += 1  # 出队 → 通知界面刷新
                self.play_concat_audio(al, emergency=False, btype=bt, source=src)
                if getattr(self, "_playing", False):
                    return  # 已开始播放 → 等完成回调
                # 该条无音频/无法播放 → 继续下一个
        except Exception as _e:
            try:
                self.set_status(f"队列播放异常: {_e}")
            except Exception:
                pass

    def _wait_emergency_play(self):
        """紧急广播抢占：轮询旧播放线程退出（_playing 置 False）后启动紧急内容"""
        def _chk():
            if getattr(self, "_playing", False):
                self.after(200, _chk)
            else:
                _al = getattr(self, "_emergency_queue", None)
                _bt = getattr(self, "_emergency_btype", "")
                self._emergency_queue = None
                self._emergency_btype = ""
                if _al:
                    self.play_concat_audio(_al, btype=_bt, source="紧急")
        self.after(200, _chk)

    def _log_bcast(self, btype, train_no="", source="手动"):
        """记录广播历史到 bcast_log.json（保留最近 2000 条，线程安全）"""
        try:
            with _LOG_LOCK:
                path = os.path.join(get_project_root(), "bcast_log.json")
                logs = []
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            logs = json.load(f) or []
                    except Exception:
                        logs = []
                logs.append({
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": btype,
                    "train": train_no or "",
                    "source": source,
                })
                if len(logs) > 2000:
                    logs = logs[-2000:]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

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

        ctk.CTkLabel(list_frame, text="车次列表（9 列与主界面同源，选中自动回填）",
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
            self.train_tree.heading(col, text=col, anchor="w")
            self.train_tree.column(col, width=_col_w[col], anchor="w")
        self.train_tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.train_tree.bind("<<TreeviewSelect>>", self.on_train_tree_select)

        # 加载车次（zebra 在 load_trains 内部调用）
        self.load_trains()

        # 右侧：详情面板（修复：字段行高不重叠，紧凑对称）
        detail_frame = ctk.CTkFrame(panel, fg_color=DS["panel"], corner_radius=10)
        detail_frame.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        detail_frame.grid_columnconfigure(0, weight=1)
        detail_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(detail_frame, text="车次详情（只读显示，修改请使用添加/更新按钮）",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color=DS["accent"])\
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6))

        # 表单（2 列紧凑布局，每对 label+entry 占 2 行，避免重叠）
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
            r, c = 1 + (i // 2) * 2, i % 2
            ctk.CTkLabel(detail_frame, text=label + ":", font=ctk.CTkFont(size=11),
                         text_color=DS["text_dim"]).grid(row=r, column=c, sticky="w",
                                                         padx=(12, 4), pady=(9, 0))
            entry = ctk.CTkEntry(detail_frame, font=ctk.CTkFont(size=12), height=30, state="readonly")
            entry.grid(row=r + 1, column=c, sticky="ew", padx=(4, 8), pady=(0, 4))
            self.train_fields[key] = entry

        # 状态（只读显示，与其他字段一致：标签上、值下，避免同行错位感）
        ctk.CTkLabel(detail_frame, text="状态:", font=ctk.CTkFont(size=11),
                     text_color=DS["text_dim"]).grid(row=9, column=0, sticky="w",
                                                     padx=(12, 4), pady=(9, 0))
        self.status_disp = ctk.CTkLabel(detail_frame, text="待检票", font=ctk.CTkFont(size=12),
                                        text_color=DS["text"], anchor="w")
        self.status_disp.grid(row=10, column=0, sticky="ew", padx=(4, 8), pady=(0, 4))

        # 按钮（2 行 2 列，均衡）
        btn_row1 = ctk.CTkFrame(detail_frame, fg_color="transparent")
        btn_row1.grid(row=11, column=0, columnspan=2, sticky="ew", padx=12, pady=(14, 5))
        ctk.CTkButton(btn_row1, text="添加", font=ctk.CTkFont(size=12),
                      fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                      command=self.add_train).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(btn_row1, text="更新", font=ctk.CTkFont(size=12),
                      fg_color=DS["btn_success"], hover_color=DS["btn_success_hover"],
                      command=self.update_train).pack(side="left", fill="x", expand=True, padx=(5, 0))

        btn_row2 = ctk.CTkFrame(detail_frame, fg_color="transparent")
        btn_row2.grid(row=12, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))
        ctk.CTkButton(btn_row2, text="移除", font=ctk.CTkFont(size=12),
                      fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                      command=self.remove_train).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(btn_row2, text="刷新", font=ctk.CTkFont(size=12),
                      fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      command=self.load_trains).pack(side="left", fill="x", expand=True, padx=(5, 0))

        return panel


    def on_train_tree_select(self, _evt=None):
        """车辆管理：选中列表项自动回填只读表单"""
        sel = self.train_tree.selection()
        if not sel:
            return
        vals = list(self.train_tree.item(sel[0])["values"])
        if len(vals) < 9:
            vals = vals + [""] * (9 - len(vals))

        def _fill(key, v):
            w = self.train_fields[key]
            try:
                w.configure(state="normal")
                w.delete(0, "end")
                w.insert(0, str(v))
                w.configure(state="readonly")
            except Exception:
                pass

        _fill("num", vals[0])
        _fill("typ", vals[1])
        _fill("dep", vals[2])
        _fill("arr", vals[3])
        _fill("dept", vals[4])
        _fill("ckpt", vals[5])
        _fill("plat", vals[6])
        self.status_disp.configure(text=str(vals[7]))
        _fill("arr_time", vals[8])

    def create_queue_panel(self):
        """广播队列管理面板（独立左侧选项卡）：查看排队中的广播，支持移除/排序/清空"""
        panel = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        # ===== 顶部：标题 + 状态 =====
        toolbar = ctk.CTkFrame(panel, fg_color=DS["panel"], corner_radius=8, height=50)
        toolbar.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        toolbar.grid_propagate(False)
        t_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        t_inner.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(t_inner, text="广播队列管理", font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=DS["accent"]).pack(side="left", padx=(5, 20))
        self.queue_status_dot = ctk.CTkLabel(t_inner, text="● 系统就绪",
                                             font=ctk.CTkFont(size=12, weight="bold"),
                                             text_color="#4d4")
        self.queue_status_dot.pack(side="right", padx=10)
        self.queue_info_label = ctk.CTkLabel(t_inner, text="队列中：0 项",
                                             font=ctk.CTkFont(size=12), text_color=DS["text_dim"])
        self.queue_info_label.pack(side="right", padx=10)

        # ===== 中部：队列表格 =====
        body = ctk.CTkFrame(panel, fg_color=DS["panel"], corner_radius=8)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(body, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 5))
        ctk.CTkLabel(head, text="待播放队列（按播放顺序）", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=DS["accent"]).pack(side="left")
        ctk.CTkLabel(head, text="播放中再点其他车次广播 → 自动排队，前一个播完自动播下一个；紧急广播优先抢占",
                     font=ctk.CTkFont(size=11), text_color="#667").pack(side="left", padx=10)

        cols = ("序号", "优先级", "广播类型", "车次", "入队时间")
        self.queue_tree = ttk.Treeview(body, columns=cols, show="headings", height=14)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("QueueTree.Heading", font=(DS["font"], 10, "bold"),
                        background=DS["panel2"], foreground=DS["text"], relief="flat", padding=6)
        style.map("QueueTree.Heading", background=[("active", DS["btn"])])
        style.configure("QueueTree", font=(DS["font"], 10), rowheight=30,
                        background=DS["row1"], fieldbackground=DS["row1"], foreground=DS["text"], borderwidth=0)
        style.map("QueueTree", background=[("selected", DS["row_sel"])],
                  foreground=[("selected", "#ffffff")])
        for c in cols:
            self.queue_tree.heading(c, text=c)
        widths = {"序号": 60, "优先级": 125, "广播类型": 220, "车次": 150, "入队时间": 110}
        for c in cols:
            self.queue_tree.column(c, width=widths.get(c, 120), anchor="center", stretch=True)
        self.queue_tree.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 8))

        # 滚动条
        vsb = ttk.Scrollbar(body, orient="vertical", command=self.queue_tree.yview)
        vsb.grid(row=1, column=1, sticky="ns", pady=(0, 8))
        self.queue_tree.configure(yscrollcommand=vsb.set)

        # ===== 底部：操作按钮 =====
        ops = ctk.CTkFrame(panel, fg_color="transparent")
        ops.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        btn_style = {"height": 32, "font": ctk.CTkFont(size=12)}
        ctk.CTkButton(ops, text="上移", fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      command=self.queue_move_up, width=80, **btn_style).pack(side="left", padx=(0, 6))
        ctk.CTkButton(ops, text="下移", fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      command=self.queue_move_down, width=80, **btn_style).pack(side="left", padx=6)
        ctk.CTkButton(ops, text="移除选中", fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                      command=self.queue_remove_selected, width=110, **btn_style).pack(side="left", padx=6)
        ctk.CTkButton(ops, text="清空队列", fg_color=DS["btn_danger"], hover_color=DS["btn_danger_hover"],
                      command=self.queue_clear_all, width=110, **btn_style).pack(side="left", padx=6)
        ctk.CTkButton(ops, text="刷新", fg_color=DS["btn_primary"], hover_color=DS["btn_primary_hover"],
                      command=self._refresh_queue_panel, width=80, **btn_style).pack(side="left", padx=6)
        ctk.CTkButton(ops, text="按优先级排序", fg_color=DS["btn"], hover_color=DS["btn_hover"],
                      command=self.queue_sort_priority, width=125, **btn_style).pack(side="left", padx=6)
        ctk.CTkLabel(ops, text="提示：移除/清空只影响待播队列，当前正在播放的广播不受影响",
                     font=ctk.CTkFont(size=11), text_color="#667").pack(side="right")
        return panel

    def _refresh_queue_panel(self):
        """刷新队列管理面板（列表 + 状态）"""
        try:
            if not hasattr(self, "queue_tree"):
                return
            # 增量更新：不整表删除重建，队列变化时行内容原地替换，避免闪一下
            q = self._bcast_queue
            desired = []
            for i, item in enumerate(q, start=1):
                bt = item[1] if len(item) > 1 else ""
                tn = item[2] if len(item) > 2 else ""
                ts = item[3] if len(item) > 3 else "--:--:--"
                desired.append((i, bcast_priority_label(bt), bt, tn, ts))
            children = list(self.queue_tree.get_children())
            for idx, vals in enumerate(desired):
                if idx < len(children):
                    iid = children[idx]
                    cur = tuple(self.queue_tree.item(iid)["values"])
                    if cur != vals:
                        self.queue_tree.item(iid, values=vals)
                else:
                    self.queue_tree.insert("", "end", values=vals)
            for iid in children[len(desired):]:
                self.queue_tree.delete(iid)
            n = len(q)
            self.queue_info_label.configure(text=f"队列中：{n} 项")
            if getattr(self, "_playing", False):
                self.queue_status_dot.configure(text="● 正在播放", text_color="#ffd24d")
            else:
                self.queue_status_dot.configure(text="● 系统就绪", text_color="#4d4")
        except Exception:
            pass

    def queue_sort_priority(self):
        """按优先级 + 开点时间重新排队（停止检票 → 开始检票 → 检票预告 → 晚点/停运 → 普通）"""
        self._sort_queue()
        self._refresh_queue_panel()
        self.set_status("队列已按优先级排序：停止检票 → 开始检票 → 检票预告 → 晚点/停运 → 普通")

    def _queue_sel_index(self):
        """当前选中的队列行索引（1 起）；无选中返回 None"""
        try:
            sel = self.queue_tree.selection()
            if not sel:
                return None
            vals = self.queue_tree.item(sel[0])["values"]
            if not vals:
                return None
            return int(vals[0]) - 1
        except Exception:
            return None

    def queue_remove_selected(self):
        """移除选中的待播广播"""
        idx = self._queue_sel_index()
        if idx is None:
            self.set_status("请先在队列列表中选择一项")
            return
        if 0 <= idx < len(self._bcast_queue):
            removed = self._bcast_queue.pop(idx)
            self._queue_ver += 1
            bt = removed[1] if len(removed) > 1 else ""
            self.set_status(f"已从队列移除：{bt or '广播'}")
        self._refresh_queue_panel()

    def queue_clear_all(self):
        """清空待播队列（正在播放的广播不受影响）"""
        n = len(self._bcast_queue)
        self._bcast_queue = []
        self._queue_ver += 1
        self.set_status(f"已清空待播队列（{n} 项），当前播放不受影响")
        self._refresh_queue_panel()

    def queue_move_up(self):
        """队列上移（播放顺序提前）"""
        idx = self._queue_sel_index()
        if idx is None:
            self.set_status("请先在队列列表中选择一项")
            return
        if idx <= 0 or idx >= len(self._bcast_queue):
            self.set_status("已在队列最前，无法继续上移")
            return
        self._bcast_queue[idx - 1], self._bcast_queue[idx] = self._bcast_queue[idx], self._bcast_queue[idx - 1]
        self._queue_ver += 1
        self.set_status("已上移（播放顺序提前）")
        self._refresh_queue_panel()
        # 保持选中
        for it in self.queue_tree.get_children():
            if self.queue_tree.item(it)["values"] and int(self.queue_tree.item(it)["values"][0]) == idx:
                self.queue_tree.selection_set(it)
                break

    def queue_move_down(self):
        """队列下移（播放顺序延后）"""
        idx = self._queue_sel_index()
        if idx is None:
            self.set_status("请先在队列列表中选择一项")
            return
        if idx < 0 or idx >= len(self._bcast_queue) - 1:
            self.set_status("已在队列最后，无法继续下移")
            return
        self._bcast_queue[idx], self._bcast_queue[idx + 1] = self._bcast_queue[idx + 1], self._bcast_queue[idx]
        self._queue_ver += 1
        self.set_status("已下移（播放顺序延后）")
        self._refresh_queue_panel()
        # 保持选中
        for it in self.queue_tree.get_children():
            if self.queue_tree.item(it)["values"] and int(self.queue_tree.item(it)["values"][0]) == idx + 2:
                self.queue_tree.selection_set(it)
                break

    def _apply_bcast_gap(self):
        """每条广播间隔（秒）：解析输入 → 立即生效 → 自动保存"""
        try:
            v = self.bcast_gap_entry.get().strip() or "0"
            v = max(0, min(3600, int(float(v))))
        except Exception:
            v = 0
        self._bcast_gap = v
        try:
            self.bcast_gap_entry.delete(0, "end")
            self.bcast_gap_entry.insert(0, str(v))
        except Exception:
            pass
        try:
            self.save_bc_settings(silent=True)
        except Exception:
            pass
        self.set_status(f"广播间隔已设置为 {v} 秒（队列播放时生效）")

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
        self.queue_panel.grid_remove()
        self.train_panel.grid_remove()
        self.screen_panel.grid_remove()
        self.system_panel.grid_remove()
        self.bcast_set_panel.grid_remove()

    def show_queue(self):
        self.set_active_nav(1)
        self.broadcast_panel.grid_remove()
        self.queue_panel.grid()
        self.train_panel.grid_remove()
        self.screen_panel.grid_remove()
        self.system_panel.grid_remove()
        self.bcast_set_panel.grid_remove()
        self._refresh_queue_panel()

    def show_train(self):
        self.set_active_nav(2)
        self.broadcast_panel.grid_remove()
        self.queue_panel.grid_remove()
        self.train_panel.grid()
        self.screen_panel.grid_remove()
        self.system_panel.grid_remove()
        self.bcast_set_panel.grid_remove()
        # 进入页面先增量同步一次，避免隐藏期间的数据要等 5 秒自动刷新才出现
        try:
            self.load_trains()
        except Exception:
            pass
        self.refresh_sched_train_list()
        # 启动车辆列表自动刷新（每 10 秒，仅启动一次，页面隐藏时自动跳过）
        if not getattr(self, "_train_auto_refresh_on", False):
            self._train_auto_refresh_on = True
            self.after(5000, self._train_auto_refresh)

    def show_screen(self):
        self.set_active_nav(3)
        self.broadcast_panel.grid_remove()
        self.queue_panel.grid_remove()
        self.train_panel.grid_remove()
        self.screen_panel.grid()
        self.system_panel.grid_remove()
        self.bcast_set_panel.grid_remove()
        # 进入大屏即刷新数据并启动时钟
        self.refresh_screen()
        self._screen_tick()

    def show_system(self):
        self.set_active_nav(4)
        self.broadcast_panel.grid_remove()
        self.queue_panel.grid_remove()
        self.train_panel.grid_remove()
        self.screen_panel.grid_remove()
        self.system_panel.grid()
        self.bcast_set_panel.grid_remove()

    def show_bcast_set(self):
        self.set_active_nav(5)
        self.broadcast_panel.grid_remove()
        self.queue_panel.grid_remove()
        self.train_panel.grid_remove()
        self.screen_panel.grid_remove()
        self.system_panel.grid_remove()
        self.bcast_set_panel.grid()

    # ========== 功能函数 ==========
    def _screen_sorted_rows(self, rows, smin=None):
        """统一车次排序（主列表/大屏/副屏共用）。
        time 模式：按开点时间升序，状态只作同时间兜底（默认，顺序稳定不跳动）；
        status 模式：正在检票 → 停止检票 → 晚点 → 待检票 → 停运 → 已发车/到达。
        无/非法开点排末尾，车次号自然排序兜底；重复车次只保留第一条。"""
        try:
            if smin is None:
                smin = getattr(self, "_screen_smin", 5)
        except Exception:
            smin = 5
        seen = set()
        unique = []
        for r in rows:
            try:
                key = str(r[0]).strip()
            except Exception:
                key = ""
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(r)
        mode = getattr(self, "_screen_sort_mode", "time")

        def _key(r):
            st = effective_train_status(r, smin)
            dep = parse_hhmm(r[4] if len(r) > 4 else "")
            dep = 24 * 60 + 9999 if dep is None else dep
            rank = STATUS_RANK.get(st, 3)
            if mode == "status":
                return (rank, dep, train_no_key(r[0]))
            # 时间模式只按开点 + 车次号排序：状态变化绝不导致行位置互换
            return (dep, train_no_key(r[0]))

        try:
            return sorted(unique, key=_key)
        except Exception:
            return unique

    def refresh_screen(self, silent=False):
        """刷新大屏：增量更新（表头只建一次、行按车次号 diff，排序变化只移动行位置不覆盖内容）
        silent=True：自动刷新时不清空状态栏（避免每 2 秒刷"已刷新"噪音）"""
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
            # 表头只建一次，刷新时不再销毁重建
            if not getattr(self, "_screen_header_built", False):
                self._build_screen_header(self.screen_container)
                self._screen_header_built = True
            # 最新数据（与主界面车次同源，按状态优先级 + 开点时间排序）
            rows = []
            for c in self.bc_train_tree.get_children():
                rows.append(list(self.bc_train_tree.item(c)["values"]))
            rows = self._screen_sorted_rows(rows, smin)
            new_keys = [str(r[0]) for r in rows]
            # 顺序缓存：仅当顺序真正变化（新增/删除/状态排序变化）时才重排 grid，
            # 消除每 2 秒全量 grid 重设导致的视觉抖动（车次一多就乱跳的根因之一）
            prev_order = getattr(self, "_screen_order", None)
            order_changed = prev_order != new_keys
            self._screen_order = list(new_keys)
            # 删除已不存在的车次行
            for key in [k for k in list(self.screen_rows.keys()) if k not in new_keys]:
                self._destroy_screen_row(key)
            # 更新已有行 / 新建缺失行；仅顺序变化时按新排序 grid 到对应位置
            # （新建行始终需要 grid；内容更新只改文本不移动，避免跳动）
            for i, r in enumerate(rows):
                key = str(r[0])
                if key in self.screen_rows:
                    row = self.screen_rows[key]
                    self._update_screen_row(key, r)
                    row["idx"] = i
                    if order_changed:
                        try:
                            row["frame"].grid(row=i + 1, column=0, sticky="ew", pady=4)
                        except Exception:
                            pass
                else:
                    self._add_screen_row(self.screen_container, i, r)
            self._update_screen_statuses(smin)
            if hasattr(self, "screen_status"):
                self.screen_status.configure(text=f"● 大屏运行中 · 共 {len(rows)} 趟列车", text_color="#6be26b")
            if not silent:
                self.set_status(f"车站大屏已刷新（{len(rows)} 趟列车）")
        except Exception as e:
            self.set_status(f"大屏刷新失败：{e}")

    def _screen_tick(self):
        """大屏时钟每秒刷新；每 2 秒自动同步一次车次数据与状态（增量更新，无变化不重绘）。
        这样在广播管理/车辆管理更新车次后，停留在大屏页也会自动跟随，无需手动点刷新。"""
        # 防止重复进入大屏时叠加多条 after 循环：取消上一条，再重启唯一一条
        _old_tick = getattr(self, "_screen_tick_after", None)
        if _old_tick:
            try:
                self.after_cancel(_old_tick)
            except Exception:
                pass
        self._screen_tick_on = True
        try:
            if not self.screen_panel.winfo_ismapped():
                self._screen_tick_after = self.after(1000, self._screen_tick)
                return
            now = time.strftime("%H:%M:%S")
            if hasattr(self, "screen_clock") and self.screen_clock.winfo_exists():
                if self.screen_clock.cget("text") != now:
                    self.screen_clock.configure(text=now)
                _wd = "一二三四五六日"[time.localtime().tm_wday]
                _d = time.strftime("%Y年%m月%d日") + f"  星期{_wd}"
                if self.screen_date.cget("text") != _d:
                    self.screen_date.configure(text=_d)
            # 每 2 秒静默刷新（refresh_screen 内含状态列更新 + 增量 diff）
            _n = getattr(self, "_screen_tick_n", 0) + 1
            self._screen_tick_n = _n
            if _n % 2 == 0:
                self.refresh_screen(silent=True)
        except Exception:
            pass
        self._screen_tick_after = self.after(1000, self._screen_tick)

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
            st = "启用" if s.get("enabled") else "停用"
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
        """每秒轮询：到点且已启用 → 播放对应广播（同一任务当天只触发一次）
        多个任务同一分钟时全部触发，按优先级进入播放队列，不会互相覆盖。"""
        try:
            now = time.strftime("%H:%M")
            day = time.strftime("%Y-%m-%d")
            last = dict(getattr(self, "_last_sched", {}) or {})
            for idx, s in enumerate(getattr(self, "bc_schedule", [])):
                if not s.get("enabled"):
                    continue
                if s.get("time") != now:
                    continue
                key = f"{day}|{idx}|{s.get('time')}|{s.get('type')}|{s.get('train')}"
                if last.get(key):
                    continue
                last[key] = True
                self.schedule_play(s.get("type", "检票预告"), s.get("train", ""))
            # 跨天清理，防止字典无限增长
            if len(last) > 800:
                last = dict(list(last.items())[-400:])
            self._last_sched = last
        except Exception:
            pass
        self.after(1000, self._schedule_tick)

    def _auto_sched_tick(self):
        """车次时刻自动广播：每 30 秒检查一次；进入提前量窗口后触发（每日每车次每类一次）。
        不再要求“正好等于”，程序晚启动几分钟也能补上，避免错过广播。"""
        try:
            cfg = self.load_sys_config()
            if cfg.get("train_auto_bcast", False):
                try:
                    preview_min = max(1, min(120, int(cfg.get("train_preview_min", 5) or 5)))
                except Exception:
                    preview_min = 5
                try:
                    start_min = max(1, min(120, int(cfg.get("train_start_min", 1) or 1)))
                except Exception:
                    start_min = 1
                now = time.localtime()
                today = time.strftime("%Y-%m-%d")
                now_min = now.tm_hour * 60 + now.tm_min
                if getattr(self, "_auto_fired_date", "") != today:
                    self._auto_fired = set()
                    self._auto_fired_date = today
                fired = getattr(self, "_auto_fired", set())
                for c in self.bc_train_tree.get_children():
                    v = list(self.bc_train_tree.item(c)["values"])
                    if len(v) < 9:
                        continue
                    no, dep = str(v[0]).strip(), str(v[4]).strip()
                    if not no or not dep:
                        continue
                    dep_min = parse_hhmm(dep)
                    if dep_min is None:
                        continue
                    diff = dep_min - now_min
                    if -1 <= diff <= preview_min and (no + "|预告") not in fired:
                        fired.add(no + "|预告")
                        self._auto_bcast_train(no, "检票预告")
                    if -1 <= diff <= start_min and (no + "|开始") not in fired:
                        fired.add(no + "|开始")
                        self._auto_bcast_train(no, "开始检票")
                self._auto_fired = fired
        except Exception:
            pass
        try:
            self.after(30000, self._auto_sched_tick)
        except Exception:
            pass

    def _auto_bcast_train(self, no, btype):
        """车次时刻自动广播触发：用完整车次信息播放（不丢发站/到站/检票口/站台），
        正在播放时按优先级排队，不丢广播。"""
        try:
            tv = self._train_values_by_no(no)
            if not tv:
                self.set_status(f"车次时刻自动广播：未找到车次 {no}，已跳过")
                return
            self.current_train = dict(tv)
            self._active_bcast_train = no
            self._auto_bcast_flag = True
            if btype == "检票预告":
                self._set_train_state(no, "待检票", keep=True)
            else:
                self._set_train_state(no, "正在检票", keep=True)
            audio_list = self.build_audio_list_from_steps(btype, train_values=tv)
            if audio_list:
                self.bc_status_dot.configure(text="● 自动广播中", text_color="#f80")
                self.set_status(f"车次时刻自动广播：{no} {btype}")
                self.play_concat_audio(audio_list, btype=btype, source="自动")
            else:
                self.set_status(f"车次时刻自动广播：{btype} 无可用音频配置")
        except Exception as _e:
            self.set_status(f"车次时刻自动广播异常：{_e}")
        finally:
            self._auto_bcast_flag = False

    def _save_train_auto_cfg(self):
        """车次时刻自动广播配置立即持久化并生效"""
        try:
            cfg = self.load_sys_config()
            cfg["train_auto_bcast"] = bool(self.train_auto_sw.get())
            try:
                cfg["train_preview_min"] = max(1, min(120, int(self.train_preview_min.get().strip() or 5)))
            except Exception:
                cfg["train_preview_min"] = 5
            try:
                cfg["train_start_min"] = max(1, min(120, int(self.train_start_min.get().strip() or 1)))
            except Exception:
                cfg["train_start_min"] = 1
            self.save_sys_config(cfg)
            self.set_status("车次时刻自动广播配置已保存并生效")
        except Exception as e:
            self.set_status(f"保存车次时刻配置失败: {e}")

    def schedule_play(self, btype, train_no):
        """定时触发：按指定车次播放指定类型广播；找不到车次直接报错，绝不用假车次顶替。"""
        train_no = (train_no or "").strip()
        tv = self._train_values_by_no(train_no) if train_no else None
        if train_no and not tv:
            self.set_status(f"定时广播跳过：未找到车次 {train_no}（{btype}）")
            return
        if tv:
            self.current_train = dict(tv)
        elif not self.current_train:
            self.set_status(f"定时广播跳过：{btype} 未指定车次")
            return
        self.set_status(f"定时广播触发：{btype} {self.current_train['no']}")
        try:
            if hasattr(self, "bc_status_dot"):
                self.bc_status_dot.configure(text="● 广播中", text_color="#f80")
        except Exception:
            pass
        # 同步大屏状态（与手动按钮一致，keep=True 播完保持，不跳回）
        try:
            _no = self.current_train["no"]
            if "检票预告" in btype:
                self._set_train_state(_no, "待检票", keep=True)
            elif "开始检票" in btype or btype == "检票中":
                self._set_train_state(_no, "正在检票", keep=True)
            elif "停止检票" in btype or "检票结束" in btype:
                self._set_train_state(_no, "停止检票", keep=True)
            elif "晚点" in btype:
                self._set_train_state(_no, "晚点", keep=True)
            elif "停运" in btype:
                self._set_train_state(_no, "停运", keep=True)
            else:
                self.refresh_screen()
        except Exception:
            pass
        self.sync_steps_to_memory()
        steps = self.bc_steps.get(btype) or self.get_default_steps(btype)
        if "晚点" in btype:
            steps = self._prepare_delay_steps(steps)
        audio_list = self.resolve_audio_items(steps, self.current_train)
        if audio_list:
            self.play_concat_audio(audio_list, btype=btype, source="定时")
        else:
            self.set_status(f"定时广播 {btype} 没有可播放的音频")
            try:
                self.bc_status_dot.configure(text="● 系统就绪", text_color="#4d4")
            except Exception:
                pass

    def update_clock(self):
        now = time.strftime("%H:%M:%S")
        if self.clock_label.cget("text") != now:
            self.clock_label.configure(text=now)
        self.after(1000, self.update_clock)

    def connect_tcp(self):
        """连接后端 TCP（线程连接，不阻塞界面启动）"""
        def _do():
            _ok = False
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect((TCP_HOST, TCP_PORT))
                self.tcp_sock = s
                _ok = True
            except Exception:
                self.tcp_sock = None
            try:
                self.after(0, lambda: self.set_status(
                    "系统启动成功" if _ok else "系统启动成功（未连接后端）"))
            except Exception:
                pass
        try:
            import threading
            threading.Thread(target=_do, daemon=True).start()
        except Exception:
            try:
                self.set_status("系统启动成功（未连接后端）")
            except Exception:
                pass

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

    def play_concat_audio(self, audio_list, emergency=False, btype="", source=None):
        """拼接多个音频片段：解码→裁静音→统一采样率→合成一个完整音频再播放（绝对无缝）
        emergency=True：紧急广播抢占——先中断当前播放，等旧线程退出后再播紧急内容
        source：广播来源（手动/自动/定时/紧急），入队和日志沿用，避免播放时来源错乱"""
        import threading
        import os
        import ctypes
        import tempfile
        import time

        root = AUDIO_DIR
        _src = source or ("紧急" if emergency else ("自动" if getattr(self, "_auto_bcast_flag", False) else "手动"))

        # 紧急抢占：中断当前播放，轮询旧线程退出后启动紧急内容（保留普通广播队列，紧急播完自动续播）
        if emergency and getattr(self, "_playing", False):
            self.set_status("紧急广播：正在抢占播放...")
            self._emergency_queue = audio_list
            self._emergency_btype = btype
            self.stop_all_audio(clear_queue=False)
            self._wait_emergency_play()
            return
        # 非紧急且正在播放：按优先级加入播放队列，前一个播完自动播放下一个
        if getattr(self, "_playing", False):
            _q_train = getattr(self, "_active_bcast_train", "") or ""
            self._enqueue_broadcast(audio_list, btype, _q_train, _src)
            return
        # 空队列：给出明确提示，不静默播放（防止"变更站台/旅客突发"等缺音频类型无声无反馈）
        if not audio_list:
            self.set_status("无可用音频片段，请检查语音包或广播配置")
            self._playing = False
            return
        self._stop_flag = False
        self._current_btype = btype
        # 日志在真正合成出音频后再写（避免“缺音频也记一条已播”的假记录）
        _log_btype = btype or "手动播放"
        _log_train = getattr(self, "_active_bcast_train", "") or ""

        # ===== 主线程读取 Tkinter 控件快照（后台线程禁止访问控件，否则 RuntimeError）=====
        cfg_start_sound = getattr(self, "_start_sound_value", "")
        cfg_end_sound = getattr(self, "_end_sound_value", "")
        cfg_main_audio = self.main_audio_entry.get().strip() if hasattr(self, "main_audio_entry") else ""
        try:
            cfg_speed = float(self.speed_slider.get()) if hasattr(self, "speed_slider") else 1.0
        except Exception:
            cfg_speed = 1.0
        try:
            cfg_var_speed = float(self.var_speed_slider.get()) if hasattr(self, "var_speed_slider") else 1.0
        except Exception:
            cfg_var_speed = 1.0
        # 主线程快照播放音量（主音量 × 夜间时段调节）
        try:
            cfg_volume = self._effective_volume()
        except Exception:
            cfg_volume = 1.0

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
                self._queue_pending = True
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
                try:
                    subdir, filename = seg[0], seg[1]
                    seg_speed = float(seg[2]) if len(seg) > 2 else 1.0
                    seg_is_var = len(seg) > 3 and bool(seg[3])
                except Exception:
                    # 防御：步骤格式错误不崩线程，按缺失提示并跳过
                    missing.append(f"步骤格式错误: {seg}")
                    continue
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
                self._queue_pending = True
                return

            # 真正有音频可播时才记录历史
            self._log_bcast(_log_btype, _log_train, _src)

            if missing:
                safe_after(0, lambda m=missing: self.set_status(f"缺音频: {'、'.join(m)}"))

            # 统一采样率；片段间交叉淡化拼接（防"叭叭叭"爆音）
            if getattr(self, "_stop_flag", False):
                safe_after(0, lambda: self.bc_status_dot.configure(text="● 系统就绪", text_color="#4d4"))
                safe_after(0, lambda: self._restore_train_state(getattr(self, "_active_bcast_train", None)))
                self._playing = False
                self._queue_pending = True
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

            # 应用播放音量（主音量 × 夜间时段调节；音量 100 时不做增益避免爆音）
            if cfg_volume is not None and 0.0 <= cfg_volume < 1.0:
                merged = merged * cfg_volume
            # 写入临时 wav（纯英文路径）
            out_wav = os.path.join(tempfile.gettempdir(), "bc_merged.wav")
            sf.write(out_wav, merged, 44100)

            # MCI 播放一个完整文件（绝对无缝）
            mci = ctypes.windll.winmm
            alias = "bc_merged"
            # 播放前先释放其他占用
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
            self._queue_pending = True

        def _worker():
            try:
                concat_and_play()
            except Exception as _e:
                safe_after(0, lambda _e=_e: self.set_status(f"播放异常: {_e}"))
            finally:
                # 任何异常都不能让 _playing 卡在 True（否则后续广播全部只能排队）
                self._playing = False
                self._queue_pending = True
                self._current_btype = ""

        self._playing = True
        try:
            threading.Thread(target=_worker, daemon=True).start()
        except Exception as _e:
            self._playing = False
            self._queue_pending = True
            self._current_btype = ""
            self.set_status(f"播放线程启动失败: {_e}")

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
        """车辆管理面板：增量同步主界面车次（不整表删除重建，刷新无闪烁）。"""
        sel = self.train_tree.selection()
        sel_no = ""
        if sel:
            try:
                sel_no = str(self.train_tree.item(sel[0])["values"][0]).strip()
            except Exception:
                sel_no = ""
        rows = []
        for c in self.bc_train_tree.get_children():
            vals = list(self.bc_train_tree.item(c)["values"])
            if len(vals) < 9:
                vals = vals + [""] * (9 - len(vals))
            rows.append(vals[:9])
        rows = self._screen_sorted_rows(rows)

        tree = self.train_tree
        existing = {}
        for c in tree.get_children():
            vals = list(tree.item(c)["values"])
            if vals:
                existing[str(vals[0]).strip()] = c
        desired = [str(r[0]).strip() for r in rows]

        # 删除已不存在的行
        for key, iid in list(existing.items()):
            if key not in desired:
                try:
                    tree.delete(iid)
                except Exception:
                    pass
                existing.pop(key, None)

        # 只更新内容变化的行
        for vals in rows:
            key = str(vals[0]).strip()
            iid = existing.get(key)
            if iid is None:
                existing[key] = tree.insert("", "end", values=tuple(vals))
            else:
                cur = list(tree.item(iid)["values"])
                cur = cur + [""] * (9 - len(cur)) if len(cur) < 9 else cur[:9]
                if tuple(cur) != tuple(vals):
                    tree.item(iid, values=tuple(vals))

        # 只有顺序真正变化才移动行
        ordered = [existing[k] for k in desired if k in existing]
        if list(tree.get_children()) != ordered:
            for idx, iid in enumerate(ordered):
                tree.move(iid, "", idx)
        zebra(tree)

        # 按车次号恢复选中，不重置详情区
        if sel_no and sel_no in existing:
            iid = existing[sel_no]
            if tree.selection() != (iid,):
                tree.selection_set(iid)
                tree.see(iid)
                self.on_train_tree_select()


    def add_train(self):
        """车辆管理面板添加：弹出主界面添加对话框（数据同源）"""
        self.add_train_dialog()

    def update_train(self):
        """车辆管理面板更新：弹出独立编辑窗口（预填选中车次）"""
        self.update_train_dialog()


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
        if getattr(self, "current_train", None) and str(self.current_train.get("no", "")) == str(no):
            self.current_train = None
            if hasattr(self, "current_train_label"):
                self.current_train_label.configure(text="未选择车次")
        zebra(self.bc_train_tree)
        self.sort_train_tree()
        self.save_trains_data()
        try:
            self.train_tree.delete(sel)
        except Exception:
            pass
        try:
            self.refresh_screen(silent=True)
        except Exception:
            pass
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
        self.sort_train_tree()
        self.save_trains_data()

    def logout(self):
        self.set_status("退出登录")
        self.destroy()

    def quit_app(self):
        self.set_status("关闭系统")
        self.quit()

# ============================================================
# 纯 Python 启动/登录界面（无图标、无 C++ 依赖）
# ============================================================
class _StartupApp:
    """启动画面 + 登录，全部用 tkinter 实现；不加载任何图标。"""
    BG = "#08111f"
    PANEL = "#0f1d31"
    LINE = "#1b3352"
    ACCENT = "#2f8cff"
    TEXT = "#eaf2ff"
    DIM = "#7f95b5"
    DANGER = "#ff6b6b"

    def __init__(self):
        self.ok = False
        self.username = "admin"
        self._login_shown = False
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.configure(bg=self.BG)
        self._splash()

    def _center(self, w, h):
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = (sw - w) // 2, max(0, (sh - h) // 2 - 24)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _clear(self):
        for w in self.root.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

    def _drag_bind(self, widget):
        widget.bind("<ButtonPress-1>", self._drag_start)
        widget.bind("<B1-Motion>", self._drag_move)

    def _drag_start(self, e):
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _splash(self):
        self._center(680, 380)
        self.root.deiconify()
        box = tk.Frame(self.root, bg=self.BG)
        box.pack(fill="both", expand=True)
        tk.Label(box, text="旅客服务系统", bg=self.BG, fg=self.ACCENT,
                 font=("Microsoft YaHei UI", 10, "bold")).pack(pady=(78, 6))
        tk.Label(box, text="智能管理广播平台", bg=self.BG, fg=self.TEXT,
                 font=("Microsoft YaHei UI", 26, "bold")).pack()
        tk.Label(box, text="PASSENGER SERVICE BROADCAST", bg=self.BG, fg=self.DIM,
                 font=("Consolas", 9)).pack(pady=(8, 28))
        tk.Frame(box, bg=self.ACCENT, height=2, width=280).pack()
        tk.Label(box, text="正在启动…", bg=self.BG, fg=self.DIM,
                 font=("Microsoft YaHei UI", 10)).pack(pady=(24, 0))
        tk.Label(box, text="V26.10.2", bg=self.BG, fg="#425a7a",
                 font=("Consolas", 8)).pack(side="bottom", pady=16)
        self.root.bind("<Button-1>", lambda e: self._show_login())
        self._splash_after = self.root.after(1200, self._show_login)

    def _show_login(self):
        if getattr(self, "_login_shown", False):
            return
        self._login_shown = True
        try:
            self.root.after_cancel(getattr(self, "_splash_after", None))
        except Exception:
            pass
        try:
            self.root.unbind("<Button-1>")
        except Exception:
            pass
        self._clear()
        self._center(760, 470)
        cfg_user, cfg_pwd, remember = _read_login_cfg()

        bar = tk.Frame(self.root, bg=self.BG, height=38)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        t = tk.Label(bar, text="登录", bg=self.BG, fg=self.DIM,
                     font=("Microsoft YaHei UI", 10))
        t.pack(side="left", padx=16)
        close = tk.Button(bar, text="关闭", command=self._close, bg=self.BG, fg=self.DIM,
                          activebackground=self.BG, activeforeground=self.TEXT,
                          relief="flat", bd=0, font=("Microsoft YaHei UI", 10), cursor="hand2")
        close.pack(side="right", padx=10)
        for w in (bar, t):
            self._drag_bind(w)

        tk.Label(self.root, text="旅客服务系统智能管理广播平台", bg=self.BG, fg=self.TEXT,
                 font=("Microsoft YaHei UI", 22, "bold")).pack(pady=(26, 4))
        tk.Label(self.root, text="请输入账号和密码进入控制台", bg=self.BG, fg=self.DIM,
                 font=("Microsoft YaHei UI", 10)).pack(pady=(0, 26))

        form = tk.Frame(self.root, bg=self.BG)
        form.pack()
        tk.Label(form, text="账号", bg=self.BG, fg=self.DIM,
                 font=("Microsoft YaHei UI", 10), anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.user_var = tk.StringVar(value=cfg_user)
        ent_user = tk.Entry(form, textvariable=self.user_var, width=34,
                            bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT,
                            relief="flat", bd=0, highlightthickness=1,
                            highlightbackground=self.LINE, highlightcolor=self.ACCENT,
                            font=("Microsoft YaHei UI", 12))
        ent_user.grid(row=1, column=0, ipady=9, pady=(0, 14))

        tk.Label(form, text="密码", bg=self.BG, fg=self.DIM,
                 font=("Microsoft YaHei UI", 10), anchor="w").grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.pwd_var = tk.StringVar(value=cfg_pwd)
        ent_pwd = tk.Entry(form, textvariable=self.pwd_var, width=34, show="*",
                           bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT,
                           relief="flat", bd=0, highlightthickness=1,
                           highlightbackground=self.LINE, highlightcolor=self.ACCENT,
                           font=("Microsoft YaHei UI", 12))
        ent_pwd.grid(row=3, column=0, ipady=9, pady=(0, 10))

        self.remember_var = tk.BooleanVar(value=bool(remember))
        chk = tk.Checkbutton(form, text="记住密码", variable=self.remember_var,
                             bg=self.BG, fg=self.DIM, activebackground=self.BG,
                             activeforeground=self.TEXT, selectcolor=self.PANEL,
                             bd=0, highlightthickness=0, font=("Microsoft YaHei UI", 9))
        chk.grid(row=4, column=0, sticky="w", pady=(0, 12))

        btn = tk.Button(form, text="登  录", command=self._do_login,
                        bg=self.ACCENT, fg="#ffffff", activebackground="#2578e0",
                        activeforeground="#ffffff", relief="flat", bd=0,
                        font=("Microsoft YaHei UI", 12, "bold"), cursor="hand2")
        btn.grid(row=5, column=0, sticky="ew", ipady=8)
        self.err = tk.Label(self.root, text="", bg=self.BG, fg=self.DANGER,
                            font=("Microsoft YaHei UI", 9))
        self.err.pack(pady=(10, 0))

        ent_user.focus_set()
        ent_user.bind("<Return>", lambda e: ent_pwd.focus_set())
        ent_pwd.bind("<Return>", lambda e: self._do_login())
        self.root.bind("<Escape>", lambda e: self._close())

    def _do_login(self):
        u = self.user_var.get().strip()
        p = self.pwd_var.get()
        cfg_user, cfg_pwd, _ = _read_login_cfg()
        if u != cfg_user or p != cfg_pwd:
            self.err.configure(text="账号或密码错误")
            return
        if self.remember_var.get():
            _save_login_cfg(u, p, True)
        else:
            _save_login_cfg(u, "", False)
        self.ok = True
        self.username = u
        self.root.destroy()

    def _close(self):
        self.ok = False
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()
        return self.ok, self.username


def _read_login_cfg():
    """读取本地登录配置；缺省 admin/123456，不依赖后端。"""
    import configparser
    u, p, remember = "admin", "123456", False
    try:
        cp = configparser.ConfigParser()
        cp.read(os.path.join(get_project_root(), "config.ini"), encoding="utf-8")
        if cp.has_section("login"):
            u = (cp.get("login", "username", fallback="") or "admin").strip() or "admin"
            p = cp.get("login", "password", fallback="")
            if not p:
                p = "123456"
            remember = cp.get("login", "remember_pwd", fallback="0").strip() in ("1", "true", "True")
    except Exception:
        pass
    return u, p, remember


def _save_login_cfg(username, password, remember):
    import configparser
    try:
        path = os.path.join(get_project_root(), "config.ini")
        cp = configparser.ConfigParser()
        cp.read(path, encoding="utf-8")
        if not cp.has_section("login"):
            cp.add_section("login")
        cp.set("login", "username", username)
        cp.set("login", "password", password if remember else "")
        cp.set("login", "remember_user", "1")
        cp.set("login", "remember_pwd", "1" if remember else "0")
        with open(path, "w", encoding="utf-8") as f:
            cp.write(f)
    except Exception:
        pass


if __name__ == "__main__":
    # ===== 启动自检：关键文件缺失时提示（不阻止启动，避免静默闪退）=====
    try:
        _miss = []
        for _name, _chk in (
            ("车次数据 trains.json", lambda: os.path.exists(os.path.join(get_project_root(), "trains.json"))),
            ("系统配置 system_config.json", lambda: os.path.exists(os.path.join(get_project_root(), "system_config.json"))),
            ("广播配置 bcast_config.json", lambda: os.path.exists(os.path.join(get_project_root(), "bcast_config.json"))),
            ("音频库 audio", lambda: (_audio_usable(os.path.join(get_project_root(), "audio")) or
                                       os.path.isdir(os.path.join(get_project_root(), "audio", "语音包")))),
        ):
            try:
                if not _chk():
                    _miss.append(_name)
            except Exception:
                pass
        if _miss:
            try:
                import tkinter.messagebox as _mb
                _mb.showwarning("资源缺失提示",
                    "以下文件/目录未找到，部分功能可能不可用：\n" +
                    "\n".join("· " + m for m in _miss) +
                    "\n\n请确认程序文件夹完整（含 audio、*.json 等），或重新解压完整发布包。")
            except Exception:
                pass
    except Exception:
        pass

    # ===== 全局异常兜底：启动/运行异常写入 error.log（闪退时可诊断）=====
    try:
        _ok, _user = _StartupApp().run()
        if not _ok:
            raise SystemExit(0)
        app = BroadcastApp(username=_user)
        app.mainloop()
    except Exception as _e:
        import traceback as _tb
        _err = _tb.format_exc()
        _logp = os.path.join(get_app_root(), "error.log")
        try:
            with open(_logp, "w", encoding="utf-8") as _f:
                _f.write("旅客服务智能管理广播系统 启动异常\n" + _err)
        except Exception:
            pass
        try:
            import tkinter.messagebox as _mb
            _mb.showerror("启动失败",
                          "程序启动失败，错误信息已写入：\n" + _logp +
                          "\n\n请将 error.log 内容反馈给开发者。\n\n" + _err[-1200:])
        except Exception:
            pass
        raise