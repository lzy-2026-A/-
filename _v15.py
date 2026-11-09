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
wins = find_all("TkTopLevel")
if not wins:
    print("窗口未找到"); sys.exit()
hwnd = wins[0]
# 前置
user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0002 | 0x0001)
user32.ShowWindow(hwnd, 9)  # SW_RESTORE
user32.SetForegroundWindow(hwnd)
time.sleep(0.8)
# 用真实鼠标点击（前置后）
user32.SetCursorPos(80, 318)
time.sleep(0.2)
user32.mouse_event(0x0002, 0, 0, 0, 0)
user32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(1.5)
user32.SetCursorPos(80, 313)
time.sleep(0.2)
user32.mouse_event(0x0002, 0, 0, 0, 0)
user32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(2.5)
from PIL import ImageGrab
r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
img.save(r"D:\桌面\旅客服务系统智能管理广播平台\_shot_bigscreen4.png")
print(f"截图 {img.size}")
user32.ShowWindow(kernel32.GetConsoleWindow(), 9)