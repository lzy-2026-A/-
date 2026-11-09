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
login = None
t0 = time.time()
while time.time()-t0 < 25:
    w = find("LoginWin")
    if w:
        login = w[0]; break
    time.sleep(0.3)
if login:
    user32.SetWindowPos(login, -1, 0, 0, 0, 0, 0x0002 | 0x0001)
    time.sleep(0.2)
    r = wintypes.RECT()
    user32.GetWindowRect(login, ctypes.byref(r))
    img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
    img.save(r"D:\桌面\旅客服务系统智能管理广播平台\_shot_Login_v10.png")
    hic = user32.SendMessageW(login, 0x007F, 1, 0)
    print(f"登录截图 {img.size} 图标={hic}")
else:
    print("登录未出现")
user32.ShowWindow(kernel32.GetConsoleWindow(), 9)