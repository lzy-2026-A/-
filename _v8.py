import ctypes, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
from ctypes import wintypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.ShowWindow(kernel32.GetConsoleWindow(), 6)
time.sleep(0.2)
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
def find(clsname):
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
got = False
t0 = time.time()
while time.time()-t0 < 10 and not got:
    w = find("SplashWin")
    if w:
        splash = w[0]
        r = wintypes.RECT()
        user32.GetWindowRect(splash, ctypes.byref(r))
        img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
        img.save(r"D:\桌面\旅客服务系统智能管理广播平台\_shot_Splash_v8.png")
        got = True
        print(f"截图 {img.size} @ rect=({r.left},{r.top},{r.right},{r.bottom})")
        break
    time.sleep(0.05)
if not got:
    print("splash 未出现")
user32.ShowWindow(kernel32.GetConsoleWindow(), 9)