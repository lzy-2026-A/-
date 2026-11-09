# -*- coding: utf-8 -*-
"""Apply logout flash-exit fix + small train-panel UI tweak to main.cpp."""
import os
import sys

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.cpp")
print("TARGET", p)
print("EXISTS", os.path.exists(p))

with open(p, "r", encoding="utf-8", newline="") as f:
    text = f.read()

print("CHARS", len(text))
print("LINES", text.count("\n") + (0 if text.endswith("\n") else 1))
print("HAS_CRLF", "\r\n" in text)
print("HAS_EnsureLoginWindow", "EnsureLoginWindow" in text)
print("HAS_g_hInst", "g_hInst" in text)
print("HAS_IDC_LBL_NUM", "IDC_LBL_NUM" in text)

nl = "\r\n" if "\r\n" in text else "\n"
applied = []
missed = []


def rep(old, new, tag):
    global text
    if old in text:
        text = text.replace(old, new, 1)
        applied.append(tag)
        print("OK", tag)
        return True
    missed.append(tag)
    print("MISS", tag)
    return False


# 1) g_hInst
rep(
    "static HWND g_hMain = nullptr;" + nl +
    "static HWND g_hLogin = nullptr;" + nl,
    "static HWND g_hMain = nullptr;" + nl +
    "static HWND g_hLogin = nullptr;" + nl +
    "static HINSTANCE g_hInst = nullptr;" + nl,
    "add_g_hInst",
)

# 2) train label IDs
rep(
    "#define IDC_LBL_VOL      2614" + nl,
    "#define IDC_LBL_VOL      2614" + nl +
    "#define IDC_LBL_NUM      2110" + nl +
    "#define IDC_LBL_DEP      2111" + nl +
    "#define IDC_LBL_ARR      2112" + nl +
    "#define IDC_LBL_DEPT     2113" + nl +
    "#define IDC_LBL_PLAT     2114" + nl +
    "#define IDC_LBL_STAT     2115" + nl,
    "add_train_label_ids",
)

# 3) ShowLoginWindow rewrite
old_show = (
    "static void ShowLoginWindow() {" + nl +
    "    g_loggedIn = false;" + nl +
    "    if (g_hMain && IsWindow(g_hMain)) ShowWindow(g_hMain, SW_HIDE);" + nl +
    "    if (g_hLogin && IsWindow(g_hLogin)) {" + nl +
    "        ShowWindow(g_hLogin, SW_SHOW);" + nl +
    "        SetForegroundWindow(g_hLogin);" + nl +
    "    }" + nl +
    "}" + nl
)
new_show = (
    "static HWND EnsureLoginWindow() {" + nl +
    "    if (g_hLogin && IsWindow(g_hLogin)) return g_hLogin;" + nl +
    "    if (!g_hInst) return nullptr;" + nl +
    "    HWND login = CreateWindowExW(0, L\"LoginWin\", L\"\"," + nl +
    "        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX," + nl +
    "        0, 0, 800, 500, nullptr, nullptr, g_hInst, nullptr);" + nl +
    "    g_hLogin = login;" + nl +
    "    if (login) {" + nl +
    "        int sw = GetSystemMetrics(SM_CXSCREEN);" + nl +
    "        int sh = GetSystemMetrics(SM_CYSCREEN);" + nl +
    "        SetWindowPos(login, nullptr, (sw - 800) / 2, (sh - 500) / 2, 0, 0, SWP_NOSIZE | SWP_NOZORDER);" + nl +
    "    }" + nl +
    "    return login;" + nl +
    "}" + nl +
    nl +
    "static void ShowLoginWindow() {" + nl +
    "    g_loggedIn = false;" + nl +
    "    HWND login = EnsureLoginWindow();" + nl +
    "    if (!login || !IsWindow(login)) {" + nl +
    "        // 登录窗不可用时绝不能把主窗藏掉，否则看起来像闪退" + nl +
    "        return;" + nl +
    "    }" + nl +
    "    int sw = GetSystemMetrics(SM_CXSCREEN);" + nl +
    "    int sh = GetSystemMetrics(SM_CYSCREEN);" + nl +
    "    SetWindowPos(login, HWND_TOP, (sw - 800) / 2, (sh - 500) / 2, 800, 500, SWP_SHOWWINDOW);" + nl +
    "    HWND hPwd = GetDlgItem(login, IDC_PWD);" + nl +
    "    if (hPwd) SetWindowTextW(hPwd, L\"\");" + nl +
    "    ShowWindow(login, SW_SHOWNORMAL);" + nl +
    "    UpdateWindow(login);" + nl +
    "    SetForegroundWindow(login);" + nl +
    "    if (g_hMain && IsWindow(g_hMain)) ShowWindow(g_hMain, SW_HIDE);" + nl +
    "    g_isLogout = false;" + nl +
    "}" + nl
)
if not rep(old_show, new_show, "rewrite_ShowLoginWindow"):
    # dump nearby for diagnosis
    idx = text.find("static void ShowLoginWindow")
    print("ShowLoginWindow idx", idx)
    if idx >= 0:
        snippet = text[idx:idx + 280]
        print("SNIP_SHOW_REPR", repr(snippet))

# 4) splash no PostQuitMessage
old_splash = (
    "            DestroyWindow(hwnd);" + nl +
    "            PostQuitMessage(0); // 让 splash 消息循环退出，继续创建登录窗口" + nl
)
new_splash = (
    "            DestroyWindow(hwnd);" + nl +
    "            // 不再 PostQuitMessage：WM_QUIT 是线程级消息，会漏进后面的主循环导致启动后直接退出" + nl
)
if not rep(old_splash, new_splash, "splash_no_quit"):
    idx = text.find("PostQuitMessage(0)")
    print("first PostQuitMessage idx", idx)
    # find splash comment
    idx2 = text.find("让 splash")
    print("splash comment idx", idx2)
    if idx2 >= 0:
        print("SNIP_SPLASH_REPR", repr(text[idx2 - 80:idx2 + 80]))

# 5) splash loop
old_loop = (
    "        MSG sm;" + nl +
    "        while (GetMessageW(&sm, nullptr, 0, 0)) {" + nl +
    "            if (!IsWindow(splash)) break;" + nl +
    "            TranslateMessage(&sm);" + nl +
    "            DispatchMessageW(&sm);" + nl +
    "        }" + nl
)
new_loop = (
    "        MSG sm;" + nl +
    "        while (IsWindow(splash)) {" + nl +
    "            if (PeekMessageW(&sm, nullptr, 0, 0, PM_REMOVE)) {" + nl +
    "                if (sm.message == WM_QUIT) continue; // 丢弃误入的退出消息" + nl +
    "                TranslateMessage(&sm);" + nl +
    "                DispatchMessageW(&sm);" + nl +
    "            } else {" + nl +
    "                WaitMessage();" + nl +
    "            }" + nl +
    "        }" + nl +
    "        MSG drain;" + nl +
    "        while (PeekMessageW(&drain, nullptr, WM_QUIT, WM_QUIT, PM_REMOVE)) {}" + nl
)
if not rep(old_loop, new_loop, "splash_loop_safe"):
    idx = text.find("GetMessageW(&sm")
    print("GetMessageW sm idx", idx)
    if idx >= 0:
        print("SNIP_LOOP_REPR", repr(text[idx - 40:idx + 220]))

# 6) login exit
old_exit = (
    "        } else if (id == IDC_BTN_EXIT) {" + nl +
    "            if (customMessageBoxW(hwnd, L\"确定退出系统？\", L\"确认\", MB_YESNO) == IDOK) {" + nl +
    "                DestroyWindow(hwnd);" + nl +
    "                PostQuitMessage(0);" + nl +
    "            }" + nl +
    "        }" + nl
)
new_exit = (
    "        } else if (id == IDC_BTN_EXIT) {" + nl +
    "            if (customMessageBoxW(hwnd, L\"确定退出系统？\", L\"确认\", MB_YESNO) == IDOK) {" + nl +
    "                g_isLogout = false;" + nl +
    "                PostQuitMessage(0);" + nl +
    "            }" + nl +
    "        }" + nl
)
if not rep(old_exit, new_exit, "login_exit_no_destroy"):
    idx = text.find("确定退出系统")
    print("exit text idx", idx)
    if idx >= 0:
        print("SNIP_EXIT_REPR", repr(text[idx - 80:idx + 180]))

# 7) login WM_DESTROY
old_dest = (
    "    case WM_DESTROY:" + nl +
    "        if (g_hLoginBg) DeleteObject(g_hLoginBg);" + nl +
    "        if (g_hLoginLeftBg) DeleteObject(g_hLoginLeftBg);" + nl +
    "        if (g_hLoginEditBg) DeleteObject(g_hLoginEditBg);" + nl +
    "        if (g_fLoginBtn) DeleteObject(g_fLoginBtn);" + nl +
    "        g_hLogin = nullptr;" + nl +
    "        return 0;" + nl
)
new_dest = (
    "    case WM_DESTROY:" + nl +
    "        if (g_hLoginBg) { DeleteObject(g_hLoginBg); g_hLoginBg = nullptr; }" + nl +
    "        if (g_hLoginLeftBg) { DeleteObject(g_hLoginLeftBg); g_hLoginLeftBg = nullptr; }" + nl +
    "        if (g_hLoginEditBg) { DeleteObject(g_hLoginEditBg); g_hLoginEditBg = nullptr; }" + nl +
    "        if (g_fLoginBtn) { DeleteObject(g_fLoginBtn); g_fLoginBtn = nullptr; }" + nl +
    "        if (g_hLogin == hwnd) g_hLogin = nullptr;" + nl +
    "        return 0;" + nl
)
if not rep(old_dest, new_dest, "login_destroy_null"):
    idx = text.find("if (g_hLoginBg) DeleteObject")
    print("login destroy idx", idx)
    if idx >= 0:
        print("SNIP_DEST_REPR", repr(text[idx - 40:idx + 280]))

# 8) g_hInst = hInst
old_win = (
    "int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, LPWSTR, int nCmd) {" + nl +
    "    // 启动声音（可自定义）" + nl +
    "    playStartupSound();" + nl
)
new_win = (
    "int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, LPWSTR, int nCmd) {" + nl +
    "    g_hInst = hInst;" + nl +
    "    // 启动声音（可自定义）" + nl +
    "    playStartupSound();" + nl
)
if not rep(old_win, new_win, "set_g_hInst"):
    idx = text.find("int WINAPI wWinMain")
    print("wWinMain idx", idx)
    if idx >= 0:
        print("SNIP_WIN_REPR", repr(text[idx:idx + 180]))

# 9) train labels
old_lbl = (
    '        CreateWindowExW(0, L"STATIC", L"车次号：", WS_CHILD|WS_VISIBLE, 20, 340, 60, 22, panel1, nullptr, nullptr, nullptr);' + nl +
    '        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 90, 338, 80, 24, panel1, (HMENU)IDC_NUM, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"STATIC", L"始发站：", WS_CHILD|WS_VISIBLE, 210, 340, 60, 22, panel1, nullptr, nullptr, nullptr);' + nl +
    '        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 270, 338, 90, 24, panel1, (HMENU)IDC_DEP, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"STATIC", L"到达站：", WS_CHILD|WS_VISIBLE, 380, 340, 60, 22, panel1, nullptr, nullptr, nullptr);' + nl +
    '        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 440, 338, 90, 24, panel1, (HMENU)IDC_ARR, nullptr, nullptr);' + nl +
    nl +
    '        CreateWindowExW(0, L"STATIC", L"发车时间：", WS_CHILD|WS_VISIBLE, 20, 372, 60, 22, panel1, nullptr, nullptr, nullptr);' + nl +
    '        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 90, 370, 80, 24, panel1, (HMENU)IDC_DEPT, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"STATIC", L"站台：", WS_CHILD|WS_VISIBLE, 210, 372, 60, 22, panel1, nullptr, nullptr, nullptr);' + nl +
    '        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 250, 370, 40, 24, panel1, (HMENU)IDC_PLAT, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"STATIC", L"状态：", WS_CHILD|WS_VISIBLE, 320, 372, 60, 22, panel1, nullptr, nullptr, nullptr);' + nl
)
new_lbl = (
    '        CreateWindowExW(0, L"STATIC", L"车次号：", WS_CHILD|WS_VISIBLE, 20, 340, 70, 22, panel1, (HMENU)IDC_LBL_NUM, nullptr, nullptr);' + nl +
    '        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 92, 338, 90, 24, panel1, (HMENU)IDC_NUM, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"STATIC", L"始发站：", WS_CHILD|WS_VISIBLE, 200, 340, 70, 22, panel1, (HMENU)IDC_LBL_DEP, nullptr, nullptr);' + nl +
    '        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 272, 338, 100, 24, panel1, (HMENU)IDC_DEP, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"STATIC", L"到达站：", WS_CHILD|WS_VISIBLE, 390, 340, 70, 22, panel1, (HMENU)IDC_LBL_ARR, nullptr, nullptr);' + nl +
    '        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 462, 338, 100, 24, panel1, (HMENU)IDC_ARR, nullptr, nullptr);' + nl +
    nl +
    '        CreateWindowExW(0, L"STATIC", L"发车时间：", WS_CHILD|WS_VISIBLE, 20, 376, 70, 22, panel1, (HMENU)IDC_LBL_DEPT, nullptr, nullptr);' + nl +
    '        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 92, 374, 90, 24, panel1, (HMENU)IDC_DEPT, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"STATIC", L"站台：", WS_CHILD|WS_VISIBLE, 200, 376, 50, 22, panel1, (HMENU)IDC_LBL_PLAT, nullptr, nullptr);' + nl +
    '        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 252, 374, 50, 24, panel1, (HMENU)IDC_PLAT, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"STATIC", L"状态：", WS_CHILD|WS_VISIBLE, 320, 376, 50, 22, panel1, (HMENU)IDC_LBL_STAT, nullptr, nullptr);' + nl
)
if not rep(old_lbl, new_lbl, "train_label_ids_create"):
    idx = text.find('L"车次号：')
    print("train label idx", idx)
    if idx >= 0:
        print("SNIP_LBL_REPR", repr(text[idx - 40:idx + 200]))

# 10) train buttons
old_btn = (
    '        CreateWindowExW(0, L"BUTTON", L"添加", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 20, 410, 80, 28, panel1, (HMENU)IDC_ADD, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"BUTTON", L"更新选中状态", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 105, 410, 110, 28, panel1, (HMENU)IDC_UPD, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"BUTTON", L"移除选中", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 220, 410, 90, 28, panel1, (HMENU)IDC_DEL, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"BUTTON", L"刷新", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 315, 410, 80, 28, panel1, (HMENU)IDC_REFRESH, nullptr, nullptr);' + nl
)
new_btn = (
    '        CreateWindowExW(0, L"BUTTON", L"添加", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 20, 416, 88, 30, panel1, (HMENU)IDC_ADD, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"BUTTON", L"更新选中状态", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 116, 416, 120, 30, panel1, (HMENU)IDC_UPD, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"BUTTON", L"移除选中", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 244, 416, 96, 30, panel1, (HMENU)IDC_DEL, nullptr, nullptr);' + nl +
    '        CreateWindowExW(0, L"BUTTON", L"刷新", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 348, 416, 88, 30, panel1, (HMENU)IDC_REFRESH, nullptr, nullptr);' + nl
)
if not rep(old_btn, new_btn, "train_buttons_layout"):
    idx = text.find('L"添加", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 20, 410')
    print("add btn idx", idx)
    if idx >= 0:
        print("SNIP_BTN_REPR", repr(text[idx - 40:idx + 280]))

# extra UI: LayoutMain train labels if we can find the train edit moves
# leave if not present; labels without IDs previously couldn't be moved

print("APPLIED", len(applied), applied)
print("MISSED", len(missed), missed)

if not applied:
    print("NO_WRITE")
    sys.exit(2)

bak = p + ".prepatch_s26.bak"
if not os.path.exists(bak):
    with open(p, "rb") as src, open(bak, "wb") as dst:
        dst.write(src.read())
    print("BACKUP", bak)
else:
    print("BACKUP_EXISTS")

with open(p, "w", encoding="utf-8", newline="") as f:
    f.write(text)

print("WROTE", len(text))
checks = [
    "static HINSTANCE g_hInst",
    "EnsureLoginWindow",
    "绝不能把主窗藏掉",
    "不再 PostQuitMessage",
    "PeekMessageW(&sm",
    "g_hLoginBg = nullptr",
    "IDC_LBL_NUM",
    "g_hInst = hInst",
]
with open(p, "r", encoding="utf-8") as f:
    v = f.read()
for c in checks:
    print(("HAS " if c in v else "LACK ") + c)
print("DONE")
