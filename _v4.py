import ctypes, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
from ctypes import wintypes
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
# 图标验证
try:
    from System.Drawing import Icon
    ic = Icon.ExtractAssociatedIcon(r"D:\桌面\旅客服务系统智能管理广播平台\完整打包_v26.10.2\frontend.exe")
    print(f"exe 内嵌图标: {ic.Width}x{ic.Height} -> {'有' if ic else '无'}")
except Exception as e:
    print("图标提取失败:", e)
# 找 splash 窗口
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
splash = None
t0 = time.time()
while time.time() - t0 < 15:
    w = find("SplashWin")
    if w: splash = w[0]; break
    time.sleep(0.3)
if not splash:
    print("splash 未出现"); sys.exit()
# WM_GETICON 检查窗口图标
ICON_BIG = 1; WM_GETICON = 0x007F
hic = user32.SendMessageW(splash, WM_GETICON, ICON_BIG, 0)
print(f"窗口图标句柄: {hic} -> {'已设置(新图标)' if hic else '未设置(默认)'}")
# 截图（PrintWindow）
from PIL import ImageGrab
r = ctypes.wintypes.RECT()
user32.GetWindowRect(splash, ctypes.byref(r))
w = r.right - r.left; h = r.bottom - r.top
user32.SetForegroundWindow(splash)
time.sleep(0.4)
img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
img.save(r"D:\桌面\旅客服务系统智能管理广播平台\_shot_SplashWin_v4.png")
print(f"截图: {w}x{h} 已保存")