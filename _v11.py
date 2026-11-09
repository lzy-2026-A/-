import ctypes, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
from ctypes import wintypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.ShowWindow(kernel32.GetConsoleWindow(), 6)
time.sleep(0.2)
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
def find_all(clsname):
    out = []
    def cb(h, l):
        cls = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(h, cls, 128)
        if cls.value == clsname and user32.IsWindowVisible(h):
            out.append(h)
        return True
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out
from PIL import ImageGrab
# 找 customtkinter 窗口（Tk 类）
wins = find_all("TkTopLevel")
if not wins:
    # 备用：找所有可见顶层窗口
    wins = []
    def cb2(h, l):
        if user32.IsWindowVisible(h):
            wins.append(h)
        return True
    user32.EnumWindows(WNDENUMPROC(cb2), 0)
    wins = [h for h in wins if user32.IsWindowVisible(h)]
for i, h in enumerate(wins[:3]):
    buf = ctypes.create_unicode_buffer(200)
    user32.GetWindowTextW(h, buf, 200)
    r = wintypes.RECT(); user32.GetWindowRect(h, ctypes.byref(r))
    print(f"[{i}] {buf.value[:40]} rect=({r.left},{r.top},{r.right},{r.bottom})")
    if i == 0:
        img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
        img.save(r"D:\桌面\旅客服务系统智能管理广播平台\_shot_mainui.png")
        print("主窗口截图已保存")
user32.ShowWindow(kernel32.GetConsoleWindow(), 9)