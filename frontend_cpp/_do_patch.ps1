$ErrorActionPreference = 'Stop'
$src = 'D:\桌面\旅客服务系统智能管理广播平台\frontend_cpp\main.cpp'
$bak = 'D:\桌面\旅客服务系统智能管理广播平台\frontend_cpp\main.cpp.prepatch'
$log = 'D:\桌面\旅客服务系统智能管理广播平台\frontend_cpp\_patch_log.txt'

function Log($m) {
    Add-Content -LiteralPath $log -Value $m -Encoding UTF8
}

Set-Content -LiteralPath $log -Value "PATCH START $(Get-Date -Format o)" -Encoding UTF8

$text = [System.IO.File]::ReadAllText($src)
[System.IO.File]::WriteAllText($bak, $text)
Log ("backup bytes=" + $text.Length)
Log ("orig lines=" + (($text -split "`n").Count))

$changes = @()

function ReplaceOnce($old, $new, $name) {
    $idx = $script:text.IndexOf($old)
    if ($idx -lt 0) {
        Log "FAIL replace $name : old text not found"
        throw "FAIL replace $name"
    }
    $idx2 = $script:text.IndexOf($old, $idx + 1)
    if ($idx2 -ge 0) {
        Log "FAIL replace $name : old text found more than once"
        throw "DUP replace $name"
    }
    $script:text = $script:text.Remove($idx, $old.Length).Insert($idx, $new)
    $script:changes += $name
    Log "OK $name"
}

# ---- A. IDC defines ----
$oldIds = @"
#define IDC_BTN_QUICK6  2606
#define IDC_BTN_QUICK7  2607
#define IDC_BTN_QUICK8  2608
#define IDC_BTN_QUICK9  2609
"@
$newIds = @"
#define IDC_BTN_QUICK6  2606
#define IDC_BTN_QUICK7  2607
#define IDC_BTN_QUICK8  2608
#define IDC_BTN_QUICK9  2609
#define IDC_LBL_BTYPE   2610
#define IDC_LBL_PRI     2611
#define IDC_LBL_MSG     2612
#define IDC_LBL_AUDIO   2613
#define IDC_LBL_VOL     2614
"@
ReplaceOnce $oldIds $newIds "A-add-IDC-labels"

# ---- A. globals near g_hMain ----
$oldGlobals = @"
static HWND g_hMain = nullptr;
static HWND g_hLoginWin = nullptr;
static bool g_loggedIn = false;
static bool g_isLogout = false; // 标记是否是退出登录
"@
$newGlobals = @"
static HWND g_hMain = nullptr;
static HWND g_hLogin = nullptr;
static bool g_loggedIn = false;
static bool g_isLogout = false; // 标记是否是退出登录
"@
ReplaceOnce $oldGlobals $newGlobals "A-unify-g_hLogin"

# replace remaining g_hLoginWin if any
if ($text.Contains('g_hLoginWin')) {
    $text = $text.Replace('g_hLoginWin', 'g_hLogin')
    $changes += 'A-replace-g_hLoginWin-usages'
    Log 'OK A-replace-g_hLoginWin-usages'
}

# ---- K. LayoutMain broadcast block ----
$oldLayout = @"
    // 广播区
    HWND grpBc = GetDlgItem(hwnd, IDC_GRP_BC);
    MoveWindow(grpBc, m, y, cw, 300, TRUE);
    HWND q1 = GetDlgItem(hwnd, IDC_BTN_QUICK1);
    HWND q2 = GetDlgItem(hwnd, IDC_BTN_QUICK2);
    HWND q3 = GetDlgItem(hwnd, IDC_BTN_QUICK3);
    HWND q4 = GetDlgItem(hwnd, IDC_BTN_QUICK4);
    HWND q5 = GetDlgItem(hwnd, IDC_BTN_QUICK5);
    HWND q6 = GetDlgItem(hwnd, IDC_BTN_QUICK6);
    HWND q7 = GetDlgItem(hwnd, IDC_BTN_QUICK7);
    HWND q8 = GetDlgItem(hwnd, IDC_BTN_QUICK8);
    HWND q9 = GetDlgItem(hwnd, IDC_BTN_QUICK9);
    int qGap = 6, qH = 38, qRowW = cw - 24;
    int qW = (qRowW - qGap * 4) / 5;
    int qx = 12, qy1 = 20, qy2 = 65;
    MoveWindow(q1, qx, qy1, qW, qH, TRUE);
    MoveWindow(q2, qx + (qW + qGap), qy1, qW, qH, TRUE);
    MoveWindow(q3, qx + (qW + qGap) * 2, qy1, qW, qH, TRUE);
    MoveWindow(q4, qx + (qW + qGap) * 3, qy1, qW, qH, TRUE);
    MoveWindow(q5, qx + (qW + qGap) * 4, qy1, qW, qH, TRUE);
    MoveWindow(q6, qx, qy2, qW, qH, TRUE);
    MoveWindow(q7, qx + (qW + qGap), qy2, qW, qH, TRUE);
    MoveWindow(q8, qx + (qW + qGap) * 2, qy2, qW, qH, TRUE);
    MoveWindow(q9, qx + (qW + qGap) * 3, qy2, qW, qH, TRUE);
    HWND typeC = GetDlgItem(hwnd, IDC_BTYPE);
    HWND priC = GetDlgItem(hwnd, IDC_PRI);
    HWND msgE = GetDlgItem(hwnd, IDC_MSG);
    HWND sendB = GetDlgItem(hwnd, IDC_SEND);
    HWND audioE = GetDlgItem(hwnd, IDC_AUDIO);
    HWND playB = GetDlgItem(hwnd, IDC_PLAY);
    HWND volS = GetDlgItem(hwnd, IDC_VOL);
    int formY = 70, msgY = 110, audioY = 158, volY = 206;
    MoveWindow(typeC, 80, formY, 160, 200, TRUE);
    MoveWindow(priC, 330, formY, 120, 200, TRUE);
    MoveWindow(msgE, 80, msgY, cw - 200, 36, TRUE);
    MoveWindow(sendB, cw - 108, msgY, 96, 36, TRUE);
    MoveWindow(audioE, 80, audioY, cw - 200, 36, TRUE);
    MoveWindow(playB, cw - 108, audioY, 96, 36, TRUE);
    MoveWindow(volS, 80, volY, cw - 200, 28, TRUE);
"@

$newLayout = @"
    // 广播区
    HWND grpBc = GetDlgItem(hwnd, IDC_GRP_BC);
    MoveWindow(grpBc, m, y, cw, 300, TRUE);
    HWND q1 = GetDlgItem(hwnd, IDC_BTN_QUICK1);
    HWND q2 = GetDlgItem(hwnd, IDC_BTN_QUICK2);
    HWND q3 = GetDlgItem(hwnd, IDC_BTN_QUICK3);
    HWND q4 = GetDlgItem(hwnd, IDC_BTN_QUICK4);
    HWND q5 = GetDlgItem(hwnd, IDC_BTN_QUICK5);
    HWND q6 = GetDlgItem(hwnd, IDC_BTN_QUICK6);
    HWND q7 = GetDlgItem(hwnd, IDC_BTN_QUICK7);
    HWND q8 = GetDlgItem(hwnd, IDC_BTN_QUICK8);
    HWND q9 = GetDlgItem(hwnd, IDC_BTN_QUICK9);
    int qGap = 6, qH = 38, qRowW = cw - 24;
    int qW = (qRowW - qGap * 4) / 5;
    int qx = 12, qy1 = 20, qy2 = 65;
    MoveWindow(q1, qx, qy1, qW, qH, TRUE);
    MoveWindow(q2, qx + (qW + qGap), qy1, qW, qH, TRUE);
    MoveWindow(q3, qx + (qW + qGap) * 2, qy1, qW, qH, TRUE);
    MoveWindow(q4, qx + (qW + qGap) * 3, qy1, qW, qH, TRUE);
    MoveWindow(q5, qx + (qW + qGap) * 4, qy1, qW, qH, TRUE);
    MoveWindow(q6, qx, qy2, qW, qH, TRUE);
    MoveWindow(q7, qx + (qW + qGap), qy2, qW, qH, TRUE);
    MoveWindow(q8, qx + (qW + qGap) * 2, qy2, qW, qH, TRUE);
    MoveWindow(q9, qx + (qW + qGap) * 3, qy2, qW, qH, TRUE);
    HWND lblType = GetDlgItem(hwnd, IDC_LBL_BTYPE);
    HWND lblPri = GetDlgItem(hwnd, IDC_LBL_PRI);
    HWND typeC = GetDlgItem(hwnd, IDC_BTYPE);
    HWND priC = GetDlgItem(hwnd, IDC_PRI);
    HWND lblMsg = GetDlgItem(hwnd, IDC_LBL_MSG);
    HWND msgE = GetDlgItem(hwnd, IDC_MSG);
    HWND sendB = GetDlgItem(hwnd, IDC_SEND);
    HWND lblAudio = GetDlgItem(hwnd, IDC_LBL_AUDIO);
    HWND audioE = GetDlgItem(hwnd, IDC_AUDIO);
    HWND playB = GetDlgItem(hwnd, IDC_PLAY);
    HWND stopB = GetDlgItem(hwnd, IDC_STOP);
    HWND pauseB = GetDlgItem(hwnd, IDC_PAUSE);
    HWND resumeB = GetDlgItem(hwnd, IDC_RESUME);
    HWND lblVol = GetDlgItem(hwnd, IDC_LBL_VOL);
    HWND volS = GetDlgItem(hwnd, IDC_VOL);
    int formY = 118, msgY = 158, audioY = 206, volY = 256;
    MoveWindow(lblType, 16, formY + 4, 56, 22, TRUE);
    MoveWindow(typeC, 80, formY, 160, 200, TRUE);
    MoveWindow(lblPri, 260, formY + 4, 60, 22, TRUE);
    MoveWindow(priC, 330, formY, 120, 200, TRUE);
    MoveWindow(lblMsg, 16, msgY + 8, 56, 22, TRUE);
    MoveWindow(msgE, 80, msgY, cw - 200, 36, TRUE);
    MoveWindow(sendB, cw - 108, msgY, 96, 36, TRUE);
    MoveWindow(lblAudio, 16, audioY + 8, 56, 22, TRUE);
    MoveWindow(audioE, 80, audioY, cw - 400, 36, TRUE);
    MoveWindow(playB, cw - 308, audioY, 70, 36, TRUE);
    MoveWindow(stopB, cw - 232, audioY, 70, 36, TRUE);
    MoveWindow(pauseB, cw - 156, audioY, 70, 36, TRUE);
    MoveWindow(resumeB, cw - 80, audioY, 70, 36, TRUE);
    MoveWindow(lblVol, 16, volY + 4, 56, 22, TRUE);
    MoveWindow(volS, 80, volY, cw - 108, 28, TRUE);
"@
ReplaceOnce $oldLayout $newLayout "K-LayoutMain-broadcast"

# ---- A. Show* functions after LayoutMain, before MainProc ----
$oldBeforeMain = "static LRESULT CALLBACK MainProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {"
$showFns = @"
static void ShowLoginWindow() {
    g_loggedIn = false;
    if (g_hMain && IsWindow(g_hMain)) ShowWindow(g_hMain, SW_HIDE);
    if (g_hLogin && IsWindow(g_hLogin)) {
        ShowWindow(g_hLogin, SW_SHOW);
        SetForegroundWindow(g_hLogin);
    }
}

static void ShowMainWindow() {
    g_loggedIn = true;
    if (g_hLogin && IsWindow(g_hLogin)) ShowWindow(g_hLogin, SW_HIDE);
    if (g_hMain && IsWindow(g_hMain)) {
        ShowWindow(g_hMain, SW_SHOWMAXIMIZED);
        SetForegroundWindow(g_hMain);
        LayoutMain(g_hMain);
        refreshTrains(g_hMain);
        refreshStatus(g_hMain);
    }
}

static LRESULT CALLBACK MainProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
"@
ReplaceOnce $oldBeforeMain $showFns "A-add-ShowLogin-ShowMain"

# ---- B. main WM_CREATE set g_hMain ----
$oldMainCreate = @"
    case WM_CREATE: {
        g_font = CreateFontW(-16, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET,
"@
$newMainCreate = @"
    case WM_CREATE: {
        g_hMain = hwnd;
        g_font = CreateFontW(-16, 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET,
"@
ReplaceOnce $oldMainCreate $newMainCreate "B-main-WM_CREATE-g_hMain"

# ---- K. create broadcast labels/controls y positions ----
$oldCreateBc = @"
        CreateWindowW(L"BUTTON", L"到站广播", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 12, 65, 140, 38, hwnd, (HMENU)IDC_BTN_QUICK6, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"发车广播", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 158, 65, 140, 38, hwnd, (HMENU)IDC_BTN_QUICK7, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"晚点通知", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 304, 65, 140, 38, hwnd, (HMENU)IDC_BTN_QUICK8, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"安全提示", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 450, 65, 140, 38, hwnd, (HMENU)IDC_BTN_QUICK9, nullptr, nullptr);
        CreateWindowW(L"STATIC", L"类型", WS_CHILD | WS_VISIBLE, 16, 74, 56, 22, hwnd, nullptr, nullptr, nullptr);
        HWND typeC = CreateWindowW(L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST | WS_VSCROLL, 80, 70, 160, 200, hwnd, (HMENU)IDC_BTYPE, nullptr, nullptr);
        SendMessageW(typeC, CB_ADDSTRING, 0, (LPARAM)L"到达");
        SendMessageW(typeC, CB_ADDSTRING, 0, (LPARAM)L"出发");
        SendMessageW(typeC, CB_ADDSTRING, 0, (LPARAM)L"晚点");
        SendMessageW(typeC, CB_ADDSTRING, 0, (LPARAM)L"取消");
        SendMessageW(typeC, CB_ADDSTRING, 0, (LPARAM)L"通告");
        SendMessageW(typeC, CB_SETCURSEL, 0, 0);
        CreateWindowW(L"STATIC", L"优先级", WS_CHILD | WS_VISIBLE, 260, 74, 60, 22, hwnd, nullptr, nullptr, nullptr);
        HWND priC = CreateWindowW(L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST, 330, 70, 120, 200, hwnd, (HMENU)IDC_PRI, nullptr, nullptr);
        SendMessageW(priC, CB_ADDSTRING, 0, (LPARAM)L"普通");
        SendMessageW(priC, CB_ADDSTRING, 0, (LPARAM)L"紧急");
        SendMessageW(priC, CB_SETCURSEL, 0, 0);
        CreateWindowW(L"STATIC", L"内容", WS_CHILD | WS_VISIBLE, 16, 118, 56, 22, hwnd, nullptr, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL, 80, 110, 680, 36, hwnd, (HMENU)IDC_MSG, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"发送广播", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 776, 110, 96, 36, hwnd, (HMENU)IDC_SEND, nullptr, nullptr);
        CreateWindowW(L"STATIC", L"音频", WS_CHILD | WS_VISIBLE, 16, 166, 56, 22, hwnd, nullptr, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL | ES_READONLY, 80, 158, 680, 36, hwnd, (HMENU)IDC_AUDIO, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"播放音频", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 776, 158, 96, 36, hwnd, (HMENU)IDC_PLAY, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"停止", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 16, 206, 80, 32, hwnd, (HMENU)IDC_STOP, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"暂停", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 104, 206, 80, 32, hwnd, (HMENU)IDC_PAUSE, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"恢复", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 192, 206, 80, 32, hwnd, (HMENU)IDC_RESUME, nullptr, nullptr);
        CreateWindowW(L"STATIC", L"音量", WS_CHILD | WS_VISIBLE, 16, 210, 56, 22, hwnd, nullptr, nullptr, nullptr);
        HWND vol = CreateWindowW(TRACKBAR_CLASSW, L"", WS_CHILD | WS_VISIBLE | TBS_AUTOTICKS, 80, 206, 680, 28, hwnd, (HMENU)IDC_VOL, nullptr, nullptr);
"@

$newCreateBc = @"
        CreateWindowW(L"BUTTON", L"到站广播", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 12, 65, 140, 38, hwnd, (HMENU)IDC_BTN_QUICK6, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"发车广播", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 158, 65, 140, 38, hwnd, (HMENU)IDC_BTN_QUICK7, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"晚点通知", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 304, 65, 140, 38, hwnd, (HMENU)IDC_BTN_QUICK8, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"安全提示", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 450, 65, 140, 38, hwnd, (HMENU)IDC_BTN_QUICK9, nullptr, nullptr);
        CreateWindowW(L"STATIC", L"类型", WS_CHILD | WS_VISIBLE, 16, 122, 56, 22, hwnd, (HMENU)IDC_LBL_BTYPE, nullptr, nullptr);
        HWND typeC = CreateWindowW(L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST | WS_VSCROLL, 80, 118, 160, 200, hwnd, (HMENU)IDC_BTYPE, nullptr, nullptr);
        SendMessageW(typeC, CB_ADDSTRING, 0, (LPARAM)L"到达");
        SendMessageW(typeC, CB_ADDSTRING, 0, (LPARAM)L"出发");
        SendMessageW(typeC, CB_ADDSTRING, 0, (LPARAM)L"晚点");
        SendMessageW(typeC, CB_ADDSTRING, 0, (LPARAM)L"取消");
        SendMessageW(typeC, CB_ADDSTRING, 0, (LPARAM)L"通告");
        SendMessageW(typeC, CB_SETCURSEL, 0, 0);
        CreateWindowW(L"STATIC", L"优先级", WS_CHILD | WS_VISIBLE, 260, 122, 60, 22, hwnd, (HMENU)IDC_LBL_PRI, nullptr, nullptr);
        HWND priC = CreateWindowW(L"COMBOBOX", L"", WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST, 330, 118, 120, 200, hwnd, (HMENU)IDC_PRI, nullptr, nullptr);
        SendMessageW(priC, CB_ADDSTRING, 0, (LPARAM)L"普通");
        SendMessageW(priC, CB_ADDSTRING, 0, (LPARAM)L"紧急");
        SendMessageW(priC, CB_SETCURSEL, 0, 0);
        CreateWindowW(L"STATIC", L"内容", WS_CHILD | WS_VISIBLE, 16, 166, 56, 22, hwnd, (HMENU)IDC_LBL_MSG, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL, 80, 158, 680, 36, hwnd, (HMENU)IDC_MSG, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"发送广播", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 776, 158, 96, 36, hwnd, (HMENU)IDC_SEND, nullptr, nullptr);
        CreateWindowW(L"STATIC", L"音频", WS_CHILD | WS_VISIBLE, 16, 214, 56, 22, hwnd, (HMENU)IDC_LBL_AUDIO, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL | ES_READONLY, 80, 206, 480, 36, hwnd, (HMENU)IDC_AUDIO, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"播放音频", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 572, 206, 70, 36, hwnd, (HMENU)IDC_PLAY, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"停止", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 648, 206, 70, 36, hwnd, (HMENU)IDC_STOP, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"暂停", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 724, 206, 70, 36, hwnd, (HMENU)IDC_PAUSE, nullptr, nullptr);
        CreateWindowW(L"BUTTON", L"恢复", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 800, 206, 70, 36, hwnd, (HMENU)IDC_RESUME, nullptr, nullptr);
        CreateWindowW(L"STATIC", L"音量", WS_CHILD | WS_VISIBLE, 16, 260, 56, 22, hwnd, (HMENU)IDC_LBL_VOL, nullptr, nullptr);
        HWND vol = CreateWindowW(TRACKBAR_CLASSW, L"", WS_CHILD | WS_VISIBLE | TBS_AUTOTICKS, 80, 256, 790, 28, hwnd, (HMENU)IDC_VOL, nullptr, nullptr);
"@
ReplaceOnce $oldCreateBc $newCreateBc "K-create-broadcast-controls"

# ---- D/E logout/exit ----
$oldLogout = @"
        case IDC_BTN_LOGOUT: {
            if (customMessageBoxW(hwnd, L"确定退出登录并返回登录窗口？", L"确认", MB_YESNO) != IDOK) break;
            g_isLogout = true;
            g_loggedIn = false;
            DestroyWindow(hwnd);
            break;
        }
        case IDC_BTN_EXIT: {
            if (customMessageBoxW(hwnd, L"确定关闭整个系统并停止后端？", L"确认", MB_YESNO) != IDOK) break;
            g_isLogout = false;
            callServer("`"Shutdown`"");
            tcpClose();
            g_connected = false;
            DestroyWindow(hwnd);
            break;
        }
"@
$newLogout = @"
        case IDC_BTN_LOGOUT: {
            if (customMessageBoxW(hwnd, L"确定退出登录并返回登录窗口？", L"确认", MB_YESNO) != IDOK) break;
            g_isLogout = true;
            ShowLoginWindow();
            break;
        }
        case IDC_BTN_EXIT: {
            if (customMessageBoxW(hwnd, L"确定关闭整个系统并停止后端？", L"确认", MB_YESNO) != IDOK) break;
            g_isLogout = false;
            callServer("`"Shutdown`"");
            tcpClose();
            g_connected = false;
            PostQuitMessage(0);
            break;
        }
"@
ReplaceOnce $oldLogout $newLogout "DE-logout-exit"

# ---- F. main WM_DESTROY ----
$oldDestroy = @"
    case WM_DESTROY:
        KillTimer(hwnd, 1);
        if (g_hMainBg) { DeleteObject(g_hMainBg); g_hMainBg = nullptr; }
        if (g_hMainEditBg) { DeleteObject(g_hMainEditBg); g_hMainEditBg = nullptr; }
        if (g_hMainTopBg) { DeleteObject(g_hMainTopBg); g_hMainTopBg = nullptr; }
        if (g_font) { DeleteObject(g_font); g_font = nullptr; }
        // 只有非退出登录时才发送退出消息
        if (!g_isLogout) {
            PostQuitMessage(0);
        }
        return 0;
"@
$newDestroy = @"
    case WM_DESTROY:
        KillTimer(hwnd, 1);
        if (g_hMainBg) { DeleteObject(g_hMainBg); g_hMainBg = nullptr; }
        if (g_hMainEditBg) { DeleteObject(g_hMainEditBg); g_hMainEditBg = nullptr; }
        if (g_hMainTopBg) { DeleteObject(g_hMainTopBg); g_hMainTopBg = nullptr; }
        if (g_font) { DeleteObject(g_font); g_font = nullptr; }
        g_hMain = nullptr;
        if (!g_isLogout) PostQuitMessage(0);
        return 0;
"@
ReplaceOnce $oldDestroy $newDestroy "F-main-WM_DESTROY"

# ---- C. login WM_CREATE set g_hLogin ----
$oldLoginCreate = @"
    case WM_CREATE: {
        RECT rc; GetClientRect(hwnd, &rc);
"@
$newLoginCreate = @"
    case WM_CREATE: {
        g_hLogin = hwnd;
        RECT rc; GetClientRect(hwnd, &rc);
"@
ReplaceOnce $oldLoginCreate $newLoginCreate "C-login-WM_CREATE-g_hLogin"

# ---- G. login success ----
$oldSuccess = @"
                DestroyWindow(hwnd);
                PostQuitMessage(0);
"@
$newSuccess = @"
                ShowMainWindow();
"@
if ($text.Contains($oldSuccess)) {
    ReplaceOnce $oldSuccess $newSuccess "G-login-success-ShowMainWindow"
} elseif ($text.Contains("ShowMainWindow();")) {
    Log "SKIP G-login-success already ShowMainWindow"
    $changes += "G-login-success-already-done"
} else {
    Log "WARN G-login-success pattern not found, searching nearby"
}

# ---- I. login WM_DESTROY set g_hLogin=null ----
$oldLoginDestroy = @"
    case WM_DESTROY:
        if (g_hLoginBg) { DeleteObject(g_hLoginBg); g_hLoginBg = nullptr; }
        if (g_hEditBg) { DeleteObject(g_hEditBg); g_hEditBg = nullptr; }
        return 0;
"@
$newLoginDestroy = @"
    case WM_DESTROY:
        if (g_hLoginBg) { DeleteObject(g_hLoginBg); g_hLoginBg = nullptr; }
        if (g_hEditBg) { DeleteObject(g_hEditBg); g_hEditBg = nullptr; }
        g_hLogin = nullptr;
        return 0;
"@
ReplaceOnce $oldLoginDestroy $newLoginDestroy "I-login-WM_DESTROY-g_hLogin"

# ---- J. WinMain single loop ----
$oldWinMain = @"
    int ret = 0;
    MSG msg;

    // 外层循环：登录 -> 主窗口 -> 退出登录回登录 / 关闭系统退出
    while (true) {
        g_loggedIn = false;
        HWND login = CreateWindowExW(0, L"LoginWin", L"",
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
            0, 0, 800, 500, nullptr, nullptr, hInst, nullptr);
        {
            int sw = GetSystemMetrics(SM_CXSCREEN);
            int sh = GetSystemMetrics(SM_CYSCREEN);
            SetWindowPos(login, nullptr, (sw - 800) / 2, (sh - 500) / 2, 0, 0, SWP_NOSIZE | SWP_NOZORDER);
        }
        ShowWindow(login, nCmd);
        UpdateWindow(login);

        // 登录窗口消息循环
        while (GetMessageW(&msg, nullptr, 0, 0)) {
            if (!IsWindow(login)) { ret = msg.wParam; break; }
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        if (!g_loggedIn) break; // 登录窗口被销毁但未登录 -> 退出程序

        // 主窗口
        HWND main = CreateWindowExW(0, L"MainWin", L"火车站广播调度系统 - 主控制台",
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX,
            0, 0, 1030, 660, nullptr, nullptr, hInst, nullptr);
        {
            int sw = GetSystemMetrics(SM_CXSCREEN);
            int sh = GetSystemMetrics(SM_CYSCREEN);
            SetWindowPos(main, nullptr, (sw - 1030) / 2, (sh - 660) / 2, 0, 0, SWP_NOSIZE | SWP_NOZORDER);
        }
        ShowWindow(main, SW_MAXIMIZE); // 启动时最大化
        UpdateWindow(main);

        // 主窗口消息循环
        g_isLogout = false; // 重置标志
        bool mainRunning = true;
        while (mainRunning) {
            // 使用 PeekMessage 非阻塞检查消息
            while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
                if (msg.message == WM_QUIT) {
                    ret = (int)msg.wParam;
                    goto cleanup;
                }
                TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
            // 检查主窗口是否还存在
            if (!IsWindow(main)) {
                mainRunning = false;
                break;
            }
            // 避免忙等待，让出 CPU
            Sleep(5);
        }
        // 主窗口退出：若连接断开则是关闭系统 -> 结束；否则退出登录 -> 回登录
        if (!g_connected) break;
    }

cleanup:
    tcpClose();
    WSACleanup();
    GdiplusShutdown(g_gdiToken);
    return ret;
}
"@

$newWinMain = @"
    int ret = 0;
    MSG msg;

    g_loggedIn = false;
    g_isLogout = false;

    HWND login = CreateWindowExW(0, L"LoginWin", L"",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        0, 0, 800, 500, nullptr, nullptr, hInst, nullptr);
    g_hLogin = login;
    {
        int sw = GetSystemMetrics(SM_CXSCREEN);
        int sh = GetSystemMetrics(SM_CYSCREEN);
        SetWindowPos(login, nullptr, (sw - 800) / 2, (sh - 500) / 2, 0, 0, SWP_NOSIZE | SWP_NOZORDER);
    }

    HWND main = CreateWindowExW(0, L"MainWin", L"火车站广播调度系统 - 主控制台",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX,
        0, 0, 1030, 660, nullptr, nullptr, hInst, nullptr);
    g_hMain = main;
    {
        int sw = GetSystemMetrics(SM_CXSCREEN);
        int sh = GetSystemMetrics(SM_CYSCREEN);
        SetWindowPos(main, nullptr, (sw - 1030) / 2, (sh - 660) / 2, 0, 0, SWP_NOSIZE | SWP_NOZORDER);
    }
    ShowWindow(main, SW_HIDE);

    ShowWindow(login, nCmd);
    UpdateWindow(login);

    while (GetMessageW(&msg, nullptr, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    ret = (int)msg.wParam;

    if (g_hMain && IsWindow(g_hMain)) DestroyWindow(g_hMain);
    if (g_hLogin && IsWindow(g_hLogin)) DestroyWindow(g_hLogin);

cleanup:
    tcpClose();
    WSACleanup();
    GdiplusShutdown(g_gdiToken);
    return ret;
}
"@

if ($text.Contains($oldWinMain)) {
    ReplaceOnce $oldWinMain $newWinMain "J-WinMain-single-loop"
} elseif ($text.Contains("ShowWindow(main, SW_HIDE);") -and $text.Contains("while (GetMessageW(&msg, nullptr, 0, 0))")) {
    Log "SKIP J-WinMain already single loop-ish"
    $changes += "J-WinMain-already-done-check"
} else {
    Log "FAIL J-WinMain old block not found"
    throw "FAIL J-WinMain"
}

# write back
[System.IO.File]::WriteAllText($src, $text)
$newLines = ($text -split "`n").Count
Log ("wrote bytes=" + $text.Length)
Log ("new lines=" + $newLines)
Log ("changes=" + ($changes -join ', '))

# verify
$v = @()
function V($name, $cond) {
    if ($cond) { $script:v += "PASS $name" } else { $script:v += "FAIL $name" }
}
V "has ShowLoginWindow" ($text.Contains("static void ShowLoginWindow()"))
V "has ShowMainWindow" ($text.Contains("static void ShowMainWindow()"))
V "g_hLogin exists" ($text.Contains("static HWND g_hLogin = nullptr;"))
V "no g_hLoginWin" (-not $text.Contains("g_hLoginWin"))
V "login success no Destroy+Quit pair" (-not ($text.Contains("DestroyWindow(hwnd);`r`n                PostQuitMessage(0);") -or $text.Contains("DestroyWindow(hwnd);`n                PostQuitMessage(0);")))
V "login success ShowMainWindow" ($text.Contains("ShowMainWindow();"))
V "logout uses ShowLoginWindow" ($text.Contains("ShowLoginWindow();"))
V "exit uses PostQuitMessage" ($text -match "case IDC_BTN_EXIT:[\s\S]*PostQuitMessage\(0\);")
V "single GetMessage loop marker" ($text.Contains("ShowWindow(main, SW_HIDE);"))
V "no outer while(true) login recreate" (-not $text.Contains("外层循环：登录"))
V "IDC_LBL_BTYPE" ($text.Contains("#define IDC_LBL_BTYPE"))
V "formY = 118" ($text.Contains("int formY = 118, msgY = 158, audioY = 206, volY = 256;"))
V "create type y=118" ($text.Contains("80, 118, 160, 200"))

Log "---- VERIFY ----"
$v | ForEach-Object { Log $_ }
Log "PATCH END"
Write-Output "PATCH_DONE"
Write-Output ("LINES=" + $newLines)
$v | ForEach-Object { Write-Output $_ }
