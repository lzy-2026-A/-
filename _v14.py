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
# 客户区逻辑坐标点击（车站大屏按钮：x=80, y≈0.39*664≈259 附近试 3 个点）
WM_LBUTTONDOWN = 0x0201; WM_LBUTTONUP = 0x0202; MK_LBUTTON = 0x0001
for y in (252, 260, 268):
    lp = (y << 16) | 80
    user32.SendMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    user32.SendMessageW(hwnd, WM_LBUTTONUP, 0, lp)
    time.sleep(0.5)
time.sleep(2.0)
from PIL import ImageGrab
r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
img.save(r"D:\桌面\旅客服务系统智能管理广播平台\_shot_bigscreen3.png")
print(f"截图 {img.size}")
user32.ShowWindow(kernel32.GetConsoleWindow(), 9)