import ctypes, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
from ctypes import wintypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.ShowWindow(kernel32.GetConsoleWindow(), 6)
time.sleep(0.2)
# 车站大屏：相对窗口 y≈0.386*830≈320 → 屏幕 y = -7+320 = 313
for y in (313, 318, 308):
    user32.SetCursorPos(80, y)
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.6)
time.sleep(2.0)
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
wins = find_all("TkTopLevel")
from PIL import ImageGrab
if wins:
    r = wintypes.RECT(); user32.GetWindowRect(wins[0], ctypes.byref(r))
    img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
    img.save(r"D:\桌面\旅客服务系统智能管理广播平台\_shot_bigscreen2.png")
    print(f"截图 {img.size}")
user32.ShowWindow(kernel32.GetConsoleWindow(), 9)