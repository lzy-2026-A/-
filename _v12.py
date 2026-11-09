import ctypes, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
from ctypes import wintypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.ShowWindow(kernel32.GetConsoleWindow(), 6)
time.sleep(0.2)
# 点击"车站大屏"选项卡（屏幕坐标，窗口 -7,-7 起）
user32.SetCursorPos(80, 322)
time.sleep(0.2)
user32.mouse_event(0x0002, 0, 0, 0, 0)
user32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(2.5)
# 截图窗口
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
    img.save(r"D:\桌面\旅客服务系统智能管理广播平台\_shot_bigscreen.png")
    print(f"大屏截图 {img.size} rect=({r.left},{r.top},{r.right},{r.bottom})")
else:
    print("窗口未找到")
user32.ShowWindow(kernel32.GetConsoleWindow(), 9)