import ctypes, time, sys, io, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
from ctypes import wintypes
user32 = ctypes.windll.user32
WM_SETTEXT = 0x000C; BM_CLICK = 0x00F5
IDC_USER = 1001; IDC_PWD = 1002; IDC_BTN_LOGIN = 1003
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
CHILDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
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
def child_by_id(hwnd_parent, cid):
    out = []
    def cb(h, l):
        if user32.GetDlgCtrlID(h) == cid: out.append(h)
        return True
    user32.EnumChildWindows(hwnd_parent, CHILDENUMPROC(cb), 0)
    return out[0] if out else None
# 等登录
login = None
t0 = time.time()
while time.time()-t0 < 25:
    w = find("LoginWin")
    if w: login = w[0]; break
    time.sleep(0.3)
print(f"登录窗口: {'出现' if login else '未出现'} ({round(time.time()-t0,1)}s)")
if login:
    u = child_by_id(login, IDC_USER); pw = child_by_id(login, IDC_PWD); btn = child_by_id(login, IDC_BTN_LOGIN)
    user32.SendMessageW(u, WM_SETTEXT, 0, "admin")
    user32.SendMessageW(pw, WM_SETTEXT, 0, "123456")
    time.sleep(0.4)
    user32.SendMessageW(btn, BM_CLICK, 0, 0)
# 等 main_ui.exe 进程 + 窗口
t1 = time.time()
proc_ok = win_ok = False
while time.time()-t1 < 30:
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq main_ui.exe"], capture_output=True, text=True)
    if "main_ui.exe" in r.stdout and not proc_ok:
        proc_ok = True
        print(f"main_ui.exe 进程出现: {round(time.time()-t1,1)}s")
    w = find("TkTopLevel")
    if w:
        buf = ctypes.create_unicode_buffer(200)
        user32.GetWindowTextW(w[0], buf, 200)
        if "旅客服务" in buf.value or "广播" in buf.value:
            win_ok = True
            print(f"主界面窗口: {buf.value[:30]}")
            break
    time.sleep(0.5)
print(f"回归结果: 进程={'OK' if proc_ok else 'FAIL'} 窗口={'OK' if win_ok else 'FAIL'}")