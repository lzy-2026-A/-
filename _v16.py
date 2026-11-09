import ctypes, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
from ctypes import wintypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.ShowWindow(kernel32.GetConsoleWindow(), 6)
time.sleep(0.2)
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
allw = []
def cb(h, l):
    cls = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(h, cls, 128)
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(h, buf, 256)
    allw.append((h, cls.value, buf.value))
    return True
user32.EnumWindows(WNDENUMPROC(cb), 0)
# 找豆包主窗口（标题含"豆包"且可见）
doubao = None
for h, cls, t in allw:
    if user32.IsWindowVisible(h) and ("豆包" in t or "Doubao" in t):
        doubao = h
        print(f"豆包窗口: {t[:40]} cls={cls}")
        break
if doubao:
    user32.ShowWindow(doubao, 6)  # 最小化
    time.sleep(0.8)
# main_ui 前置
mains = [h for h, cls, t in allw if cls == "TkTopLevel"]
if mains:
    hwnd = mains[0]
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.8)
    user32.SetCursorPos(80, 313)
    time.sleep(0.2)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(2.5)
    from PIL import ImageGrab
    r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
    img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
    img.save(r"D:\桌面\旅客服务系统智能管理广播平台\_shot_bigscreen5.png")
    print(f"大屏截图 {img.size}")
else:
    print("main_ui 未找到")
if doubao:
    user32.ShowWindow(doubao, 9)  # 恢复豆包
user32.ShowWindow(kernel32.GetConsoleWindow(), 9)