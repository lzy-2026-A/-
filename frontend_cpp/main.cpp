// 火车站广播调度系统 - C++ Win32 前端
// 编译: cl /EHsc /O2 frontend_cpp/main.cpp /Fe:广播系统前端.exe /link ws2_32.lib comctl32.lib user32.lib gdi32.lib
#define UNICODE
#define _UNICODE
#define _WIN32_IE 0x0600
// 应用图标资源 ID（app.rc 中 IDI_ICON1 ICON ...）
#define IDI_ICON1 101
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <commctrl.h>
#include <gdiplus.h>
#include <shobjidl.h>
#include <string>
#include <vector>
#include <algorithm>
#pragma comment(lib, "gdiplus.lib")
using namespace Gdiplus;

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")

// 前向声明
static int customMessageBoxW(HWND parent, const wchar_t* text, const wchar_t* caption, UINT type);

// ============================================================
// 自定义深色 MessageBox
// ============================================================
#define IDC_MB_OK 3001
#define IDC_MB_YES 3002
#define IDC_MB_NO 3003

static HBRUSH g_hMbBg = nullptr;
static HFONT g_fMbText = nullptr;
static HFONT g_fMbBtn = nullptr;
static int g_mbResult = 0;

static LRESULT CALLBACK MbProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        g_hMbBg = CreateSolidBrush(RGB(26, 37, 64));
        g_fMbText = CreateFontW(14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");
        g_fMbBtn = CreateFontW(13, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");

        CREATESTRUCT* cs = (CREATESTRUCT*)lp;
        const wchar_t* text = (const wchar_t*)cs->lpCreateParams;

        // 文字
        HWND st = CreateWindowExW(0, L"STATIC", text,
            WS_CHILD|WS_VISIBLE|SS_CENTER, 30, 30, 340, 60, hwnd, nullptr, nullptr, nullptr);
        SendMessageW(st, WM_SETFONT, (WPARAM)g_fMbText, TRUE);

        // 按钮：放两个自绘按钮（确定/取消）
        HWND btnYes = CreateWindowExW(0, L"BUTTON", L"确  定",
            WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 60, 110, 120, 36, hwnd, (HMENU)IDC_MB_OK, nullptr, nullptr);
        SendMessageW(btnYes, WM_SETFONT, (WPARAM)g_fMbBtn, TRUE);
        HWND btnNo = CreateWindowExW(0, L"BUTTON", L"取  消",
            WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 220, 110, 120, 36, hwnd, (HMENU)IDC_MB_NO, nullptr, nullptr);
        SendMessageW(btnNo, WM_SETFONT, (WPARAM)g_fMbBtn, TRUE);

        g_mbResult = IDCANCEL;
        return 0;
    }
    case WM_ERASEBKGND: {
        RECT rc; GetClientRect(hwnd, &rc);
        FillRect((HDC)wp, &rc, g_hMbBg);
        return 1;
    }
    case WM_CTLCOLORSTATIC: {
        HDC hdc = (HDC)wp;
        SetTextColor(hdc, RGB(220, 228, 240));
        SetBkMode(hdc, TRANSPARENT);
        return (LRESULT)g_hMbBg;
    }
    case WM_DRAWITEM: {
        LPDRAWITEMSTRUCT dis = (LPDRAWITEMSTRUCT)lp;
        RECT rc = dis->rcItem;
        COLORREF bg = (dis->CtlID == IDC_MB_OK) ? RGB(42, 93, 176) : RGB(58, 74, 102);
        COLORREF hover = (dis->CtlID == IDC_MB_OK) ? RGB(60, 120, 210) : RGB(78, 98, 130);
        bool pressed = (dis->itemState & ODS_SELECTED) != 0;

        // 先用窗口背景色盖住整个按钮区域（圆角外四角不露默认浅色）
        HBRUSH bgBr = CreateSolidBrush(RGB(26, 37, 64));
        FillRect(dis->hDC, &rc, bgBr);
        DeleteObject(bgBr);

        // 再裁剪圆角画按钮色
        HRGN rgn = CreateRoundRectRgn(rc.left, rc.top, rc.right + 1, rc.bottom + 1, 8, 8);
        SelectClipRgn(dis->hDC, rgn);

        HBRUSH br = CreateSolidBrush(pressed ? hover : bg);
        FillRect(dis->hDC, &rc, br);
        DeleteObject(br);

        SetBkMode(dis->hDC, TRANSPARENT);
        SetTextColor(dis->hDC, RGB(255, 255, 255));
        if (g_fMbBtn) SelectObject(dis->hDC, g_fMbBtn);
        const wchar_t* btnText = (dis->CtlID == IDC_MB_OK) ? L"确  定" : L"取  消";
        DrawTextW(dis->hDC, const_cast<LPWSTR>(btnText), -1, &rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE);

        SelectClipRgn(dis->hDC, nullptr);
        DeleteObject(rgn);
        return TRUE;
    }
    case WM_COMMAND: {
        int id = LOWORD(wp);
        if (id == IDC_MB_OK) { g_mbResult = IDOK; DestroyWindow(hwnd); }
        else if (id == IDC_MB_NO) { g_mbResult = IDCANCEL; DestroyWindow(hwnd); }
        return 0;
    }
    case WM_CLOSE: { g_mbResult = IDCANCEL; DestroyWindow(hwnd); return 0; }
    case WM_DESTROY:
        if (g_hMbBg) DeleteObject(g_hMbBg);
        if (g_fMbText) DeleteObject(g_fMbText);
        if (g_fMbBtn) DeleteObject(g_fMbBtn);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

static int customMessageBoxW(HWND parent, const wchar_t* text, const wchar_t* caption, UINT type) {
    WNDCLASSW wc = {0};
    wc.lpfnWndProc = MbProc;
    wc.hInstance = GetModuleHandleW(nullptr);
    wc.lpszClassName = L"CustomMsgBox";
    wc.hbrBackground = nullptr;
    RegisterClassW(&wc);

    int sw = GetSystemMetrics(SM_CXSCREEN);
    int sh = GetSystemMetrics(SM_CYSCREEN);
    int w = 400, h = 200;
    HWND mb = CreateWindowExW(WS_EX_DLGMODALFRAME, L"CustomMsgBox", caption,
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_VISIBLE,
        (sw - w) / 2, (sh - h) / 2, w, h, parent, nullptr, GetModuleHandleW(nullptr), (LPVOID)text);
    ShowWindow(mb, SW_SHOW);
    UpdateWindow(mb);

    // 模态：禁用父窗口
    if (parent) EnableWindow(parent, FALSE);

    MSG msg;
    // 用 PeekMessage 轮询：窗口销毁后 IsWindow 立即为假，循环可靠退出
    while (IsWindow(mb)) {
        while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        Sleep(10);
    }

    if (parent) {
        EnableWindow(parent, TRUE);
        SetForegroundWindow(parent);
    }
    return g_mbResult;
}

// ============================================================
// 编码转换工具
// ============================================================
static std::wstring utf8ToWide(const std::string& s) {
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0);
    std::wstring out(n, 0);
    MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), &out[0], n);
    return out;
}
static std::string wideToUtf8(const std::wstring& s) {
    if (s.empty()) return "";
    int n = WideCharToMultiByte(CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0, nullptr, nullptr);
    std::string out(n, 0);
    WideCharToMultiByte(CP_UTF8, 0, s.c_str(), (int)s.size(), &out[0], n, nullptr, nullptr);
    return out;
}
static std::wstring gbkToWide(const std::string& s) {
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(936, 0, s.c_str(), (int)s.size(), nullptr, 0); // 936 = GBK
    std::wstring out(n, 0);
    MultiByteToWideChar(936, 0, s.c_str(), (int)s.size(), &out[0], n);
    return out;
}
static std::wstring trimW(const std::wstring& s) {
    size_t a = s.find_first_not_of(L" \t\r\n");
    size_t b = s.find_last_not_of(L" \t\r\n");
    return a == std::wstring::npos ? L"" : s.substr(a, b - a + 1);
}

// ============================================================
// 简单 JSON 字段提取（针对本系统固定响应结构）
// ============================================================
// 在 json 中找 "key":"value"，返回 value（已去引号、已转义还原简单）
static bool jsonGetString(const std::string& json, const std::string& key, std::string& out) {
    std::string pat = "\"" + key + "\"";
    size_t p = json.find(pat);
    if (p == std::string::npos) return false;
    p = json.find(':', p + pat.size());
    if (p == std::string::npos) return false;
    p = json.find('"', p);
    if (p == std::string::npos) return false;
    size_t e = p + 1;
    while (e < json.size()) {
        if (json[e] == '\\' && e + 1 < json.size()) { e += 2; continue; }
        if (json[e] == '"') break;
        e++;
    }
    out = json.substr(p + 1, e - p - 1);
    return true;
}
static bool jsonGetBool(const std::string& json, const std::string& key, bool& out) {
    std::string pat = "\"" + key + "\"";
    size_t p = json.find(pat);
    if (p == std::string::npos) return false;
    p = json.find(':', p + pat.size());
    if (p == std::string::npos) return false;
    p++;
    while (p < json.size() && (json[p] == ' ' || json[p] == '\t')) p++;
    if (p + 3 < json.size() && json[p] == 't') { out = true; return true; }
    out = false; return true;
}
static bool jsonGetInt(const std::string& json, const std::string& key, int& out) {
    std::string pat = "\"" + key + "\"";
    size_t p = json.find(pat);
    if (p == std::string::npos) return false;
    p = json.find(':', p + pat.size());
    if (p == std::string::npos) return false;
    p++;
    while (p < json.size() && (json[p] == ' ' || json[p] == '\t' || json[p] == '-')) p++;
    int v = 0; bool neg = false;
    if (p > 0 && json[p-1] == '-') neg = true;
    while (p < json.size() && json[p] >= '0' && json[p] <= '9') { v = v * 10 + (json[p] - '0'); p++; }
    out = neg ? -v : v;
    return true;
}

// 解析车次列表 ActiveTrains
struct Train {
    std::wstring num, dep, arr, deptime, platform, status;
};
static std::vector<Train> parseTrains(const std::string& json) {
    std::vector<Train> trains;
    size_t p = json.find("\"trains\"");
    if (p == std::string::npos) return trains;
    p = json.find('[', p);
    if (p == std::string::npos) return trains;
    size_t e = json.find(']', p);
    std::string arr = json.substr(p, e - p);
    // 按 { 切分每个对象
    size_t pos = 0;
    while ((pos = arr.find('{', pos)) != std::string::npos) {
        size_t end = arr.find('}', pos);
        if (end == std::string::npos) break;
        std::string obj = arr.substr(pos, end - pos);
        Train t;
        std::string v;
        if (jsonGetString(obj, "train_number", v)) t.num = utf8ToWide(v);
        if (jsonGetString(obj, "departure_station", v)) t.dep = utf8ToWide(v);
        if (jsonGetString(obj, "arrival_station", v)) t.arr = utf8ToWide(v);
        if (jsonGetString(obj, "departure_time", v)) t.deptime = utf8ToWide(v);
        if (jsonGetString(obj, "platform", v)) t.platform = utf8ToWide(v);
        if (jsonGetString(obj, "status", v)) t.status = utf8ToWide(v);
        trains.push_back(t);
        pos = end + 1;
    }
    return trains;
}

// ============================================================
// TCP 客户端
// ============================================================
static SOCKET g_sock = INVALID_SOCKET;
static bool g_connected = false;

static bool tcpConnect() {
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
    sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = htons(8888);
    inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);
    // 重试最多 8 次（每次 500ms），等后端起来
    for (int i = 0; i < 8; i++) {
        g_sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (connect(g_sock, (sockaddr*)&addr, sizeof(addr)) != SOCKET_ERROR) {
            DWORD rt = 6000;
            setsockopt(g_sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&rt, sizeof(rt));
            g_connected = true;
            return true;
        }
        closesocket(g_sock);
        g_sock = INVALID_SOCKET;
        Sleep(500);
    }
    g_connected = false;
    return false;
}

// 获取项目根目录：兼容两种布局
// 1) 开发/旧布局：frontend.exe 在 frontend_cpp\ 子目录下 → 根目录是上级（dir\..）
// 2) 发布包布局：frontend.exe 在发布包根目录 → 根目录就是 exe 所在目录（dir）
static std::wstring GetAppRoot() {
    wchar_t exePath[MAX_PATH] = {0};
    GetModuleFileNameW(nullptr, exePath, MAX_PATH);
    std::wstring dir(exePath);
    size_t slash = dir.find_last_of(L"\\/");
    if (slash != std::wstring::npos) dir = dir.substr(0, slash);
    std::wstring up = dir + L"\\..";
    if (GetFileAttributesW((up + L"\\dist\\main_ui\\main_ui.exe").c_str()) != INVALID_FILE_ATTRIBUTES)
        return up;   // 开发布局：frontend_cpp\frontend.exe → 根=上级
    if (GetFileAttributesW((dir + L"\\dist\\main_ui\\main_ui.exe").c_str()) != INVALID_FILE_ATTRIBUTES)
        return dir;  // 发布包布局：根目录 frontend.exe → 根=自身
    return dir;      // 兜底：优先自身目录
}

// 隐藏窗口拉起后端（不弹 cmd 黑窗）
static void launchBackend() {
    wchar_t exePath[MAX_PATH] = {0};
    GetModuleFileNameW(nullptr, exePath, MAX_PATH);
    std::wstring dir(exePath);
    size_t slash = dir.find_last_of(L"\\/");
    if (slash != std::wstring::npos) dir = dir.substr(0, slash);
    std::vector<std::wstring> candidates = {
        dir + L"\\..\\backend\\target\\debug\\train_broadcast_backend.exe",
        dir + L"\\backend\\target\\debug\\train_broadcast_backend.exe",
        L"backend\\target\\debug\\train_broadcast_backend.exe",
    };
    for (auto& path : candidates) {
        DWORD attr = GetFileAttributesW(path.c_str());
        if (attr != INVALID_FILE_ATTRIBUTES) {
            // 规范化路径去掉 ..
            wchar_t full[MAX_PATH] = {0};
            GetFullPathNameW(path.c_str(), MAX_PATH, full, nullptr);
            std::wstring wd = dir + L"\\..";
            STARTUPINFOW si = { sizeof(si) };
            PROCESS_INFORMATION pi = {0};
            BOOL ok = CreateProcessW(full, nullptr, nullptr, nullptr, FALSE,
                CREATE_NO_WINDOW, nullptr, wd.c_str(), &si, &pi);
            if (ok) {
                CloseHandle(pi.hProcess);
                CloseHandle(pi.hThread);
            }
            return;
        }
    }
}
static void tcpClose() {
    g_connected = false;
    if (g_sock != INVALID_SOCKET) { closesocket(g_sock); g_sock = INVALID_SOCKET; }
    WSACleanup();
}
// 发送 UTF-8 请求，返回 GBK 响应字节串（去除末尾 \n）
static std::string tcpSend(const std::string& utf8Payload) {
    if (!g_connected) {
        if (!tcpConnect()) return "";
    }
    send(g_sock, utf8Payload.c_str(), (int)utf8Payload.size(), 0);
    std::string buf;
    char tmp[4096];
    while (true) {
        int n = recv(g_sock, tmp, sizeof(tmp), 0);
        if (n <= 0) break;
        buf.append(tmp, n);
        if (buf.find('\n') != std::string::npos) break;
    }
    if (!buf.empty() && buf.back() == '\n') buf.pop_back();
    return buf;
}

// ============================================================
// 业务请求封装（返回成功与否 + 消息）
// ============================================================
struct Resp { bool ok; std::wstring msg; std::string raw; };

static Resp callServer(const std::string& utf8Req) {
    Resp r; r.ok = false;
    r.raw = tcpSend(utf8Req);
    if (r.raw.empty()) { r.msg = L"服务器无响应"; g_connected = false; return r; }
    std::string m;
    if (jsonGetString(r.raw, "message", m)) r.msg = gbkToWide(m);
    bool b;
    if (jsonGetBool(r.raw, "success", b)) { r.ok = b; }
    else if (r.raw.find("\"Error\"") == std::string::npos && r.raw.find("\"Success\"") != std::string::npos) {
        r.ok = true;
    } else if (r.raw.find("\"Error\"") != std::string::npos) {
        r.ok = false;
    } else {
        r.ok = true; // 数据型响应（如 ActiveTrains/SystemStatus）
    }
    return r;
}

// ============================================================
// 控件 ID
// ============================================================
#define IDC_USER 1001
#define IDC_PWD 1002
#define IDC_BTN_LOGIN 1003
#define IDC_BTN_REG 1004

#define IDC_TRAIN_LIST 2001
#define IDC_NUM 2101
#define IDC_DEP 2102
#define IDC_ARR 2103
#define IDC_DEPT 2104
#define IDC_PLAT 2105
#define IDC_STATUS_CMB 2106
#define IDC_ADD 2201
#define IDC_UPD 2202
#define IDC_DEL 2203
#define IDC_REFRESH 2204

#define IDC_BTYPE_CMB 2301
#define IDC_MSG 2302
#define IDC_PRI 2303
#define IDC_SEND 2304
#define IDC_PB_BOARD 2401
#define IDC_PB_DELAY 2402
#define IDC_PB_SAFE 2403
#define IDC_PB_EMG 2404

#define IDC_AUDIO_FILE 2501
#define IDC_PLAY 2502
#define IDC_STOP 2503
#define IDC_PAUSE 2504
#define IDC_RESUME 2505
#define IDC_VOL_SLIDER 2506
#define IDC_VOL_LABEL 2507
#define IDC_SETVOL 2508

// 广播面板按钮 ID - 每个按钮有唯一 ID（使用 2600+ 避免与其他 ID 冲突）
#define IDC_PB_WAITING 2601
#define IDC_PB_CHECKIN 2602
#define IDC_PB_PLATFORM 2603
#define IDC_PB_TRACK 2604
#define IDC_PB_TRAFFIC 2605
#define IDC_PB_DELAY2 2606
#define IDC_PB_CANCEL 2607
#define IDC_PB_CHIME 2608

#define IDC_AUTO_CHK 2701
#define IDC_QUEUE_LBL 2702
#define IDC_AUDIO_LBL 2703
#define IDC_SYS_LBL 2704
#define IDC_BOTTOM_LBL 2705

#define IDC_BTN_LOGOUT   2801
#define IDC_BTN_EXIT     2802
#define IDC_LBL_BTYPE    2610
#define IDC_LBL_PRI      2611
#define IDC_LBL_MSG      2612
#define IDC_LBL_AUDIO    2613
#define IDC_LBL_VOL      2614
#define IDC_CHK_REMEMBER_USER 2901
#define IDC_CHK_REMEMBER_PWD 2902
#define IDC_LINK_REG 2903

// 全局标志：标记是否退出登录（返回登录窗口）vs 关闭系统
static bool g_isLogout = false;

// 主控制台 UI
#define IDC_TAB_BROADCAST 3001
#define IDC_TAB_TRAIN 3002
#define IDC_TAB_SCREEN 3003
#define IDC_TAB_SYSTEM 3004
#define IDC_TAB_BROADCAST_SET 3005
#define IDC_TOP_TITLE 3101
#define IDC_TOP_CITY 3102
#define IDC_TOP_WELCOME 3103
#define IDC_PANEL_BROADCAST 3201
#define IDC_PANEL_TRAIN 3202
#define IDC_PANEL_SCREEN 3203
#define IDC_PANEL_SYSTEM 3204
#define IDC_PANEL_BROADCAST_SET 3205

static HFONT g_font = nullptr;

// 状态/类型 映射
static const wchar_t* STATUS_ITEMS[] = {L"计划中", L"检票中", L"晚点", L"已发车", L"已到达", L"取消"};
static const wchar_t* STATUS_EN[]   = {L"Scheduled", L"Boarding", L"Delayed", L"Departed", L"Arrived", L"Cancelled"};
static const wchar_t* BTYPE_ITEMS[] = {L"检票广播", L"晚点广播", L"安全提醒", L"紧急通知", L"欢迎词", L"欢送词", L"站台变更"};
static const wchar_t* BTYPE_EN[]   = {L"BoardingAnnouncement", L"DelayAnnouncement", L"SafetyReminder", L"EmergencyNotice", L"WelcomeMessage", L"FarewellMessage", L"PlatformChange"};

static std::wstring statusZh2En(const std::wstring& zh) {
    for (int i = 0; i < 6; i++) if (zh == STATUS_ITEMS[i]) return STATUS_EN[i];
    return L"Scheduled";
}
static std::wstring statusEn2Zh(const std::wstring& en) {
    for (int i = 0; i < 6; i++) if (en == STATUS_EN[i]) return STATUS_ITEMS[i];
    return en;
}

// 禁用窗口关闭按钮
static void disableCloseButton(HWND hwnd) {
    HMENU hmenu = GetSystemMenu(hwnd, FALSE);
    if (hmenu) {
        EnableMenuItem(hmenu, SC_CLOSE, MF_BYCOMMAND | MF_GRAYED);
        DrawMenuBar(hwnd);
    }
}
static void setBottomText(HWND hwnd, const std::wstring& s) {
    SetDlgItemTextW(hwnd, IDC_BOTTOM_LBL, s.c_str());
}
static HWND g_hMain = nullptr;
static HWND g_hLogin = nullptr;
static bool g_loggedIn = false;

// ============================================================
// 主窗口：刷新车次列表
// ============================================================
static void refreshTrains(HWND hwnd) {
    Resp r = callServer("\"GetActiveTrains\"");
    HWND list = GetDlgItem(hwnd, IDC_TRAIN_LIST);
    ListView_DeleteAllItems(list);
    std::string v;
    std::string raw = r.raw;
    // 用 parseTrains 解析
    size_t pp = raw.find("\"trains\"");
    if (pp == std::string::npos) { setBottomText(hwnd, L"车次列表获取失败"); return; }
    std::vector<Train> trains = parseTrains(raw);
    int i = 0;
    for (auto& t : trains) {
        LVITEMW it = {0};
        it.mask = LVIF_TEXT;
        it.iItem = i;
        it.pszText = const_cast<LPWSTR>(t.num.c_str());
        ListView_InsertItem(list, &it);
        ListView_SetItemText(list, i, 1, const_cast<LPWSTR>(t.dep.c_str()));
        ListView_SetItemText(list, i, 2, const_cast<LPWSTR>(t.arr.c_str()));
        ListView_SetItemText(list, i, 3, const_cast<LPWSTR>(t.deptime.c_str()));
        ListView_SetItemText(list, i, 4, const_cast<LPWSTR>(t.platform.c_str()));
        ListView_SetItemText(list, i, 5, const_cast<LPWSTR>(statusEn2Zh(t.status).c_str()));
        i++;
    }
    wchar_t buf[128];
    swprintf(buf, 128, L"车次共 %d 列", i);
    setBottomText(hwnd, buf);
}

static void refreshStatus(HWND hwnd) {
    // 队列
    Resp q = callServer("\"GetQueueStatus\"");
    int size = 0; std::string next;
    jsonGetInt(q.raw, "size", size);
    jsonGetString(q.raw, "next_broadcast", next);
    std::wstring wnext = next.empty() ? L"无" : gbkToWide(next);
    SetDlgItemTextW(hwnd, IDC_QUEUE_LBL, (L"队列：待播 " + std::to_wstring(size) + L" 条；下一条：" + wnext).c_str());

    // 音频
    Resp a = callServer("\"GetAudioStatus\"");
    std::string st, cur;
    jsonGetString(a.raw, "status", st);
    jsonGetString(a.raw, "current", cur);
    std::wstring wst = gbkToWide(st);
    std::wstring audioText = L"音频：";
    if (wst == L"playing") audioText += L"播放中";
    else if (wst == L"paused") audioText += L"已暂停";
    else if (wst == L"idle") audioText += L"空闲";
    else if (wst == L"stopped") audioText += L"已停止";
    else audioText += wst;
    if (!cur.empty()) audioText += L"（" + gbkToWide(cur) + L"）";
    SetDlgItemTextW(hwnd, IDC_AUDIO_LBL, audioText.c_str());

    // 系统
    Resp s = callServer("\"GetSystemStatus\"");
    int acct = 0, qsz = 0; bool autoM = false; bool run = true;
    jsonGetInt(s.raw, "account_count", acct);
    jsonGetInt(s.raw, "queue_size", qsz);
    jsonGetBool(s.raw, "auto_mode", autoM);
    jsonGetBool(s.raw, "is_running", run);
    std::wstring sys = L"系统：";
    sys += run ? L"运行中" : L"已停止";
    sys += L"；自动模式 ";
    sys += autoM ? L"开" : L"关";
    sys += L"；账号 ";
    sys += std::to_wstring(acct) + L" 个；队列 ";
    sys += std::to_wstring(qsz);
    SetDlgItemTextW(hwnd, IDC_SYS_LBL, sys.c_str());
}

static std::wstring getEditW(HWND hwnd, int id) {
    int len = GetWindowTextLengthW(GetDlgItem(hwnd, id));
    std::wstring s(len, 0);
    GetWindowTextW(GetDlgItem(hwnd, id), &s[0], len + 1);
    return trimW(s);
}

// 主窗口过程
// 主控制台深色配色
#define MAIN_BG          RGB(26, 37, 64)
#define MAIN_TEXT        RGB(220, 228, 240)
#define MAIN_EDIT_BG     RGB(14, 28, 54)
#define MAIN_LIST_BG     RGB(14, 28, 54)
#define MAIN_BTN_BLUE    RGB(42, 93, 176)
#define MAIN_BTN_BLUE_HI RGB(60, 120, 210)
#define MAIN_BTN_GRAY    RGB(58, 74, 102)
#define MAIN_BTN_GRAY_HI RGB(78, 98, 130)
#define MAIN_SECTION     RGB(100, 140, 200)

static HBRUSH g_hMainBg = nullptr;
static HBRUSH g_hMainEditBg = nullptr;

// 主控制台深色配色 - 优化后的配色方案
#define MAIN_BG          RGB(15, 23, 42)      // 深蓝背景
#define MAIN_TOP_BG      RGB(30, 41, 59)      // 顶部栏
#define MAIN_PANEL_BG    RGB(30, 41, 59)      // 面板背景
#define MAIN_TEXT        RGB(226, 232, 240)   // 主文字
#define MAIN_TEXT_DIM    RGB(148, 163, 184)   // 次要文字
#define MAIN_ACCENT      RGB(59, 130, 246)    // 强调蓝
#define MAIN_ACCENT_HI   RGB(96, 165, 250)    // 高亮蓝
#define MAIN_SUCCESS     RGB(34, 197, 94)     // 成功绿
#define MAIN_WARNING     RGB(251, 191, 36)    // 警告黄
#define MAIN_DANGER      RGB(239, 68, 68)     // 危险红
#define MAIN_TAB_ACTIVE  RGB(59, 130, 246)
#define MAIN_TAB_INACTIVE RGB(51, 65, 85)
#define MAIN_EDIT_BG     RGB(15, 23, 42)

static HBRUSH g_hMainTopBg = nullptr;
static int g_activeTab = 0; // 0=广播 1=车次 2=大屏 3=系统 4=设置

// 切换面板
static void SwitchPanel(HWND hwnd, int tab) {
    g_activeTab = tab;
    ShowWindow(GetDlgItem(hwnd, IDC_PANEL_BROADCAST), tab == 0 ? SW_SHOW : SW_HIDE);
    ShowWindow(GetDlgItem(hwnd, IDC_PANEL_TRAIN), tab == 1 ? SW_SHOW : SW_HIDE);
    ShowWindow(GetDlgItem(hwnd, IDC_PANEL_SCREEN), tab == 2 ? SW_SHOW : SW_HIDE);
    ShowWindow(GetDlgItem(hwnd, IDC_PANEL_SYSTEM), tab == 3 ? SW_SHOW : SW_HIDE);
    ShowWindow(GetDlgItem(hwnd, IDC_PANEL_BROADCAST_SET), tab == 4 ? SW_SHOW : SW_HIDE);
    InvalidateRect(hwnd, nullptr, TRUE);
}

// 自适应布局 - 左侧导航栏风格
static void LayoutMain(HWND hwnd) {
    RECT rc; GetClientRect(hwnd, &rc);
    int W = rc.right, H = rc.bottom;
    if (W < 800 || H < 500) return;

    int topH = 60;      // 顶部栏高度
    int sideW = 180;    // 左侧导航宽度
    int bottomH = 35;   // 底部状态栏高度
    int contentX = sideW;
    int contentY = topH;
    int contentW = W - sideW;
    int contentH = H - contentY - bottomH;

    // 顶部栏
    MoveWindow(GetDlgItem(hwnd, IDC_TOP_TITLE), 65, 15, 350, 30, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_TOP_WELCOME), W - 200, 15, 180, 30, TRUE);

    // 左侧导航按钮（垂直排列）
    int navH = 45;
    int navGap = 2;
    int navY = 10;
    MoveWindow(GetDlgItem(hwnd, IDC_TAB_BROADCAST), 0, navY, sideW, navH, TRUE); navY += navH + navGap;
    MoveWindow(GetDlgItem(hwnd, IDC_TAB_TRAIN), 0, navY, sideW, navH, TRUE); navY += navH + navGap;
    MoveWindow(GetDlgItem(hwnd, IDC_TAB_SCREEN), 0, navY, sideW, navH, TRUE); navY += navH + navGap;
    MoveWindow(GetDlgItem(hwnd, IDC_TAB_SYSTEM), 0, navY, sideW, navH, TRUE); navY += navH + navGap;
    MoveWindow(GetDlgItem(hwnd, IDC_TAB_BROADCAST_SET), 0, navY, sideW, navH, TRUE);

    // 五个面板 - 右侧内容区域
    int panelW = contentW - 20;
    int panelH = contentH - 10;
    MoveWindow(GetDlgItem(hwnd, IDC_PANEL_BROADCAST), contentX + 10, contentY + 5, panelW, panelH, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_PANEL_TRAIN), contentX + 10, contentY + 5, panelW, panelH, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_PANEL_SCREEN), contentX + 10, contentY + 5, panelW, panelH, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_PANEL_SYSTEM), contentX + 10, contentY + 5, panelW, panelH, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_PANEL_BROADCAST_SET), contentX + 10, contentY + 5, panelW, panelH, TRUE);

    // 获取当前显示的面板
    HWND hPanelTrain = GetDlgItem(hwnd, IDC_PANEL_TRAIN);
    if (IsWindowVisible(hPanelTrain)) {
        // 车次管理面板内容 - 自适应
        int listW = panelW - 40;
        int listH = max(150, panelH - 250);
        MoveWindow(GetDlgItem(hwnd, IDC_TRAIN_LIST), 20, 20, listW, listH, TRUE);

        int fy = listH + 35;
        int colW = min(140, (listW - 60) / 4);
        MoveWindow(GetDlgItem(hwnd, IDC_NUM), 90, fy, colW, 26, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_DEP), 90 + colW + 80, fy, colW, 26, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_ARR), 90 + (colW + 80) * 2, fy, colW, 26, TRUE);

        int fy2 = fy + 36;
        MoveWindow(GetDlgItem(hwnd, IDC_DEPT), 90, fy2, colW, 26, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PLAT), 90 + colW + 80, fy2, 60, 26, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_STATUS_CMB), 90 + colW + 80 + 80, fy2, 120, 180, TRUE);

        int by = fy2 + 42;
        int btnW = min(100, (listW - 40) / 4);
        MoveWindow(GetDlgItem(hwnd, IDC_ADD), 20, by, btnW, 32, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_UPD), 20 + btnW + 10, by, btnW + 15, 32, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_DEL), 20 + (btnW + 10) * 2 + 15, by, btnW, 32, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_REFRESH), 20 + (btnW + 10) * 3 + 15, by, btnW, 32, TRUE);
    }

    // 广播管理面板内容 - 自适应
    HWND hPanelBrd = GetDlgItem(hwnd, IDC_PANEL_BROADCAST);
    if (IsWindowVisible(hPanelBrd)) {
        int ctrlW = min(120, (panelW - 100) / 6);
        // 快捷按钮行1
        MoveWindow(GetDlgItem(hwnd, IDC_PB_WAITING), 20, 20, ctrlW, 36, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PB_CHECKIN), 20 + ctrlW + 10, 20, ctrlW, 36, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PB_PLATFORM), 20 + (ctrlW + 10) * 2, 20, ctrlW, 36, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PB_TRACK), 20 + (ctrlW + 10) * 3, 20, ctrlW, 36, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PB_TRAFFIC), 20 + (ctrlW + 10) * 4, 20, ctrlW, 36, TRUE);
        // 快捷按钮行2
        MoveWindow(GetDlgItem(hwnd, IDC_PB_DELAY2), 20, 65, ctrlW, 36, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PB_CANCEL), 20 + ctrlW + 10, 65, ctrlW, 36, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PB_CHIME), 20 + (ctrlW + 10) * 2, 65, ctrlW, 36, TRUE);

        // 类型 / 优先级（避开快捷按钮第二行 y=65）
        int formY = 118;
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_BTYPE), 20, formY, 50, 22, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_BTYPE_CMB), 70, formY - 2, 120, 180, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_PRI), 210, formY, 55, 22, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PRI), 270, formY - 2, 40, 24, TRUE);

        // 消息输入区
        int msgY = 158;
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_MSG), 20, msgY, 50, 22, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_MSG), 70, msgY - 2, panelW - 200, 26, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_SEND), panelW - 120, msgY - 4, 100, 28, TRUE);

        // 音频文件区
        int audioY = 206;
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_AUDIO), 20, audioY, 70, 22, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_AUDIO_FILE), 90, audioY - 2, panelW - 430, 26, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PLAY), panelW - 330, audioY - 4, 80, 28, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_STOP), panelW - 240, audioY - 4, 80, 28, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PAUSE), panelW - 150, audioY - 4, 80, 28, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_RESUME), panelW - 60, audioY - 4, 50, 28, TRUE);

        // 音量控制区 - 使用 Trackbar
        int volY = 256;
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_VOL), 20, volY, 50, 22, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_VOL_SLIDER), 70, volY - 4, min(350, panelW - 320), 28, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_VOL_LABEL), 70 + min(350, panelW - 320) + 10, volY, 45, 26, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_SETVOL), panelW - 140, volY - 2, 110, 32, TRUE);
    }

    // 底部状态栏 - 固定在底部
    MoveWindow(GetDlgItem(hwnd, IDC_BOTTOM_LBL), 15, H - bottomH + 5, W - 240, bottomH - 8, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_BTN_LOGOUT), W - 220, H - bottomH + 2, 100, 32, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_BTN_EXIT), W - 110, H - bottomH + 2, 100, 32, TRUE);
}

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

    // 在登录窗口上显示"系统正在加载中，请稍后"
    if (g_hLogin && IsWindow(g_hLogin)) {
        // 先清空窗口，画一个深色背景
        HDC hdc = GetDC(g_hLogin);
        RECT rc; GetClientRect(g_hLogin, &rc);
        HBRUSH hBg = CreateSolidBrush(RGB(26, 37, 64));
        FillRect(hdc, &rc, hBg);
        DeleteObject(hBg);

        // 画文字
        SetBkMode(hdc, TRANSPARENT);
        SetTextColor(hdc, RGB(220, 228, 240));
        HFONT hFont = CreateFontW(22, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            DEFAULT_QUALITY, DEFAULT_PITCH | FF_SWISS, L"Microsoft YaHei");
        HFONT hOld = (HFONT)SelectObject(hdc, hFont);
        // 手动计算居中位置
        std::wstring text = L"系统正在加载中，请稍后...";
        SIZE textSize;
        GetTextExtentPoint32W(hdc, text.c_str(), (int)text.length(), &textSize);
        int x = (rc.right - textSize.cx) / 2;
        int y = (rc.bottom - textSize.cy) / 2;
        TextOutW(hdc, x, y, text.c_str(), (int)text.length());
        SelectObject(hdc, hOld);
        DeleteObject(hFont);
        ReleaseDC(g_hLogin, hdc);
        UpdateWindow(g_hLogin);
    }

    // 启动 Python UI 程序（打包好的 exe）
    std::wstring root = GetAppRoot();
    std::wstring uiExe = root + L"\\dist\\main_ui\\main_ui.exe";
    std::wstring params = L"\"" + uiExe + L"\"";

    STARTUPINFOW si = {sizeof(si)};
    PROCESS_INFORMATION pi = {0};
    CreateProcessW(nullptr, (LPWSTR)params.data(), nullptr, nullptr, FALSE,
                   0, nullptr, root.c_str(), &si, &pi);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    // 等待 1 秒，让 Python UI 完全启动并显示
    Sleep(1000);

    // 隐藏登录窗口并退出
    if (g_hLogin && IsWindow(g_hLogin)) ShowWindow(g_hLogin, SW_HIDE);
    PostQuitMessage(0);
}

static LRESULT CALLBACK MainProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        g_hMainBg = CreateSolidBrush(MAIN_BG);
        g_hMainEditBg = CreateSolidBrush(MAIN_EDIT_BG);
        g_hMainTopBg = CreateSolidBrush(MAIN_TOP_BG);

        g_font = CreateFontW(14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");
        HFONT fTitle = CreateFontW(20, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");
        HFONT fTab = CreateFontW(14, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");
        HFONT fCity = CreateFontW(24, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");

        // === 顶部栏 ===
        CreateWindowExW(0, L"STATIC", L"旅客服务智能管理广播系统",
            WS_CHILD|WS_VISIBLE, 20, 12, 300, 30, hwnd, (HMENU)IDC_TOP_TITLE, nullptr, nullptr);
        SendMessageW(GetDlgItem(hwnd, IDC_TOP_TITLE), WM_SETFONT, (WPARAM)fTitle, TRUE);

        CreateWindowExW(0, L"STATIC", L"调度中心",
            WS_CHILD|WS_VISIBLE|SS_CENTER, 0, 10, 100, 40, hwnd, (HMENU)IDC_TOP_CITY, nullptr, nullptr);
        SendMessageW(GetDlgItem(hwnd, IDC_TOP_CITY), WM_SETFONT, (WPARAM)fCity, TRUE);

        CreateWindowExW(0, L"STATIC", L"",
            WS_CHILD, 0, 0, 10, 10, hwnd, (HMENU)IDC_TOP_WELCOME, nullptr, nullptr);

        // === 导航标签（5个）===
        CreateWindowExW(0, L"BUTTON", L"广播管理",
            WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 0, 0, 110, 30, hwnd, (HMENU)IDC_TAB_BROADCAST, nullptr, nullptr);
        SendMessageW(GetDlgItem(hwnd, IDC_TAB_BROADCAST), WM_SETFONT, (WPARAM)fTab, TRUE);

        CreateWindowExW(0, L"BUTTON", L"车辆管理",
            WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 0, 0, 110, 30, hwnd, (HMENU)IDC_TAB_TRAIN, nullptr, nullptr);
        SendMessageW(GetDlgItem(hwnd, IDC_TAB_TRAIN), WM_SETFONT, (WPARAM)fTab, TRUE);

        CreateWindowExW(0, L"BUTTON", L"车站大屏",
            WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 0, 0, 110, 30, hwnd, (HMENU)IDC_TAB_SCREEN, nullptr, nullptr);
        SendMessageW(GetDlgItem(hwnd, IDC_TAB_SCREEN), WM_SETFONT, (WPARAM)fTab, TRUE);

        CreateWindowExW(0, L"BUTTON", L"系统设置",
            WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 0, 0, 110, 30, hwnd, (HMENU)IDC_TAB_SYSTEM, nullptr, nullptr);
        SendMessageW(GetDlgItem(hwnd, IDC_TAB_SYSTEM), WM_SETFONT, (WPARAM)fTab, TRUE);

        CreateWindowExW(0, L"BUTTON", L"广播设置",
            WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 0, 0, 110, 30, hwnd, (HMENU)IDC_TAB_BROADCAST_SET, nullptr, nullptr);
        SendMessageW(GetDlgItem(hwnd, IDC_TAB_BROADCAST_SET), WM_SETFONT, (WPARAM)fTab, TRUE);

        // === 面板 1：车次管理 ===
        CreateWindowExW(0, L"STATIC", L"",
            WS_CHILD, 0, 0, 100, 100, hwnd, (HMENU)IDC_PANEL_TRAIN, nullptr, nullptr);

        HWND list = CreateWindowExW(WS_EX_CLIENTEDGE, WC_LISTVIEWW, L"",
            WS_CHILD|WS_VISIBLE|LVS_REPORT|LVS_SINGLESEL, 15, 15, 580, 450, GetDlgItem(hwnd, IDC_PANEL_TRAIN), (HMENU)IDC_TRAIN_LIST, nullptr, nullptr);
        ListView_SetExtendedListViewStyle(list, LVS_EX_FULLROWSELECT);
        ListView_SetBkColor(list, RGB(14, 28, 54));
        ListView_SetTextBkColor(list, RGB(14, 28, 54));
        ListView_SetTextColor(list, RGB(220, 228, 240));
        const wchar_t* cols[] = {L"车次", L"始发站", L"终点站", L"发车时间", L"站台", L"检票口", L"状态"};
        int cw[] = {70, 80, 80, 80, 50, 60, 60};
        for (int i = 0; i < 7; i++) {
            LVCOLUMNW c = {0};
            c.mask = LVCF_TEXT|LVCF_WIDTH|LVCF_SUBITEM;
            c.pszText = (LPWSTR)cols[i];
            c.cx = cw[i];
            c.iSubItem = i;
            ListView_InsertColumn(list, i, &c);
        }

        HWND panel1 = GetDlgItem(hwnd, IDC_PANEL_TRAIN);
        CreateWindowExW(0, L"STATIC", L"车次号：", WS_CHILD|WS_VISIBLE, 20, 340, 60, 22, panel1, nullptr, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 90, 338, 80, 24, panel1, (HMENU)IDC_NUM, nullptr, nullptr);
        CreateWindowExW(0, L"STATIC", L"始发站：", WS_CHILD|WS_VISIBLE, 210, 340, 60, 22, panel1, nullptr, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 270, 338, 90, 24, panel1, (HMENU)IDC_DEP, nullptr, nullptr);
        CreateWindowExW(0, L"STATIC", L"到达站：", WS_CHILD|WS_VISIBLE, 380, 340, 60, 22, panel1, nullptr, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 440, 338, 90, 24, panel1, (HMENU)IDC_ARR, nullptr, nullptr);

        CreateWindowExW(0, L"STATIC", L"发车时间：", WS_CHILD|WS_VISIBLE, 20, 372, 60, 22, panel1, nullptr, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 90, 370, 80, 24, panel1, (HMENU)IDC_DEPT, nullptr, nullptr);
        CreateWindowExW(0, L"STATIC", L"站台：", WS_CHILD|WS_VISIBLE, 210, 372, 60, 22, panel1, nullptr, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 250, 370, 40, 24, panel1, (HMENU)IDC_PLAT, nullptr, nullptr);
        CreateWindowExW(0, L"STATIC", L"状态：", WS_CHILD|WS_VISIBLE, 320, 372, 60, 22, panel1, nullptr, nullptr, nullptr);
        HWND cmb = CreateWindowExW(0, L"COMBOBOX", L"", WS_CHILD|WS_VISIBLE|CBS_DROPDOWNLIST, 360, 370, 110, 180, panel1, (HMENU)IDC_STATUS_CMB, nullptr, nullptr);
        for (int i = 0; i < 6; i++) SendMessageW(cmb, CB_ADDSTRING, 0, (LPARAM)STATUS_ITEMS[i]);
        SendMessageW(cmb, CB_SETCURSEL, 0, 0);

        CreateWindowExW(0, L"BUTTON", L"添加", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 20, 410, 80, 28, panel1, (HMENU)IDC_ADD, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"更新选中状态", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 105, 410, 110, 28, panel1, (HMENU)IDC_UPD, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"移除选中", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 220, 410, 90, 28, panel1, (HMENU)IDC_DEL, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"刷新", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 315, 410, 80, 28, panel1, (HMENU)IDC_REFRESH, nullptr, nullptr);

        // === 面板 2：广播管理 ===
        CreateWindowExW(0, L"STATIC", L"",
            WS_CHILD, 0, 0, 100, 100, hwnd, (HMENU)IDC_PANEL_BROADCAST, nullptr, nullptr);
        HWND panel2 = GetDlgItem(hwnd, IDC_PANEL_BROADCAST);

        // 分类快捷广播按钮（修复重复 ID，每个按钮有唯一 ID）
        CreateWindowExW(0, L"BUTTON", L"候车室广播", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 20, 20, 110, 35, panel2, (HMENU)IDC_PB_WAITING, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"检票口广播", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 140, 20, 110, 35, panel2, (HMENU)IDC_PB_CHECKIN, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"站台广播", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 260, 20, 110, 35, panel2, (HMENU)IDC_PB_PLATFORM, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"股道广播", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 380, 20, 110, 35, panel2, (HMENU)IDC_PB_TRACK, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"行车广播", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 500, 20, 110, 35, panel2, (HMENU)IDC_PB_TRAFFIC, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"晚点广播", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 620, 20, 110, 35, panel2, (HMENU)IDC_PB_DELAY2, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"停运广播", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 20, 65, 110, 35, panel2, (HMENU)IDC_PB_CANCEL, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"提示音",   WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 140, 65, 110, 35, panel2, (HMENU)IDC_PB_CHIME, nullptr, nullptr);

        CreateWindowExW(0, L"STATIC", L"类型：", WS_CHILD|WS_VISIBLE, 20, 118, 50, 22, panel2, (HMENU)IDC_LBL_BTYPE, nullptr, nullptr);
        HWND bt = CreateWindowExW(0, L"COMBOBOX", L"", WS_CHILD|WS_VISIBLE|CBS_DROPDOWNLIST, 70, 116, 120, 180, panel2, (HMENU)IDC_BTYPE_CMB, nullptr, nullptr);
        for (int i = 0; i < 7; i++) SendMessageW(bt, CB_ADDSTRING, 0, (LPARAM)BTYPE_ITEMS[i]);
        SendMessageW(bt, CB_SETCURSEL, 0, 0);

        CreateWindowExW(0, L"STATIC", L"优先级：", WS_CHILD|WS_VISIBLE, 210, 118, 55, 22, panel2, (HMENU)IDC_LBL_PRI, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"5", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL|ES_NUMBER, 270, 116, 40, 24, panel2, (HMENU)IDC_PRI, nullptr, nullptr);

        CreateWindowExW(0, L"STATIC", L"内容：", WS_CHILD|WS_VISIBLE, 20, 158, 50, 22, panel2, (HMENU)IDC_LBL_MSG, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 70, 156, 600, 24, panel2, (HMENU)IDC_MSG, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"发送广播", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 690, 154, 100, 28, panel2, (HMENU)IDC_SEND, nullptr, nullptr);

        CreateWindowExW(0, L"STATIC", L"音频文件：", WS_CHILD|WS_VISIBLE, 20, 206, 70, 22, panel2, (HMENU)IDC_LBL_AUDIO, nullptr, nullptr);
        CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 90, 204, 390, 24, panel2, (HMENU)IDC_AUDIO_FILE, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"播放", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 490, 202, 80, 28, panel2, (HMENU)IDC_PLAY, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"停止", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 580, 202, 80, 28, panel2, (HMENU)IDC_STOP, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"暂停", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 670, 202, 80, 28, panel2, (HMENU)IDC_PAUSE, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"恢复", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 760, 202, 80, 28, panel2, (HMENU)IDC_RESUME, nullptr, nullptr);

        // 音量控制 - 使用 Trackbar 滑块替代静态文本
        CreateWindowExW(0, L"STATIC", L"音量：", WS_CHILD|WS_VISIBLE, 20, 256, 50, 22, panel2, (HMENU)IDC_LBL_VOL, nullptr, nullptr);
        HWND hVolSlider = CreateWindowExW(0, TRACKBAR_CLASSW, L"",
            WS_CHILD|WS_VISIBLE|TBS_HORZ|TBS_AUTOTICKS,
            70, 252, 300, 30, panel2, (HMENU)IDC_VOL_SLIDER, nullptr, nullptr);
        SendMessageW(hVolSlider, TBM_SETRANGE, TRUE, MAKELPARAM(0, 100));
        SendMessageW(hVolSlider, TBM_SETPOS, TRUE, 80);
        SendMessageW(hVolSlider, TBM_SETTICFREQ, 10, 0);

        // 音量数值显示
        CreateWindowExW(0, L"STATIC", L"80%", WS_CHILD|WS_VISIBLE|SS_CENTER,
            380, 256, 40, 22, panel2, (HMENU)IDC_VOL_LABEL, nullptr, nullptr);

        CreateWindowExW(0, L"BUTTON", L"设置音量", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW,
            430, 252, 90, 28, panel2, (HMENU)IDC_SETVOL, nullptr, nullptr);

        // === 面板 3：车站大屏（占位）===
        CreateWindowExW(0, L"STATIC", L"",
            WS_CHILD, 0, 0, 100, 100, hwnd, (HMENU)IDC_PANEL_SCREEN, nullptr, nullptr);
        HWND panelS = GetDlgItem(hwnd, IDC_PANEL_SCREEN);
        CreateWindowExW(0, L"STATIC", L"车站大屏 - 待开发",
            WS_CHILD|WS_VISIBLE|SS_CENTER, 20, 100, 400, 40, panelS, nullptr, nullptr, nullptr);

        // === 面板 4：系统设置 ===
        CreateWindowExW(0, L"STATIC", L"",
            WS_CHILD, 0, 0, 100, 100, hwnd, (HMENU)IDC_PANEL_SYSTEM, nullptr, nullptr);
        HWND panel3 = GetDlgItem(hwnd, IDC_PANEL_SYSTEM);
        CreateWindowExW(0, L"BUTTON", L"自动广播模式", WS_CHILD|WS_VISIBLE|BS_AUTOCHECKBOX, 20, 20, 120, 24, panel3, (HMENU)IDC_AUTO_CHK, nullptr, nullptr);
        SendMessageW(GetDlgItem(hwnd, IDC_AUTO_CHK), BM_SETCHECK, BST_CHECKED, 0);
        CreateWindowExW(0, L"STATIC", L"队列：-", WS_CHILD|WS_VISIBLE, 20, 60, 400, 22, panel3, (HMENU)IDC_QUEUE_LBL, nullptr, nullptr);
        CreateWindowExW(0, L"STATIC", L"音频：-", WS_CHILD|WS_VISIBLE, 20, 90, 400, 22, panel3, (HMENU)IDC_AUDIO_LBL, nullptr, nullptr);
        CreateWindowExW(0, L"STATIC", L"系统：-", WS_CHILD|WS_VISIBLE, 20, 120, 400, 22, panel3, (HMENU)IDC_SYS_LBL, nullptr, nullptr);

        // === 面板 5：广播设置（占位）===
        CreateWindowExW(0, L"STATIC", L"",
            WS_CHILD, 0, 0, 100, 100, hwnd, (HMENU)IDC_PANEL_BROADCAST_SET, nullptr, nullptr);
        HWND panelBS = GetDlgItem(hwnd, IDC_PANEL_BROADCAST_SET);
        CreateWindowExW(0, L"STATIC", L"广播设置 - 待开发",
            WS_CHILD|WS_VISIBLE|SS_CENTER, 20, 100, 400, 40, panelBS, nullptr, nullptr, nullptr);

        // === 底部状态栏 ===
        CreateWindowExW(0, L"STATIC", L"就绪", WS_CHILD|WS_VISIBLE|SS_SUNKEN, 10, 0, 600, 24, hwnd, (HMENU)IDC_BOTTOM_LBL, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"退出登录", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 770, 0, 100, 30, hwnd, (HMENU)IDC_BTN_LOGOUT, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"关闭系统", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 880, 0, 100, 30, hwnd, (HMENU)IDC_BTN_EXIT, nullptr, nullptr);

        // 统一字体
        HWND h = GetWindow(hwnd, GW_CHILD);
        while (h) { SendMessageW(h, WM_SETFONT, (WPARAM)g_font, TRUE); h = GetWindow(h, GW_HWNDNEXT); }

        disableCloseButton(hwnd);
        SetTimer(hwnd, 1, 3000, nullptr);

        refreshTrains(hwnd);
        refreshStatus(hwnd);
        SwitchPanel(hwnd, 0); // 默认显示广播管理
        LayoutMain(hwnd);
        return 0;
    }
    case WM_ERASEBKGND:
        return 1; // 不擦除，直接 WM_PAINT 画背景图
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);
        RECT rc; GetClientRect(hwnd, &rc);
        {
            Graphics g(hdc);
            g.SetSmoothingMode(SmoothingModeAntiAlias);
            g.SetInterpolationMode(InterpolationModeHighQualityBicubic);

            // 画 startup3.png 作为整个窗口背景
            std::wstring root = GetAppRoot();
            std::wstring i1 = root + L"\\images\\startup3.png";
            std::wstring i2 = root + L"\\images\\startup3.jpg";
            Image* img = nullptr;
            const wchar_t* paths[] = { i1.c_str(), i2.c_str(), L"images\\startup3.png", L"images\\startup3.jpg" };
            for (auto pp : paths) {
                if (GetFileAttributesW(pp) != INVALID_FILE_ATTRIBUTES) {
                    img = Image::FromFile(pp);
                    if (img && img->GetLastStatus() == Ok) break;
                    delete img; img = nullptr;
                }
            }
            if (img) {
                g.DrawImage(img, 0, 0, rc.right, rc.bottom);
                delete img;
            }

            // 左上角画铁路 logo
            {
                std::wstring logoPath = root + L"\\images\\tl.png";
                if (GetFileAttributesW(logoPath.c_str()) != INVALID_FILE_ATTRIBUTES) {
                    Image* logo = Image::FromFile(logoPath.c_str());
                    if (logo && logo->GetLastStatus() == Ok) {
                        g.DrawImage(logo, 5, 5, 50, 50);
                    }
                    delete logo;
                }
            }

            // 顶部栏半透明深色覆盖
            SolidBrush topBrush(Color(230, 15, 22, 38));
            g.FillRectangle(&topBrush, 0, 0, rc.right, 60);

            // 导航栏半透明深色覆盖
            SolidBrush navBrush(Color(180, 20, 30, 50));
            g.FillRectangle(&navBrush, 0, 60, rc.right, 45);

            // 内容区半透明深色卡片
            SolidBrush contentBrush(Color(180, 25, 35, 60));
            g.FillRectangle(&contentBrush, 10, 115, rc.right - 20, rc.bottom - 155);

            // 底部栏半透明深色覆盖
            SolidBrush bottomBrush(Color(230, 15, 22, 38));
            g.FillRectangle(&bottomBrush, 0, rc.bottom - 30, rc.right, 30);
        }
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_CTLCOLORSTATIC: {
        HDC hdc = (HDC)wp;
        SetTextColor(hdc, RGB(220, 228, 240));
        SetBkMode(hdc, TRANSPARENT);
        return (LRESULT)GetStockObject(NULL_BRUSH); // 透明背景，显示背景图
    }
    case WM_CTLCOLOREDIT: {
        HDC hdc = (HDC)wp;
        SetTextColor(hdc, RGB(240, 248, 255));
        SetBkColor(hdc, MAIN_EDIT_BG);
        return (LRESULT)g_hMainEditBg;
    }
    case WM_DRAWITEM: {
        LPDRAWITEMSTRUCT dis = (LPDRAWITEMSTRUCT)lp;
        RECT rc = dis->rcItem;
        UINT ctlId = dis->CtlID;

        // 导航标签按钮
        if (ctlId == IDC_TAB_BROADCAST || ctlId == IDC_TAB_TRAIN || ctlId == IDC_TAB_SCREEN || ctlId == IDC_TAB_SYSTEM || ctlId == IDC_TAB_BROADCAST_SET) {
            int tab = 0;
            if (ctlId == IDC_TAB_BROADCAST) tab = 0;
            else if (ctlId == IDC_TAB_TRAIN) tab = 1;
            else if (ctlId == IDC_TAB_SCREEN) tab = 2;
            else if (ctlId == IDC_TAB_SYSTEM) tab = 3;
            else tab = 4;
            bool active = (g_activeTab == tab);
            COLORREF bg = active ? MAIN_TAB_ACTIVE : MAIN_TAB_INACTIVE;

            HBRUSH bgBr = CreateSolidBrush(MAIN_TOP_BG);
            FillRect(dis->hDC, &rc, bgBr);
            DeleteObject(bgBr);

            HRGN rgn = CreateRoundRectRgn(rc.left, rc.top, rc.right + 1, rc.bottom + 1, 6, 6);
            SelectClipRgn(dis->hDC, rgn);
            HBRUSH br = CreateSolidBrush(bg);
            FillRect(dis->hDC, &rc, br);
            DeleteObject(br);

            SetBkMode(dis->hDC, TRANSPARENT);
            SetTextColor(dis->hDC, RGB(255, 255, 255));
            if (g_font) SelectObject(dis->hDC, g_font);
            wchar_t btnText[64] = {0};
            GetWindowTextW(dis->hwndItem, btnText, 64);
            DrawTextW(dis->hDC, btnText, -1, &rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE);

            SelectClipRgn(dis->hDC, nullptr);
            DeleteObject(rgn);
            return TRUE;
        }

        // 其他按钮
        bool isPrimary = (ctlId == IDC_ADD || ctlId == IDC_SEND);
        COLORREF bg = isPrimary ? MAIN_BTN_BLUE : MAIN_BTN_GRAY;
        COLORREF hover = isPrimary ? MAIN_BTN_BLUE_HI : MAIN_BTN_GRAY_HI;
        bool pressed = (dis->itemState & ODS_SELECTED) != 0;

        HBRUSH bgBr = CreateSolidBrush(MAIN_BG);
        FillRect(dis->hDC, &rc, bgBr);
        DeleteObject(bgBr);

        HRGN rgn = CreateRoundRectRgn(rc.left, rc.top, rc.right + 1, rc.bottom + 1, 6, 6);
        SelectClipRgn(dis->hDC, rgn);

        HBRUSH br = CreateSolidBrush(pressed ? hover : bg);
        FillRect(dis->hDC, &rc, br);
        DeleteObject(br);

        SetBkMode(dis->hDC, TRANSPARENT);
        SetTextColor(dis->hDC, RGB(255, 255, 255));
        if (g_font) SelectObject(dis->hDC, g_font);
        wchar_t btnText[64] = {0};
        GetWindowTextW(dis->hwndItem, btnText, 64);
        DrawTextW(dis->hDC, btnText, -1, &rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE);

        SelectClipRgn(dis->hDC, nullptr);
        DeleteObject(rgn);
        return TRUE;
    }
    case WM_HSCROLL: {
        // 处理音量滑块拖动
        if ((HWND)lp == GetDlgItem(hwnd, IDC_VOL_SLIDER)) {
            int v = (int)SendMessageW((HWND)lp, TBM_GETPOS, 0, 0);
            if (v < 0) v = 0; if (v > 100) v = 100;
            wchar_t volText[16];
            swprintf(volText, 16, L"%d%%", v);
            SetDlgItemTextW(hwnd, IDC_VOL_LABEL, volText);
        }
        return 0;
    }
    case WM_COMMAND: {
        int id = LOWORD(wp);
        switch (id) {
        case IDC_TAB_BROADCAST: SwitchPanel(hwnd, 0); break;
        case IDC_TAB_TRAIN: SwitchPanel(hwnd, 1); break;
        case IDC_TAB_SCREEN: SwitchPanel(hwnd, 2); break;
        case IDC_TAB_SYSTEM: SwitchPanel(hwnd, 3); break;
        case IDC_TAB_BROADCAST_SET: SwitchPanel(hwnd, 4); break;
        case IDC_ADD: {
            std::wstring num = getEditW(hwnd, IDC_NUM);
            if (num.empty()) { customMessageBoxW(hwnd, L"请输入车次号", L"提示", MB_OK); break; }
            std::wstring dep = getEditW(hwnd, IDC_DEP);
            std::wstring arr = getEditW(hwnd, IDC_ARR);
            std::wstring dt = getEditW(hwnd, IDC_DEPT);
            std::wstring plat = getEditW(hwnd, IDC_PLAT);
            int idx = (int)SendMessageW(GetDlgItem(hwnd, IDC_STATUS_CMB), CB_GETCURSEL, 0, 0);
            std::wstring sen = L"{\"AddTrain\":{\"train_number\":\"" + num + L"\",\"departure_station\":\"" + dep +
                L"\",\"arrival_station\":\"" + arr + L"\",\"departure_time\":\"" + dt + L"\",\"platform\":\"" + plat +
                L"\",\"status\":\"" + STATUS_EN[idx] + L"\"}}";
            Resp r = callServer(wideToUtf8(sen));
            setBottomText(hwnd, r.msg);
            if (r.ok) refreshTrains(hwnd);
            break;
        }
        case IDC_UPD: {
            int sel = ListView_GetNextItem(GetDlgItem(hwnd, IDC_TRAIN_LIST), -1, LVNI_SELECTED);
            if (sel < 0) { customMessageBoxW(hwnd, L"请先选择一列车次", L"提示", MB_OK); break; }
            wchar_t buf[64] = {0};
            ListView_GetItemText(GetDlgItem(hwnd, IDC_TRAIN_LIST), sel, 0, buf, 64);
            int idx = (int)SendMessageW(GetDlgItem(hwnd, IDC_STATUS_CMB), CB_GETCURSEL, 0, 0);
            std::wstring sen = L"{\"UpdateTrainStatus\":{\"train_number\":\"" + std::wstring(buf) + L"\",\"status\":\"" + STATUS_EN[idx] + L"\"}}";
            Resp r = callServer(wideToUtf8(sen));
            setBottomText(hwnd, r.msg);
            if (r.ok) { refreshTrains(hwnd); refreshStatus(hwnd); }
            break;
        }
        case IDC_DEL: {
            int sel = ListView_GetNextItem(GetDlgItem(hwnd, IDC_TRAIN_LIST), -1, LVNI_SELECTED);
            if (sel < 0) { customMessageBoxW(hwnd, L"请先选择一列车次", L"提示", MB_OK); break; }
            wchar_t buf[64] = {0};
            ListView_GetItemText(GetDlgItem(hwnd, IDC_TRAIN_LIST), sel, 0, buf, 64);
            if (customMessageBoxW(hwnd, (std::wstring(L"确定移除车次 ") + buf + L"？").c_str(), L"确认", MB_YESNO) != IDOK) break;
            std::wstring sen = L"{\"RemoveTrain\":{\"train_number\":\"" + std::wstring(buf) + L"\"}}";
            Resp r = callServer(wideToUtf8(sen));
            setBottomText(hwnd, r.msg);
            if (r.ok) refreshTrains(hwnd);
            break;
        }
        case IDC_REFRESH: refreshTrains(hwnd); refreshStatus(hwnd); break;
        case IDC_PB_WAITING:
        case IDC_PB_CHECKIN:
        case IDC_PB_BOARD: SendMessageW(GetDlgItem(hwnd, IDC_BTYPE_CMB), CB_SETCURSEL, 0, 0); break;
        case IDC_PB_DELAY:
        case IDC_PB_DELAY2: SendMessageW(GetDlgItem(hwnd, IDC_BTYPE_CMB), CB_SETCURSEL, 1, 0); break;
        case IDC_PB_SAFE:
        case IDC_PB_PLATFORM:
        case IDC_PB_TRACK:
        case IDC_PB_TRAFFIC: SendMessageW(GetDlgItem(hwnd, IDC_BTYPE_CMB), CB_SETCURSEL, 2, 0); break;
        case IDC_PB_EMG:
        case IDC_PB_CANCEL:
        case IDC_PB_CHIME: SendMessageW(GetDlgItem(hwnd, IDC_BTYPE_CMB), CB_SETCURSEL, 3, 0); break;
        case IDC_SEND: {
            std::wstring msg = getEditW(hwnd, IDC_MSG);
            if (msg.empty()) { customMessageBoxW(hwnd, L"请输入广播内容", L"提示", MB_OK); break; }
            int idx = (int)SendMessageW(GetDlgItem(hwnd, IDC_BTYPE_CMB), CB_GETCURSEL, 0, 0);
            int pri = _wtoi(getEditW(hwnd, IDC_PRI).c_str());
            if (pri < 1) pri = 5;
            std::wstring sen = L"{\"AddManualBroadcast\":{\"broadcast_type\":\"" + std::wstring(BTYPE_EN[idx]) +
                L"\",\"train_info\":null,\"message\":\"" + msg + L"\",\"audio_file\":null,\"priority\":" + std::to_wstring(pri) + L"}}";
            Resp r = callServer(wideToUtf8(sen));
            setBottomText(hwnd, r.msg);
            if (r.ok) { SetDlgItemTextW(hwnd, IDC_MSG, L""); refreshStatus(hwnd); }
            break;
        }
        case IDC_PLAY: {
            std::wstring f = getEditW(hwnd, IDC_AUDIO_FILE);
            if (f.empty()) { customMessageBoxW(hwnd, L"请输入音频文件名", L"提示", MB_OK); break; }
            std::wstring sen = L"{\"PlayAudio\":{\"path\":\"" + f + L"\"}}";
            Resp r = callServer(wideToUtf8(sen));
            setBottomText(hwnd, r.msg);
            refreshStatus(hwnd);
            break;
        }
        case IDC_STOP: { Resp r = callServer("\"StopAudio\""); setBottomText(hwnd, r.msg); refreshStatus(hwnd); break; }
        case IDC_PAUSE: { Resp r = callServer("\"PauseAudio\""); setBottomText(hwnd, r.msg); refreshStatus(hwnd); break; }
        case IDC_RESUME: { Resp r = callServer("\"ResumeAudio\""); setBottomText(hwnd, r.msg); refreshStatus(hwnd); break; }
        case IDC_SETVOL: {
            // 从 Trackbar 获取音量值
            HWND hSlider = GetDlgItem(hwnd, IDC_VOL_SLIDER);
            int v = (int)SendMessageW(hSlider, TBM_GETPOS, 0, 0);
            if (v < 0) v = 0; if (v > 100) v = 100;
            // 更新显示标签
            wchar_t volText[16];
            swprintf(volText, 16, L"%d%%", v);
            SetDlgItemTextW(hwnd, IDC_VOL_LABEL, volText);
            // 发送到服务器
            std::wstring sv = L"{\"SetVolume\":{\"volume\":" + std::to_wstring(v) + L"}}";
            Resp r = callServer(wideToUtf8(sv));
            setBottomText(hwnd, r.msg);
            break;
        }
        case IDC_AUTO_CHK: {
            bool on = SendMessageW(GetDlgItem(hwnd, IDC_AUTO_CHK), BM_GETCHECK, 0, 0) == BST_CHECKED;
            std::wstring sv = L"{\"SetAutoMode\":{\"enabled\":";
            sv += on ? L"true}}" : L"false}}";
            Resp r = callServer(wideToUtf8(sv));
            setBottomText(hwnd, r.msg);
            break;
        }
        case IDC_BTN_LOGOUT: {
            if (customMessageBoxW(hwnd, L"确定退出登录并返回登录窗口？", L"确认", MB_YESNO) != IDOK) break;
            g_isLogout = true;
            ShowLoginWindow();
            break;
        }
        case IDC_BTN_EXIT: {
            if (customMessageBoxW(hwnd, L"确定关闭整个系统并停止后端？", L"确认", MB_YESNO) != IDOK) break;
            g_isLogout = false;
            callServer("\"Shutdown\"");
            tcpClose();
            g_connected = false;
            PostQuitMessage(0);
            break;
        }
        }
        return 0;
    }
    case WM_SIZE:
        LayoutMain(hwnd);
        return 0;
    case WM_TIMER: refreshStatus(hwnd); return 0;
    case WM_CLOSE: return 0;
    case WM_DESTROY:
        KillTimer(hwnd, 1);
        if (g_hMainBg) { DeleteObject(g_hMainBg); g_hMainBg = nullptr; }
        if (g_hMainEditBg) { DeleteObject(g_hMainEditBg); g_hMainEditBg = nullptr; }
        if (g_hMainTopBg) { DeleteObject(g_hMainTopBg); g_hMainTopBg = nullptr; }
        if (g_font) { DeleteObject(g_font); g_font = nullptr; }
        g_hMain = nullptr;
        if (!g_isLogout) PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}


// ============================================================
// 启动画面（Splash）：异步加载完成后自动关闭进入登录
// ============================================================
static ULONG_PTR g_gdiToken = 0;
static HWND g_hSplash = nullptr;
// 开机音乐前置声明（实现在 playStartupSound 处）
static bool g_musicOpen = false;
static DWORD g_musicLengthMs = 0;
static DWORD g_splashStartTick = 0;
static bool musicDone();
static void stopStartupMusic();
static bool mainUiRunning(); // 实现在文件后部（主界面单实例检测）

// ---- 启动状态机（真实加载进度驱动，后台线程执行，UI 不卡） ----
// 阶段顺序：初始化配置 → 连接服务 → 检查更新 → 加载资源 → 启动主界面
static int  g_stage = 0;                 // 当前阶段 0-4
static int  g_realProgress = 0;          // 真实进度（后台线程推进，0-100）
static int  g_animProgress = 0;          // 显示进度（UI 平滑逼近真实进度）
static bool g_stageFailed = false;       // 加载失败（拉起主界面失败等）
static bool g_timeoutShown = false;      // 超时（10 秒）已显示按钮
static bool g_launchOk = false;          // 主界面已成功拉起
static bool g_abortExit = false;         // 用户在启动界面点了退出（不进登录）
static HANDLE g_hWorker = nullptr;       // 后台加载线程句柄
static Image* g_splashImg = nullptr;     // 背景图缓存（WM_CREATE 加载一次，避免每帧重解码）
static std::wstring g_splashStatus;      // 当前状态文字

// 启动日志（frontend_startup.log，根目录，追加）
static void WriteStartupLog(const wchar_t* stage, const wchar_t* result, DWORD ms) {
    std::wstring root = GetAppRoot();
    std::wstring logPath = root + L"\\frontend_startup.log";
    HANDLE h = CreateFileW(logPath.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ,
                           nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    SYSTEMTIME st; GetLocalTime(&st);
    wchar_t line[512];
    wsprintfW(line, L"[%04d-%02d-%02d %02d:%02d:%02d] %s %s (%lu ms)\r\n",
        st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond, stage, result, ms);
    DWORD w = 0;
    // 转 UTF-8 写入（记事本/终端均可正常阅读）
    char utf8[1024];
    int n = WideCharToMultiByte(CP_UTF8, 0, line, -1, utf8, sizeof(utf8), nullptr, nullptr);
    if (n > 1) WriteFile(h, utf8, (DWORD)(n - 1), &w, nullptr);
    CloseHandle(h);
}

// ---- 后台加载线程：真实执行五阶段，每阶段完成后通知主线程更新 UI ----
static DWORD WINAPI SplashWorkerThread(LPVOID param) {
    HWND hwnd = (HWND)param;
    std::wstring root = GetAppRoot();
    DWORD t0 = GetTickCount();

    // 阶段0：初始化配置（检查配置文件存在）
    DWORD ts = GetTickCount();
    int cfgOk = 0;
    const wchar_t* cfgs[] = { L"bcast_config.json", L"system_config.json", L"trains.json" };
    for (auto c : cfgs) {
        std::wstring p = root + L"\\" + c;
        if (GetFileAttributesW(p.c_str()) != INVALID_FILE_ATTRIBUTES) cfgOk++;
    }
    WriteStartupLog(L"初始化配置", cfgOk == 3 ? L"OK(3/3)" : L"部分缺失(记日志不阻塞)", GetTickCount() - ts);
    PostMessageW(hwnd, WM_APP + 1, 0, cfgOk == 3 ? 1 : 0);

    // 阶段1：连接服务（拉起后端 + TCP 探测；线程内执行，不卡 UI）
    ts = GetTickCount();
    launchBackend();
    tcpConnect(); // 内部有 4 秒重试，现在跑在后台线程
    WriteStartupLog(L"连接服务", L"OK(失败不阻塞)", GetTickCount() - ts);
    PostMessageW(hwnd, WM_APP + 1, 1, 1);

    // 阶段2：检查更新（无更新服务器：检查主界面程序是否就绪）
    ts = GetTickCount();
    std::wstring uiExe = root + L"\\dist\\main_ui\\main_ui.exe";
    bool uiReady = GetFileAttributesW(uiExe.c_str()) != INVALID_FILE_ATTRIBUTES;
    WriteStartupLog(L"检查更新", uiReady ? L"主界面就绪" : L"主界面缺失", GetTickCount() - ts);
    PostMessageW(hwnd, WM_APP + 1, 2, uiReady ? 1 : 0);

    // 阶段3：加载资源（背景图与音频目录）
    ts = GetTickCount();
    std::wstring img = root + L"\\images\\startup.png";
    std::wstring audio = root + L"\\audio";
    bool imgOk = GetFileAttributesW(img.c_str()) != INVALID_FILE_ATTRIBUTES;
    bool audOk = GetFileAttributesW(audio.c_str()) != INVALID_FILE_ATTRIBUTES;
    WriteStartupLog(L"加载资源", (imgOk && audOk) ? L"OK" : L"资源缺失", GetTickCount() - ts);
    PostMessageW(hwnd, WM_APP + 1, 3, (imgOk && audOk) ? 1 : 0);

    // 阶段4：启动主界面（就绪检查；实际拉起仍在登录成功后执行，保持原流程不变）
    ts = GetTickCount();
    bool launchOk = uiReady; // 主界面程序就绪即视为通过
    WriteStartupLog(L"启动主界面", launchOk ? L"就绪(登录后拉起)" : L"主界面缺失", GetTickCount() - ts);
    PostMessageW(hwnd, WM_APP + 2, launchOk ? 1 : 0, 0);
    (void)t0;
    return 0;
}

// GDI+ 按比例居中裁切铺满（cover 模式，不拉伸变形）
static void DrawImageCover(Graphics& g, Image* img, int dstX, int dstY, int dstW, int dstH) {
    int iw = (int)img->GetWidth(), ih = (int)img->GetHeight();
    if (iw <= 0 || ih <= 0) return;
    float scale = ((float)dstW / iw > (float)dstH / ih) ? (float)dstW / iw : (float)dstH / ih;
    int sw = (int)(dstW / scale), sh = (int)(dstH / scale);
    int sx = (iw - sw) / 2, sy = (ih - sh) / 2;
    g.DrawImage(img, RectF((REAL)dstX, (REAL)dstY, (REAL)dstW, (REAL)dstH),
                (REAL)sx, (REAL)sy, (REAL)sw, (REAL)sh, UnitPixel);
}

// GDI+ 圆角矩形填充
static void GdiFillRoundRect(Graphics& g, const RectF& rc, float r, const SolidBrush& br) {
    GraphicsPath path;
    float d = r * 2.0f;
    path.AddArc(RectF(rc.X, rc.Y, d, d), 180, 90);
    path.AddArc(RectF(rc.GetRight() - d, rc.Y, d, d), 270, 90);
    path.AddArc(RectF(rc.GetRight() - d, rc.GetBottom() - d, d, d), 0, 90);
    path.AddArc(RectF(rc.X, rc.GetBottom() - d, d, d), 90, 90);
    path.CloseFigure();
    g.FillPath(&br, &path);
}

static LRESULT CALLBACK SplashProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        // 多屏适配：以鼠标所在显示器为目标屏，窗口按屏幕比例缩放居中
        POINT pt; GetCursorPos(&pt);
        HMONITOR mon = MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST);
        MONITORINFO mi = { sizeof(mi) };
        GetMonitorInfoW(mon, &mi);
        int sw = mi.rcWork.right - mi.rcWork.left;
        int sh = mi.rcWork.bottom - mi.rcWork.top;
        // 窗口尺寸按屏幕比例（宽 50%、高 56%），带上下限
        int w = sw / 2, h = (int)(sh * 0.56f);
        if (w > 1200) w = 1200;
        if (h > 675) h = 675;
        if (w < 800) w = 800;
        if (h < 450) h = 450;
        int x = mi.rcWork.left + (sw - w) / 2;
        int y = mi.rcWork.top + (sh - h) / 2;
        SetWindowPos(hwnd, HWND_TOPMOST, x, y, w, h, SWP_SHOWWINDOW);

        // 背景图只加载一次并缓存（消除每帧重解码导致的卡顿）
        if (g_splashImg) { delete g_splashImg; g_splashImg = nullptr; }
        std::wstring root = GetAppRoot();
        std::wstring i1 = root + L"\\images\\startup.png";
        std::wstring i2 = root + L"\\images\\startup.jpg";
        std::wstring i3 = root + L"\\images\\startup.bmp";
        const wchar_t* paths[] = { i1.c_str(), i2.c_str(), i3.c_str(),
                                  L"images\\startup.png", L"images\\startup.jpg", L"images\\startup.bmp" };
        for (auto pp : paths) {
            if (GetFileAttributesW(pp) != INVALID_FILE_ATTRIBUTES) {
                g_splashImg = Image::FromFile(pp);
                if (g_splashImg && g_splashImg->GetLastStatus() == Ok) break;
                delete g_splashImg; g_splashImg = nullptr;
            }
        }

        // 状态复位
        g_splashStartTick = GetTickCount();
        g_stage = 0; g_realProgress = 0; g_animProgress = 0;
        g_stageFailed = false; g_timeoutShown = false; g_launchOk = false;
        g_splashStatus = L"初始化配置...";

        // 状态检测 + 超时保护：500ms 一次（横条已去除，无需动画重绘，占用极低）
        SetTimer(hwnd, 1, 500, nullptr);

        // 后台加载线程（真实五阶段：初始化配置→连接服务→检查更新→加载资源→启动主界面）
        if (g_hWorker) { CloseHandle(g_hWorker); g_hWorker = nullptr; }
        g_hWorker = CreateThread(nullptr, 0, SplashWorkerThread, hwnd, 0, nullptr);
        // 窗口显示后（消息队列处理时）按真实尺寸精确居中一次（DWM 调整后）
        PostMessageW(hwnd, WM_APP + 3, 0, 0);
        return 0;
    }
    case WM_APP + 3: { // 窗口已显示：按真实窗口尺寸在鼠标所在屏精确居中
        POINT pt; GetCursorPos(&pt);
        HMONITOR mon = MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST);
        MONITORINFO mi = { sizeof(mi) };
        GetMonitorInfoW(mon, &mi);
        int sw = mi.rcWork.right - mi.rcWork.left;
        int sh = mi.rcWork.bottom - mi.rcWork.top;
        RECT wr; GetWindowRect(hwnd, &wr);
        int rw = wr.right - wr.left, rh = wr.bottom - wr.top;
        SetWindowPos(hwnd, HWND_TOPMOST,
            mi.rcWork.left + (sw - rw) / 2, mi.rcWork.top + (sh - rh) / 2,
            0, 0, SWP_NOSIZE);
        return 0;
    }
    case WM_APP + 1: { // 后台线程：某阶段完成（wp=阶段号, lp=1成功/0失败）
        int stage = (int)wp;
        if (stage >= 0 && stage < 5) {
            g_stage = stage;
            const wchar_t* labels[] = { L"初始化配置", L"连接服务", L"检查更新", L"加载资源", L"启动主界面" };
            g_splashStatus = labels[stage];
            g_realProgress = (stage + 1) * 20;
            if (g_realProgress > 100) g_realProgress = 100;
        }
        InvalidateRect(hwnd, nullptr, FALSE);
        return 0;
    }
    case WM_APP + 2: { // 后台线程：全部完成（wp=1 主界面拉起成功）
        g_launchOk = (wp != 0);
        g_realProgress = 100;
        g_stage = 4;
        if (g_launchOk) {
            g_splashStatus = L"系统准备就绪，正在进入...";
        } else {
            g_stageFailed = true;
            g_splashStatus = L"启动主界面失败";
        }
        InvalidateRect(hwnd, nullptr, FALSE);
        return 0;
    }
    case WM_TIMER: {
        // 进度横条已去除：无动画推进，仅做超时保护 + 收尾检测（500ms 一次，占用极低）
        DWORD elapsed = GetTickCount() - g_splashStartTick;
        // 超时保护：10 秒未完成 → 显示 重试/退出/查看日志
        if (elapsed >= 10000 && g_realProgress < 100 && !g_timeoutShown) {
            g_timeoutShown = true;
            g_splashStatus = L"启动超时，请重试或查看日志";
            InvalidateRect(hwnd, nullptr, FALSE);
        }
        // 正常收尾：至少 2 秒 + 加载完成 + 主界面已拉起 + 启动音乐播完 → 进登录
        if (elapsed >= 2000 && g_realProgress >= 100 && g_launchOk && musicDone()) {
            stopStartupMusic();
            KillTimer(hwnd, 1);
            DestroyWindow(hwnd);
            PostQuitMessage(0); // 让 splash 消息循环退出，继续创建登录窗口
        }
        return 0;
    }
    case WM_LBUTTONUP: {
        // 仅当显示按钮时响应（超时未完成 或 拉起失败）
        bool showBtns = (g_timeoutShown && g_realProgress < 100) || (g_stageFailed && !g_launchOk);
        if (!showBtns) return 0;
        RECT rc; GetClientRect(hwnd, &rc);
        int bw = 120, bh = 40, gap = 16;
        int total = bw * 3 + gap * 2;
        int x0 = (rc.right - total) / 2, y0 = rc.bottom - 90;
        int mx = (short)LOWORD(lp), my = (short)HIWORD(lp);
        int btn = -1;
        for (int i = 0; i < 3; i++) {
            int bx = x0 + i * (bw + gap);
            if (mx >= bx && mx < bx + bw && my >= y0 && my < y0 + bh) { btn = i; break; }
        }
        if (btn == 0) { // 重试：重置状态并重启后台线程
            if (g_hWorker) {
                if (WaitForSingleObject(g_hWorker, 0) != WAIT_OBJECT_0) return 0; // 旧线程仍在跑，忽略
                CloseHandle(g_hWorker); g_hWorker = nullptr;
            }
            g_splashStartTick = GetTickCount();
            g_stage = 0; g_realProgress = 0; g_animProgress = 0;
            g_stageFailed = false; g_timeoutShown = false; g_launchOk = false;
            g_splashStatus = L"初始化配置...";
            g_hWorker = CreateThread(nullptr, 0, SplashWorkerThread, hwnd, 0, nullptr);
            InvalidateRect(hwnd, nullptr, FALSE);
        } else if (btn == 1) { // 退出：标记后销毁，不进登录
            g_abortExit = true;
            KillTimer(hwnd, 1);
            DestroyWindow(hwnd);
            PostQuitMessage(0);
        } else if (btn == 2) { // 查看日志：用记事本打开（不弹 cmd）
            std::wstring root = GetAppRoot();
            std::wstring logPath = root + L"\\frontend_startup.log";
            ShellExecuteW(nullptr, L"open", L"notepad.exe", logPath.c_str(), nullptr, SW_SHOWNORMAL);
        }
        return 0;
    }
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);
        RECT rc; GetClientRect(hwnd, &rc);
        {
            Graphics g(hdc);
            g.SetSmoothingMode(SmoothingModeAntiAlias);
            g.SetInterpolationMode(InterpolationModeHighQualityBicubic);

            // 背景：缓存的图1（无图则渐变兜底）
            if (g_splashImg) {
                DrawImageCover(g, g_splashImg, 0, 0, rc.right, rc.bottom);
            } else {
                LinearGradientBrush bgBrush(Point(0, 0), Point(0, rc.bottom),
                    Color(255, 26, 38, 60), Color(255, 10, 14, 26));
                g.FillRectangle(&bgBrush, 0, 0, rc.right, rc.bottom);
                FontFamily ff0(L"微软雅黑");
                StringFormat sf0;
                sf0.SetAlignment(StringAlignmentCenter);
                Font errF0(&ff0, 13, FontStyleBold, UnitPixel);
                SolidBrush errC0(Color(255, 229, 72, 77));
                RectF er0(0, 240, (REAL)rc.right, 24);
                g.DrawString(L"背景图加载失败（images\\startup.png 缺失）", -1, &errF0, er0, &sf0, &errC0);
            }

            // 底部深蓝渐变遮罩（保证文字清晰）
            LinearGradientBrush mask(Point(0, rc.bottom - 190), Point(0, rc.bottom),
                Color(0, 10, 24, 46), Color(235, 8, 18, 36));
            g.FillRectangle(&mask, 0, rc.bottom - 190, rc.right, 190);

            // 字体：优先 Noto Sans SC（思源黑体），系统缺失时回退微软雅黑
            FontFamily ffNoto(L"Noto Sans SC");
            FontFamily ffYh(L"微软雅黑");
            FontFamily* ff = (ffNoto.GetLastStatus() == Ok) ? &ffNoto : &ffYh;
            StringFormat sf;
            sf.SetAlignment(StringAlignmentCenter);

            // 顶部系统名（居中点缀）
            Font topFont(ff, 12, FontStyleBold, UnitPixel);
            SolidBrush topC(Color(255, 205, 230, 255));
            RectF topRect(0, 26, (REAL)rc.right, 20);
            g.DrawString(L"旅客服务智能管理广播系统", -1, &topFont, topRect, &sf, &topC);

            // 主标题
            Font titleFont(ff, 30, FontStyleBold, UnitPixel);
            SolidBrush white(Color(255, 255, 255, 255));
            RectF titleRect(0, rc.bottom - 130, (REAL)rc.right, 44);
            g.DrawString(L"旅客服务系统智能管理广播平台", -1, &titleFont, titleRect, &sf, &white);

            // 版本号（14px 加粗提亮，提升可读性）
            Font verFont(ff, 14, FontStyleBold, UnitPixel);
            SolidBrush gray(Color(255, 210, 225, 245));
            RectF verRect(0, rc.bottom - 86, (REAL)rc.right, 22);
            g.DrawString(L"V26.10.2", -1, &verFont, verRect, &sf, &gray);

            // 状态文字（当前阶段；空时显示默认）——进度横条已去除，状态文字置于底部
            Font hintFont(ff, 11, FontStyleRegular, UnitPixel);
            SolidBrush lightGray(Color(255, 225, 235, 250));
            RectF hintRect(0, rc.bottom - 40, (REAL)rc.right, 18);
            const wchar_t* st = g_splashStatus.empty() ? L"系统正在启动中，请稍候..." : g_splashStatus.c_str();
            g.DrawString(st, -1, &hintFont, hintRect, &sf, &lightGray);

            // 拉起失败提示（红色，明确原因）
            if (g_stageFailed && !g_launchOk) {
                Font errFont(ff, 12, FontStyleBold, UnitPixel);
                SolidBrush errC(Color(255, 229, 72, 77));
                RectF errRect(0, rc.bottom - 74, (REAL)rc.right, 22);
                g.DrawString(L"启动主界面失败，请点击下方按钮重试或查看日志", -1, &errFont, errRect, &sf, &errC);
            }

            // 超时/失败时显示 重试 / 退出 / 查看日志
            bool showBtns = (g_timeoutShown && g_realProgress < 100) || (g_stageFailed && !g_launchOk);
            if (showBtns) {
                int bw = 120, bh = 40, gap = 16;
                int total = bw * 3 + gap * 2;
                int x0 = (rc.right - total) / 2, y0 = rc.bottom - 92;
                const wchar_t* labels[3] = { L"重试", L"退出", L"查看日志" };
                Font bf(ff, 13, FontStyleBold, UnitPixel);
                SolidBrush btnText(Color(255, 255, 255, 255));
                for (int i = 0; i < 3; i++) {
                    int bx = x0 + i * (bw + gap);
                    SolidBrush btnBg(Color(235, 15, 32, 56));
                    GdiFillRoundRect(g, RectF((REAL)bx, (REAL)y0, (REAL)bw, (REAL)bh), 10, btnBg);
                    RectF bRect((REAL)bx, (REAL)y0, (REAL)bw, (REAL)bh);
                    g.DrawString(labels[i], -1, &bf, bRect, &sf, &btnText);
                }
            }
        }
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_ERASEBKGND: return 1;
    case WM_DESTROY: {
        if (g_splashImg) { delete g_splashImg; g_splashImg = nullptr; }
        if (g_hWorker) { CloseHandle(g_hWorker); g_hWorker = nullptr; }
        KillTimer(hwnd, 1);
        return 0;
    }
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

// ============================================================
// 登录窗口
// ============================================================
// g_hLogin / g_loggedIn 已在文件前部统一定义


// 深色风格配色（原创青蓝系）
#define LOGIN_BG_RIGHT    RGB(13, 26, 48)    // 卡片深蓝
#define LOGIN_BG_LEFT     RGB(9, 18, 36)     // 备用深蓝
#define LOGIN_EDIT_BG     RGB(8, 20, 40)     // 输入框深蓝
#define LOGIN_TEXT        RGB(225, 232, 242) // 浅色文字
#define LOGIN_TEXT_DIM    RGB(150, 165, 190) // 次要文字
#define LOGIN_BTN_BLUE    RGB(0, 130, 175)   // 登录按钮青蓝
#define LOGIN_BTN_GRAY    RGB(52, 66, 92)    // 退出按钮灰蓝
#define LOGIN_BTN_BLUE_HI RGB(25, 160, 205)  // 悬停青蓝
#define LOGIN_BTN_GRAY_HI RGB(72, 90, 120)   // 悬停灰蓝

static HBRUSH g_hLoginBg = nullptr;
static HBRUSH g_hLoginLeftBg = nullptr;
static HBRUSH g_hLoginEditBg = nullptr;
static HFONT g_fLoginBtn = nullptr;
static bool g_btnHover[3] = {false, false, false}; // 登录/退出/注册

// 自绘圆角按钮
static void DrawLoginButton(LPDRAWITEMSTRUCT dis, COLORREF bg, COLORREF bgHover, const wchar_t* text) {
    HDC hdc = dis->hDC;
    RECT rc = dis->rcItem;
    bool hover = (dis->itemState & ODS_SELECTED) != 0;

    // 先用窗口背景色填充整个按钮区域（盖住默认白色边框/焦点框）
    HBRUSH bgBr = CreateSolidBrush(LOGIN_BG_RIGHT);
    FillRect(hdc, &rc, bgBr);
    DeleteObject(bgBr);

    // 圆角路径
    HRGN rgn = CreateRoundRectRgn(rc.left, rc.top, rc.right + 1, rc.bottom + 1, 8, 8);
    SelectClipRgn(hdc, rgn);

    // 背景
    COLORREF c = hover ? bgHover : bg;
    HBRUSH br = CreateSolidBrush(c);
    FillRect(hdc, &rc, br);
    DeleteObject(br);

    // 边框
    HPEN pen = CreatePen(PS_SOLID, 1, RGB(30, 50, 90));
    HPEN oldPen = (HPEN)SelectObject(hdc, pen);
    HBRUSH oldBr = (HBRUSH)SelectObject(hdc, GetStockObject(NULL_BRUSH));
    RoundRect(hdc, rc.left, rc.top, rc.right, rc.bottom, 8, 8);
    SelectObject(hdc, oldPen);
    SelectObject(hdc, oldBr);
    DeleteObject(pen);

    // 文字
    SetBkMode(hdc, TRANSPARENT);
    SetTextColor(hdc, RGB(255, 255, 255));
    if (g_fLoginBtn) SelectObject(hdc, g_fLoginBtn);
    DrawTextW(hdc, const_cast<LPWSTR>(text), -1, &rc, DT_CENTER | DT_VCENTER | DT_SINGLELINE);

    SelectClipRgn(hdc, nullptr);
    DeleteObject(rgn);
}

static LRESULT CALLBACK LoginProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        g_hLogin = hwnd;
        g_hLoginBg = CreateSolidBrush(LOGIN_BG_RIGHT);
        g_hLoginLeftBg = CreateSolidBrush(LOGIN_BG_LEFT);
        g_hLoginEditBg = CreateSolidBrush(LOGIN_EDIT_BG);

        HFONT fTitle = CreateFontW(20, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");
        HFONT fLabel = CreateFontW(13, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");
        HFONT fEdit = CreateFontW(14, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");
        g_fLoginBtn = CreateFontW(14, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");
        HFONT fSmall = CreateFontW(11, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            GB2312_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"微软雅黑");

        // 中央卡片内：标题（卡片顶部）
        HWND tCard = CreateWindowExW(0, L"STATIC", L"旅客服务智能管理广播系统",
            WS_CHILD|WS_VISIBLE|SS_CENTER, 290, 90, 420, 30, hwnd, nullptr, nullptr, nullptr);
        SendMessageW(tCard, WM_SETFONT, (WPARAM)fTitle, TRUE);

        // 副标题（统一身份认证）
        HWND t = CreateWindowExW(0, L"STATIC", L"统一身份认证",
            WS_CHILD|WS_VISIBLE|SS_CENTER, 290, 128, 420, 26, hwnd, nullptr, nullptr, nullptr);
        SendMessageW(t, WM_SETFONT, (WPARAM)fLabel, TRUE);

        // 账号
        CreateWindowExW(0, L"STATIC", L"登录账号", WS_CHILD|WS_VISIBLE, 330, 192, 100, 20, hwnd, nullptr, nullptr, nullptr);
        HWND u = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL, 330, 216, 340, 30, hwnd, (HMENU)IDC_USER, nullptr, nullptr);
        SendMessageW(u, WM_SETFONT, (WPARAM)fEdit, TRUE);

        // 密码
        CreateWindowExW(0, L"STATIC", L"登录密码", WS_CHILD|WS_VISIBLE, 330, 258, 100, 20, hwnd, nullptr, nullptr, nullptr);
        HWND p = CreateWindowExW(WS_EX_CLIENTEDGE, L"EDIT", L"", WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL|ES_PASSWORD, 330, 282, 340, 30, hwnd, (HMENU)IDC_PWD, nullptr, nullptr);
        SendMessageW(p, WM_SETFONT, (WPARAM)fEdit, TRUE);

        // 选项
        CreateWindowExW(0, L"BUTTON", L"记住账号", WS_CHILD|WS_VISIBLE|BS_AUTOCHECKBOX, 330, 326, 90, 22, hwnd, (HMENU)IDC_CHK_REMEMBER_USER, nullptr, nullptr);
        SendMessageW(GetDlgItem(hwnd, IDC_CHK_REMEMBER_USER), WM_SETFONT, (WPARAM)fSmall, TRUE);
        CreateWindowExW(0, L"BUTTON", L"记住密码", WS_CHILD|WS_VISIBLE|BS_AUTOCHECKBOX, 425, 326, 90, 22, hwnd, (HMENU)IDC_CHK_REMEMBER_PWD, nullptr, nullptr);
        SendMessageW(GetDlgItem(hwnd, IDC_CHK_REMEMBER_PWD), WM_SETFONT, (WPARAM)fSmall, TRUE);
        HWND link = CreateWindowExW(0, L"STATIC", L"注册账号", WS_CHILD|WS_VISIBLE|SS_NOTIFY, 585, 326, 70, 22, hwnd, (HMENU)IDC_LINK_REG, nullptr, nullptr);
        SendMessageW(link, WM_SETFONT, (WPARAM)fSmall, TRUE);

        // 自绘按钮
        CreateWindowExW(0, L"BUTTON", L"登  录", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 330, 368, 340, 42, hwnd, (HMENU)IDC_BTN_LOGIN, nullptr, nullptr);
        CreateWindowExW(0, L"BUTTON", L"退  出", WS_CHILD|WS_VISIBLE|BS_OWNERDRAW, 330, 422, 340, 38, hwnd, (HMENU)IDC_BTN_EXIT, nullptr, nullptr);

        CreateWindowExW(0, L"STATIC", L"V26.10.2", WS_CHILD|WS_VISIBLE|SS_RIGHT, 855, 584, 130, 18, hwnd, nullptr, nullptr, nullptr);

        // 读取配置文件：记住账号/密码
        {
            std::wstring cfg = GetAppRoot() + L"\\config.ini";
            wchar_t userBuf[128] = {0}, pwdBuf[128] = {0};
            DWORD ru = GetPrivateProfileStringW(L"login", L"username", L"", userBuf, 128, cfg.c_str());
            DWORD rp = GetPrivateProfileStringW(L"login", L"password", L"", pwdBuf, 128, cfg.c_str());
            BOOL rememberUser = GetPrivateProfileIntW(L"login", L"remember_user", 0, cfg.c_str());
            BOOL rememberPwd = GetPrivateProfileIntW(L"login", L"remember_pwd", 0, cfg.c_str());
            if (rememberUser) {
                SetDlgItemTextW(hwnd, IDC_USER, userBuf);
                SendMessageW(GetDlgItem(hwnd, IDC_CHK_REMEMBER_USER), BM_SETCHECK, BST_CHECKED, 0);
            }
            if (rememberPwd && rp > 0) {
                SetDlgItemTextW(hwnd, IDC_PWD, pwdBuf);
                SendMessageW(GetDlgItem(hwnd, IDC_CHK_REMEMBER_PWD), BM_SETCHECK, BST_CHECKED, 0);
            }
        }

        disableCloseButton(hwnd);
        return 0;
    }
    case WM_ERASEBKGND: {
        return 1; // 背景全部由 WM_PAINT 绘制（图片+遮罩+卡片），避免闪烁
    }
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);
        {
            Graphics g(hdc);
            g.SetSmoothingMode(SmoothingModeAntiAlias);
            g.SetInterpolationMode(InterpolationModeHighQualityBicubic);
            RECT rc; GetClientRect(hwnd, &rc);

            // 背景：免版权铁路照片（全幅居中裁切铺满）
            std::wstring root = GetAppRoot();
            std::wstring i1 = root + L"\\images\\startup2.png";
            std::wstring i2 = root + L"\\images\\startup2.jpg";
            Image* img = nullptr;
            const wchar_t* paths[] = { i1.c_str(), i2.c_str(), L"images\\startup2.png", L"images\\startup2.jpg" };
            for (auto pp : paths) {
                if (GetFileAttributesW(pp) != INVALID_FILE_ATTRIBUTES) {
                    img = Image::FromFile(pp);
                    if (img && img->GetLastStatus() == Ok) break;
                    delete img; img = nullptr;
                }
            }
            if (img) {
                DrawImageCover(g, img, 0, 0, rc.right, rc.bottom);
                delete img;
            } else {
                LinearGradientBrush bgBrush(Point(0, 0), Point(0, rc.bottom),
                    Color(255, 20, 30, 52), Color(255, 8, 12, 24));
                g.FillRectangle(&bgBrush, 0, 0, rc.right, rc.bottom);
            }

            // 全窗深色遮罩（突出中央卡片）
            SolidBrush veil(Color(150, 6, 12, 26));
            g.FillRectangle(&veil, 0, 0, rc.right, rc.bottom);

            // 中央圆角卡片（深蓝半透明）
            SolidBrush card(Color(232, 13, 26, 48));
            RectF cardRc(290, 75, 420, 470);
            GdiFillRoundRect(g, cardRc, 18, card);
            // 卡片顶部青蓝饰条（原创点缀）
            SolidBrush accent(Color(255, 35, 190, 235));
            GdiFillRoundRect(g, RectF(290 + 165, 75 + 22, 90, 4), 2, accent);
        }
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_DRAWITEM: {
        LPDRAWITEMSTRUCT dis = (LPDRAWITEMSTRUCT)lp;
        if (dis->CtlID == IDC_BTN_LOGIN) {
            DrawLoginButton(dis, LOGIN_BTN_BLUE, LOGIN_BTN_BLUE_HI, L"登  录");
            return TRUE;
        } else if (dis->CtlID == IDC_BTN_EXIT) {
            DrawLoginButton(dis, LOGIN_BTN_GRAY, LOGIN_BTN_GRAY_HI, L"退  出");
            return TRUE;
        }
        break;
    }
    case WM_CTLCOLORSTATIC: {
        HDC hdc = (HDC)wp;
        SetTextColor(hdc, LOGIN_TEXT);
        SetBkMode(hdc, TRANSPARENT);
        return (LRESULT)GetStockObject(HOLLOW_BRUSH); // 透明背景，露出卡片/背景
    }
    case WM_CTLCOLOREDIT: {
        HDC hdc = (HDC)wp;
        SetTextColor(hdc, RGB(240, 248, 255));
        SetBkColor(hdc, LOGIN_EDIT_BG);
        return (LRESULT)g_hLoginEditBg;
    }
    case WM_COMMAND: {
        int id = LOWORD(wp);
        if (id == IDC_BTN_LOGIN || id == IDOK) {
            std::wstring u = getEditW(hwnd, IDC_USER);
            std::wstring p = getEditW(hwnd, IDC_PWD);
            if (u.empty() || p.empty()) { customMessageBoxW(hwnd, L"请输入账号和密码", L"提示", MB_OK); break; }
            std::wstring sen = L"{\"Login\":{\"username\":\"" + u + L"\",\"password\":\"" + p + L"\"}}";
            Resp r = callServer(wideToUtf8(sen));
            if (r.ok) {
                g_loggedIn = true;
                // 保存记住账号/密码
                {
                    std::wstring cfg = GetAppRoot() + L"\\config.ini";
                    BOOL ru = SendMessageW(GetDlgItem(hwnd, IDC_CHK_REMEMBER_USER), BM_GETCHECK, 0, 0) == BST_CHECKED;
                    BOOL rp = SendMessageW(GetDlgItem(hwnd, IDC_CHK_REMEMBER_PWD), BM_GETCHECK, 0, 0) == BST_CHECKED;
                    WritePrivateProfileStringW(L"login", L"remember_user", ru ? L"1" : L"0", cfg.c_str());
                    WritePrivateProfileStringW(L"login", L"remember_pwd", rp ? L"1" : L"0", cfg.c_str());
                    if (ru) WritePrivateProfileStringW(L"login", L"username", u.c_str(), cfg.c_str());
                    if (rp) WritePrivateProfileStringW(L"login", L"password", p.c_str(), cfg.c_str());
                }
                ShowMainWindow();
            } else {
                customMessageBoxW(hwnd, r.msg.c_str(), L"登录失败", MB_OK);
            }
        } else if (id == IDC_BTN_REG || id == IDC_LINK_REG) {
            std::wstring u = getEditW(hwnd, IDC_USER);
            std::wstring p = getEditW(hwnd, IDC_PWD);
            if (u.empty() || p.empty()) { customMessageBoxW(hwnd, L"请先输入要注册的账号和密码", L"提示", MB_OK); break; }
            std::wstring sen = L"{\"Register\":{\"username\":\"" + u + L"\",\"password\":\"" + p + L"\"}}";
            Resp r = callServer(wideToUtf8(sen));
            if (r.ok) customMessageBoxW(hwnd, L"注册成功，请点登录", L"成功", MB_OK);
            else customMessageBoxW(hwnd, r.msg.c_str(), L"注册失败", MB_OK);
        } else if (id == IDC_BTN_EXIT) {
            if (customMessageBoxW(hwnd, L"确定退出系统？", L"确认", MB_YESNO) == IDOK) {
                DestroyWindow(hwnd);
                PostQuitMessage(0);
            }
        }
        return 0;
    }
    case WM_CLOSE: return 0;
    case WM_DESTROY:
        if (g_hLoginBg) DeleteObject(g_hLoginBg);
        if (g_hLoginLeftBg) DeleteObject(g_hLoginLeftBg);
        if (g_hLoginEditBg) DeleteObject(g_hLoginEditBg);
        if (g_fLoginBtn) DeleteObject(g_fLoginBtn);
        g_hLogin = nullptr;
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

// ============================================================
// WinMain
// ============================================================
// 自定义开机音乐：优先 audio/startup.wav / startup.mp3，找不到则用系统音
static void playStartupSound() {
    std::wstring root = GetAppRoot();
    std::wstring p1 = root + L"\\audio\\startup.wav";
    std::wstring p2 = root + L"\\audio\\startup.mp3";
    std::wstring p3 = L"audio\\startup.wav";
    std::wstring p4 = L"audio\\startup.mp3";
    const wchar_t* files[] = { p1.c_str(), p2.c_str(), p3.c_str(), p4.c_str() };
    for (auto p : files) {
        if (GetFileAttributesW(p) != INVALID_FILE_ATTRIBUTES) {
            wchar_t cmd[512];
            swprintf(cmd, 512, L"open \"%s\" alias startupmusic", p);
            if (mciSendStringW(cmd, nullptr, 0, nullptr) == 0) {
                // 查询总时长
                wchar_t lenBuf[64] = {0};
                mciSendStringW(L"status startupmusic length", lenBuf, 64, nullptr);
                g_musicLengthMs = _wtoi(lenBuf);
                g_musicOpen = true;
                mciSendStringW(L"play startupmusic from 0", nullptr, 0, nullptr);
                return;
            }
        }
    }
    g_musicOpen = false;
    PlaySoundW(L"SystemAsterisk", nullptr, SND_ALIAS | SND_ASYNC);
}

// 检查音乐是否播放完成（无自定义音乐时返回 true）
static bool musicDone() {
    if (!g_musicOpen) return true;
    wchar_t posBuf[64] = {0};
    mciSendStringW(L"status startupmusic position", posBuf, 64, nullptr);
    DWORD pos = _wtoi(posBuf);
    return pos >= g_musicLengthMs;
}
static void stopStartupMusic() {
    if (g_musicOpen) {
        mciSendStringW(L"stop startupmusic", nullptr, 0, nullptr);
        mciSendStringW(L"close startupmusic", nullptr, 0, nullptr);
        g_musicOpen = false;
    } else {
        PlaySoundW(nullptr, nullptr, 0);
    }
}

// 探测主界面(main_ui.exe)是否已在运行：尝试连接其单实例端口 27890
bool mainUiRunning() {
    SOCKET s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (s == INVALID_SOCKET) return false;
    sockaddr_in addr = {};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(27890);
    addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    // 非阻塞 connect，避免卡住
    u_long mode = 1;
    ioctlsocket(s, FIONBIO, &mode);
    int r = connect(s, (sockaddr*)&addr, sizeof(addr));
    if (r == 0) { closesocket(s); return true; }
    fd_set w;
    FD_ZERO(&w);
    FD_SET(s, &w);
    timeval tv = {0, 300000};  // 300ms 超时
    int sel = select(0, nullptr, &w, nullptr, &tv);
    closesocket(s);
    return sel == 1;  // 可写 = 连接成功 = main_ui 在运行
}

// 给窗口应用应用图标（任务栏 / Alt-Tab / 窗口标题栏），使用 exe 内嵌资源
static void ApplyAppIcon(HWND hwnd) {
    if (!hwnd) return;
    HICON hIcon = (HICON)LoadImageW(GetModuleHandleW(nullptr),
        MAKEINTRESOURCEW(IDI_ICON1), IMAGE_ICON, 0, 0, LR_SHARED | LR_DEFAULTSIZE);
    if (hIcon) {
        SendMessageW(hwnd, WM_SETICON, ICON_BIG, (LPARAM)hIcon);
        SendMessageW(hwnd, WM_SETICON, ICON_SMALL, (LPARAM)hIcon);
    }
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, LPWSTR, int nCmd) {
    // ===== DPI 感知：任何窗口创建前开启，保证高缩放下文字清晰、坐标正确 =====
    SetProcessDPIAware();
    // ===== AppUserModelID：让任务栏/Alt-Tab 使用本程序独立图标组（不归入 Python/默认组） =====
    SetCurrentProcessExplicitAppUserModelID(L"PassengerBroadcast.System.Frontend.v26102");

    // ===== 单实例锁：只允许一个进程运行，重复启动会被拦截 =====
    HANDLE hSingle = CreateMutexW(nullptr, TRUE, L"Local\\PassengerBroadcastSys_SingleInstance");
    if (hSingle && GetLastError() == ERROR_ALREADY_EXISTS) {
        MessageBoxW(nullptr, L"程序已经在运行中，请勿重复启动。", L"旅客服务智能管理广播系统",
                    MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND);
        return 0;
    }
    // 启动声音（可自定义）
    playStartupSound();

    // GDI+ 初始化（用于启动画面图片）
    GdiplusStartupInput gdiInput;
    GdiplusStartup(&g_gdiToken, &gdiInput, nullptr);

    InitCommonControls();
    WSAData wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);

    // ===== 全链路单实例：主界面(main_ui)已在运行 → 也拦截 =====
    if (mainUiRunning()) {
        MessageBoxW(nullptr, L"程序已经在运行中，请勿重复启动。", L"旅客服务智能管理广播系统",
                    MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND);
        WSACleanup();
        return 0;
    }

    // 注册启动画面类
    WNDCLASSW sc = {0};
    sc.lpfnWndProc = SplashProc;
    sc.hInstance = hInst;
    sc.hIcon = (HICON)LoadImageW(hInst, MAKEINTRESOURCEW(IDI_ICON1), IMAGE_ICON, 0, 0, LR_SHARED | LR_DEFAULTSIZE);
    sc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    sc.hbrBackground = nullptr;
    sc.lpszClassName = L"SplashWin";
    RegisterClassW(&sc);

    // 启动画面消息循环（后台线程负责真实加载，UI 不卡）
    {
        HWND splash = CreateWindowExW(0, L"SplashWin", L"",
            WS_POPUP, 0, 0, 960, 540, nullptr, nullptr, hInst, nullptr);
        g_hSplash = splash;
        ApplyAppIcon(splash);
        ShowWindow(splash, SW_SHOW);
        UpdateWindow(splash);
        MSG sm;
        while (GetMessageW(&sm, nullptr, 0, 0)) {
            if (!IsWindow(splash)) break;
            TranslateMessage(&sm);
            DispatchMessageW(&sm);
        }
    }

    // 用户在启动界面点了"退出" → 不进登录，直接清理退出
    if (g_abortExit) {
        tcpClose();
        WSACleanup();
        GdiplusShutdown(g_gdiToken);
        return 0;
    }

    // 注册登录窗口类（只注册一次）
    WNDCLASSW lc = {0};
    lc.lpfnWndProc = LoginProc;
    lc.hInstance = hInst;
    lc.hIcon = (HICON)LoadImageW(hInst, MAKEINTRESOURCEW(IDI_ICON1), IMAGE_ICON, 0, 0, LR_SHARED | LR_DEFAULTSIZE);
    lc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    lc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    lc.lpszClassName = L"LoginWin";
    if (!GetClassInfoW(hInst, L"LoginWin", &lc)) {
        RegisterClassW(&lc);
    }

    // 注册主窗口类（只注册一次）
    WNDCLASSW mc = {0};
    mc.lpfnWndProc = MainProc;
    mc.hInstance = hInst;
    mc.hIcon = (HICON)LoadImageW(hInst, MAKEINTRESOURCEW(IDI_ICON1), IMAGE_ICON, 0, 0, LR_SHARED | LR_DEFAULTSIZE);
    mc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    mc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    mc.lpszClassName = L"MainWin";
    if (!GetClassInfoW(hInst, L"MainWin", &mc)) {
        RegisterClassW(&mc);
    }

    int ret = 0;
    MSG msg;

    g_loggedIn = false;
    g_isLogout = false;

    HWND login = CreateWindowExW(0, L"LoginWin", L"",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        0, 0, 1000, 620, nullptr, nullptr, hInst, nullptr);
    ApplyAppIcon(login);
    g_hLogin = login;
    {
        int sw = GetSystemMetrics(SM_CXSCREEN);
        int sh = GetSystemMetrics(SM_CYSCREEN);
        SetWindowPos(login, nullptr, (sw - 1000) / 2, (sh - 620) / 2, 0, 0, SWP_NOSIZE | SWP_NOZORDER);
    }

    HWND main = CreateWindowExW(0, L"MainWin", L"旅客服务智能管理广播系统",
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
