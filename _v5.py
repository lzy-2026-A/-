import ctypes, time, sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
from ctypes import wintypes
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
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
def snap(hwnd, path):
    r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
    w = r.right-r.left; h = r.bottom-r.top
    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(memdc, bmp)
    user32.PrintWindow(hwnd, memdc, 3)
    # GetDIBits
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD),("biWidth", ctypes.c_long),("biHeight", ctypes.c_long),
                    ("biPlanes", wintypes.WORD),("biBitCount", wintypes.WORD),("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),("biXPelsPerMeter", ctypes.c_long),("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", wintypes.DWORD),("biClrImportant", wintypes.DWORD)]
    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w; bmi.biHeight = -h; bmi.biPlanes = 1; bmi.biBitCount = 32; bmi.biCompression = 0
    buf = ctypes.create_string_buffer(w*h*4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    # 存 BMP
    bmp_header = b'BM' + struct.pack('<I', 54+w*h*4) + struct.pack('<IHHI', 0,0,54,0)
    dib = bmi.biSize.to_bytes(4,'little') + struct.pack('<iihhIIiiII', bmi.biWidth, bmi.biHeight, bmi.biPlanes, bmi.biBitCount, bmi.biCompression, bmi.biSizeImage, bmi.biXPelsPerMeter, bmi.biYPelsPerMeter, bmi.biClrUsed, bmi.biClrImportant)
    raw = bytearray(buf.raw)
    # BGRA->BGR
    for i in range(0, len(raw), 4):
        raw[i], raw[i+2] = raw[i+2], raw[i]
    with open(path,'wb') as f:
        f.write(bmp_header); f.write(dib); f.write(bytes(raw))
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(memdc); user32.ReleaseDC(hwnd, hdc)
    print(f"截图 {path} {w}x{h}")
# 1) splash 图标 + 截图
splash = None
t0 = time.time()
while time.time()-t0 < 12:
    w = find("SplashWin")
    if w: splash = w[0]; break
    time.sleep(0.3)
if splash:
    hic = user32.SendMessageW(splash, 0x007F, 1, 0)
    print(f"Splash 窗口图标: {hic} -> {'已设置' if hic else '未设置'}")
    snap(splash, r"D:\桌面\旅客服务系统智能管理广播平台\_shot_Splash_v5.png")
else:
    print("splash 未出现")
# 2) 登录窗口图标（等 splash 结束）
login = None
t0 = time.time()
while time.time()-t0 < 25:
    w = find("LoginWin")
    if w: login = w[0]; break
    time.sleep(0.5)
if login:
    hic = user32.SendMessageW(login, 0x007F, 1, 0)
    print(f"Login 窗口图标: {hic} -> {'已设置' if hic else '未设置'}")
    snap(login, r"D:\桌面\旅客服务系统智能管理广播平台\_shot_Login_v5.png")
else:
    print("登录窗口未出现")