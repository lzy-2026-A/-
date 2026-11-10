// 旅客服务智能管理广播平台 - C++ 启动器
// 重新设计：无边框启动画面 → 品牌分栏登录页 → 拉起 Python 主界面
// 不依赖后端即可登录并进入主界面。

#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define WINVER 0x0A00
#define _WIN32_WINNT 0x0A00

#include <windows.h>
#include <windowsx.h>
#include <ole2.h>
#include <commctrl.h>
#include <shellapi.h>
#include <shobjidl.h>
#include <dwmapi.h>
#include <gdiplus.h>

#include <string>
#include <vector>
#include <ctime>
#include <cwchar>

using namespace Gdiplus;

// ============================================================
// 常量 / 全局状态
// ============================================================
static const wchar_t* kSplashClass = L"PSB_CppSplash_2026";
static const wchar_t* kLoginClass  = L"PSB_CppLogin_2026";
static const wchar_t* kMainTitle   = L"旅客服务智能管理广播系统";

enum ControlId {
    IDC_USER = 1001,
    IDC_PWD = 1002,
    IDC_LOGIN = 1003,
    IDC_EXIT = 1004,
    IDC_REMEMBER = 1005,
    IDC_CAPTCHA = 1006
};

static HINSTANCE g_inst = nullptr;
static ULONG_PTR g_gdiToken = 0;
static HWND g_hLogin = nullptr;
static HWND g_hSplash = nullptr;
static int g_dpi = 96;
static float g_scale = 1.0f;

static bool g_loggedIn = false;
static bool g_launching = false;
static bool g_remember = false;
static bool g_splashSkipped = false;
static ULONGLONG g_splashStart = 0;

static std::wstring g_captcha;
static std::wstring g_status = L"请输入账号、密码和验证码";
static int g_statusKind = 0;   // 0=提示 1=错误 2=成功

static RECT g_captchaRect = {0, 0, 0, 0};
static RECT g_captchaHintRect = {0, 0, 0, 0};
static RECT g_skipRect = {0, 0, 0, 0};

static Font* g_fBadge = nullptr;
static Font* g_fSplashTitle = nullptr;
static Font* g_fSplashSub = nullptr;
static Font* g_fSplashStatus = nullptr;
static Font* g_fSplashSmall = nullptr;
static Font* g_fFormTitle = nullptr;
static Font* g_fFormSub = nullptr;
static Font* g_fLabel = nullptr;
static Font* g_fSmall = nullptr;
static Font* g_fTiny = nullptr;
static Font* g_fCaptcha = nullptr;
static Font* g_fButton = nullptr;
static Font* g_fCheck = nullptr;

static HFONT g_hFontEdit = nullptr;
static HBRUSH g_hWhiteBrush = nullptr;
static HBRUSH g_hFormBrush = nullptr;

static int S(int v) {
    int r = (int)(v * g_scale + 0.5f);
    return r < 0 ? 0 : r;
}

static REAL SR(int v) { return (REAL)S(v); }

// ============================================================
// 路径 / 文件
// ============================================================
static bool FileExists(const std::wstring& path) {
    DWORD attr = GetFileAttributesW(path.c_str());
    return attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY);
}

static std::wstring GetAppRoot() {
    wchar_t exePath[MAX_PATH] = {0};
    GetModuleFileNameW(nullptr, exePath, MAX_PATH);
    std::wstring dir(exePath);
    size_t slash = dir.find_last_of(L"\\/");
    if (slash != std::wstring::npos) dir = dir.substr(0, slash);

    std::wstring up = dir + L"\\..";
    wchar_t fullUp[MAX_PATH] = {0};
    if (GetFullPathNameW(up.c_str(), MAX_PATH, fullUp, nullptr) &&
        FileExists(std::wstring(fullUp) + L"\\dist\\main_ui\\main_ui.exe")) {
        return std::wstring(fullUp);
    }
    if (FileExists(dir + L"\\dist\\main_ui\\main_ui.exe")) return dir;
    return dir;
}

static std::wstring ConfigPath() {
    return GetAppRoot() + L"\\config.ini";
}

// ============================================================
// 绘图工具
// ============================================================
static void InitDpiAndScale() {
    typedef BOOL(WINAPI* SetDpiCtxFn)(DPI_AWARENESS_CONTEXT);
    SetDpiCtxFn setCtx = (SetDpiCtxFn)GetProcAddress(
        GetModuleHandleW(L"user32.dll"), "SetProcessDpiAwarenessContext");
    if (setCtx) setCtx((DPI_AWARENESS_CONTEXT)-4);

    HDC dc = GetDC(nullptr);
    g_dpi = dc ? GetDeviceCaps(dc, LOGPIXELSX) : 96;
    if (dc) ReleaseDC(nullptr, dc);
    if (g_dpi <= 0) g_dpi = 96;

    RECT work = {0, 0, 1536, 864};
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work, 0);
    float workW = (float)(work.right - work.left);
    float workH = (float)(work.bottom - work.top);
    float dpiScale = (float)g_dpi / 96.0f;
    float fitW = (workW - 70.0f) / 900.0f;
    float fitH = (workH - 60.0f) / 560.0f;
    g_scale = std::min(dpiScale, std::min(fitW, fitH));
    if (g_scale < 0.80f) g_scale = 0.80f;
    if (g_scale > 1.85f) g_scale = 1.85f;
}

static void InitFonts() {
    FontFamily family(L"Microsoft YaHei UI");
    if (!family.IsAvailable()) {
        FontFamily alt(L"Microsoft YaHei");
        if (alt.IsAvailable()) {
            // 构造新家族并复制（FontFamily 不可赋值）
            FontFamily* p = new FontFamily(L"Microsoft YaHei");
            g_fBadge = new Font(p, (REAL)S(34), FontStyleBold, UnitPixel);
            g_fSplashTitle = new Font(p, (REAL)S(28), FontStyleBold, UnitPixel);
            g_fSplashSub = new Font(p, (REAL)S(10), FontStyleRegular, UnitPixel);
            g_fSplashStatus = new Font(p, (REAL)S(11), FontStyleRegular, UnitPixel);
            g_fSplashSmall = new Font(p, (REAL)S(9), FontStyleRegular, UnitPixel);
            g_fFormTitle = new Font(p, (REAL)S(25), FontStyleBold, UnitPixel);
            g_fFormSub = new Font(p, (REAL)S(11), FontStyleRegular, UnitPixel);
            g_fLabel = new Font(p, (REAL)S(11), FontStyleRegular, UnitPixel);
            g_fSmall = new Font(p, (REAL)S(10), FontStyleRegular, UnitPixel);
            g_fTiny = new Font(p, (REAL)S(9), FontStyleRegular, UnitPixel);
            g_fCaptcha = new Font(p, (REAL)S(22), FontStyleBold | FontStyleItalic, UnitPixel);
            g_fButton = new Font(p, (REAL)S(14), FontStyleBold, UnitPixel);
            g_fCheck = new Font(p, (REAL)S(11), FontStyleRegular, UnitPixel);
            delete p;
        }
    }
    if (!g_fBadge) {
        g_fBadge = new Font(&family, (REAL)S(34), FontStyleBold, UnitPixel);
        g_fSplashTitle = new Font(&family, (REAL)S(28), FontStyleBold, UnitPixel);
        g_fSplashSub = new Font(&family, (REAL)S(10), FontStyleRegular, UnitPixel);
        g_fSplashStatus = new Font(&family, (REAL)S(11), FontStyleRegular, UnitPixel);
        g_fSplashSmall = new Font(&family, (REAL)S(9), FontStyleRegular, UnitPixel);
        g_fFormTitle = new Font(&family, (REAL)S(25), FontStyleBold, UnitPixel);
        g_fFormSub = new Font(&family, (REAL)S(11), FontStyleRegular, UnitPixel);
        g_fLabel = new Font(&family, (REAL)S(11), FontStyleRegular, UnitPixel);
        g_fSmall = new Font(&family, (REAL)S(10), FontStyleRegular, UnitPixel);
        g_fTiny = new Font(&family, (REAL)S(9), FontStyleRegular, UnitPixel);
        g_fCaptcha = new Font(&family, (REAL)S(22), FontStyleBold | FontStyleItalic, UnitPixel);
        g_fButton = new Font(&family, (REAL)S(14), FontStyleBold, UnitPixel);
        g_fCheck = new Font(&family, (REAL)S(11), FontStyleRegular, UnitPixel);
    }

    g_hFontEdit = CreateFontW(-S(14), 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
        DEFAULT_PITCH | FF_DONTCARE, L"Microsoft YaHei UI");
    g_hWhiteBrush = CreateSolidBrush(RGB(255, 255, 255));
    g_hFormBrush = CreateSolidBrush(RGB(248, 250, 253));
}

static void DrawTextG(Graphics& g, const std::wstring& text, Font* font, Color color,
                      RectF rc, StringAlignment align = StringAlignmentNear,
                      StringAlignment line = StringAlignmentCenter, bool wrap = false) {
    if (!font) return;
    StringFormat fmt;
    fmt.SetAlignment(align);
    fmt.SetLineAlignment(line);
    if (!wrap) fmt.SetFormatFlags(StringFormatFlagsNoWrap);
    fmt.SetTrimming(StringTrimmingEllipsisCharacter);
    SolidBrush brush(color);
    g.DrawString(text.c_str(), -1, font, rc, &fmt, &brush);
}

static void FillRoundRect(Graphics& g, RectF r, REAL radius, Color color) {
    if (r.Width <= 0 || r.Height <= 0) return;
    REAL d = radius * 2.0f;
    if (d > r.Width) d = r.Width;
    if (d > r.Height) d = r.Height;
    GraphicsPath path;
    path.AddArc(r.X, r.Y, d, d, 180.0f, 90.0f);
    path.AddArc(r.X + r.Width - d, r.Y, d, d, 270.0f, 90.0f);
    path.AddArc(r.X + r.Width - d, r.Y + r.Height - d, d, d, 0.0f, 90.0f);
    path.AddArc(r.X, r.Y + r.Height - d, d, d, 90.0f, 90.0f);
    path.CloseFigure();
    SolidBrush brush(color);
    g.FillPath(&brush, &path);
}

static void DrawRoundBorder(Graphics& g, RectF r, REAL radius, Color color, REAL width = 1.0f) {
    REAL d = radius * 2.0f;
    if (d > r.Width) d = r.Width;
    if (d > r.Height) d = r.Height;
    GraphicsPath path;
    path.AddArc(r.X, r.Y, d, d, 180.0f, 90.0f);
    path.AddArc(r.X + r.Width - d, r.Y, d, d, 270.0f, 90.0f);
    path.AddArc(r.X + r.Width - d, r.Y + r.Height - d, d, d, 0.0f, 90.0f);
    path.AddArc(r.X, r.Y + r.Height - d, d, d, 90.0f, 90.0f);
    path.CloseFigure();
    Pen pen(color, width);
    g.DrawPath(&pen, &path);
}

static void DrawBadge(Graphics& g, REAL x, REAL y, REAL d, REAL fontSize) {
    LinearGradientBrush br(PointF(x, y), PointF(x + d, y + d),
        Color(255, 68, 183, 238), Color(255, 22, 92, 190));
    g.FillEllipse(&br, x, y, d, d);
    Pen ring(Color(90, 255, 255, 255), 1.0f);
    g.DrawEllipse(&ring, x + 2, y + 2, d - 4, d - 4);
    Font* f = g_fBadge;
    (void)fontSize;
    DrawTextG(g, L"播", f, Color(255, 255, 255, 255),
              RectF(x, y - S(1), d, d), StringAlignmentCenter, StringAlignmentCenter);
}

// ============================================================
// 启动画面
// ============================================================
static const wchar_t* kStages[] = {
    L"正在加载系统核心组件…",
    L"正在连接广播调度服务…",
    L"正在校验音频资源…",
    L"正在初始化界面资源…",
    L"加载完成，正在启动…"
};

static void PaintSplash(HWND hwnd) {
    PAINTSTRUCT ps;
    HDC hdc = BeginPaint(hwnd, &ps);
    RECT rc;
    GetClientRect(hwnd, &rc);

    Graphics g(hdc);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);
    g.SetInterpolationMode(InterpolationModeHighQualityBicubic);

    LinearGradientBrush bg(Point(0, 0), Point(0, rc.bottom),
        Color(255, 7, 18, 35), Color(255, 13, 34, 58));
    g.FillRectangle(&bg, 0, 0, rc.right, rc.bottom);

    // 顶部淡蓝径向光晕
    {
        GraphicsPath glowPath;
        glowPath.AddEllipse((REAL)S(-120), (REAL)S(-260), (REAL)S(1000), (REAL)S(620));
        PathGradientBrush glow(&glowPath);
        glow.SetCenterPoint(PointF((REAL)S(380), (REAL)S(40)));
        glow.SetCenterColor(Color(78, 48, 144, 224));
        Color surround[] = {Color(0, 7, 18, 35)};
        int n = 1;
        glow.SetSurroundColors(surround, &n);
        g.FillPath(&glow, &glowPath);
    }

    // 底部极淡网格
    {
        Pen grid(Color(16, 104, 174, 228), 1.0f);
        for (int x = 0; x < rc.right; x += S(38)) {
            g.DrawLine(&grid, x, S(336), x, rc.bottom);
        }
        for (int y = S(336); y < rc.bottom; y += S(26)) {
            g.DrawLine(&grid, 0, y, rc.right, y);
        }
    }

    DrawBadge(g, SR(344), SR(54), SR(72), 34);

    DrawTextG(g, L"旅客服务系统智能管理广播平台", g_fSplashTitle,
              Color(255, 238, 246, 255),
              RectF(0, SR(148), (REAL)rc.right, SR(42)),
              StringAlignmentCenter, StringAlignmentCenter);

    DrawTextG(g, L"Passenger Service Intelligent Broadcasting Management Platform",
              g_fSplashSub, Color(255, 132, 162, 192),
              RectF(0, SR(194), (REAL)rc.right, SR(24)),
              StringAlignmentCenter, StringAlignmentCenter);

    // 静态启动条：不做逐帧进度重绘，避免启动画面自身闪烁
    int barX = S(140);
    int barY = S(300);
    int barW = rc.right - S(280);
    int barH = S(3);
    FillRoundRect(g, RectF((REAL)barX, (REAL)barY, (REAL)barW, (REAL)barH),
                  (REAL)(barH / 2), Color(255, 54, 180, 238));
    DrawTextG(g, L"正在启动…", g_fSplashStatus, Color(255, 146, 184, 218),
              RectF(0, SR(316), (REAL)rc.right, SR(24)),
              StringAlignmentCenter, StringAlignmentCenter);

    DrawTextG(g, L"© 2026 Lishui Station  ·  Passenger Service", g_fSplashSmall,
              Color(255, 86, 112, 142),
              RectF(SR(40), (REAL)rc.bottom - SR(40), (REAL)S(520), SR(24)));

    DrawTextG(g, L"V26.10.2  ·  C++ Launcher", g_fSplashSmall,
              Color(255, 78, 104, 134),
              RectF((REAL)rc.right - S(280), (REAL)rc.bottom - SR(40), SR(240), SR(24)),
              StringAlignmentFar, StringAlignmentCenter);

    g_skipRect = {rc.right - S(158), rc.bottom - S(72), rc.right - S(36), rc.bottom - S(42)};
    DrawTextG(g, L"ESC  Skip", g_fSplashSmall, Color(255, 108, 154, 196),
              RectF((REAL)g_skipRect.left, (REAL)g_skipRect.top,
                    (REAL)(g_skipRect.right - g_skipRect.left),
                    (REAL)(g_skipRect.bottom - g_skipRect.top)),
              StringAlignmentCenter, StringAlignmentCenter);

    EndPaint(hwnd, &ps);
}

static LRESULT CALLBACK SplashProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE:
        g_hSplash = hwnd;
        g_splashStart = GetTickCount64();
        g_splashSkipped = false;
        SetTimer(hwnd, 1, 1000, nullptr);
        SetFocus(hwnd);
        return 0;
    case WM_ERASEBKGND:
        return 1;
    case WM_PAINT:
        PaintSplash(hwnd);
        return 0;
    case WM_TIMER:
        if (wp == 1) {
            if (GetTickCount64() - g_splashStart >= 2700) {
                KillTimer(hwnd, 1);
                DestroyWindow(hwnd);
            } else {
                // 启动画面是静态的：计时只负责关闭，不再整窗/局部重绘
            }
        }
        return 0;
    case WM_KEYDOWN:
        if (wp == VK_ESCAPE) {
            g_splashSkipped = true;
            DestroyWindow(hwnd);
            return 0;
        }
        break;
    case WM_LBUTTONUP: {
        POINT pt = {GET_X_LPARAM(lp), GET_Y_LPARAM(lp)};
        if (PtInRect(&g_skipRect, pt)) {
            g_splashSkipped = true;
            DestroyWindow(hwnd);
            return 0;
        }
        break;
    }
    case WM_DESTROY:
        g_hSplash = nullptr;
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

static void ShowSplash() {
    WNDCLASSW wc = {0};
    wc.lpfnWndProc = SplashProc;
    wc.hInstance = g_inst;
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    wc.hbrBackground = nullptr;
    wc.lpszClassName = kSplashClass;
    RegisterClassW(&wc);

    int w = S(760), h = S(460);
    RECT work = {0, 0, 1536, 864};
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work, 0);
    int x = work.left + ((work.right - work.left) - w) / 2;
    int y = work.top + ((work.bottom - work.top) - h) / 2;

    HWND splash = CreateWindowExW(WS_EX_TOPMOST, kSplashClass, L"",
        WS_POPUP, x, y, w, h, nullptr, nullptr, g_inst, nullptr);
    if (!splash) return;

    HRGN rgn = CreateRoundRectRgn(0, 0, w + 1, h + 1, S(16), S(16));
    SetWindowRgn(splash, rgn, TRUE);
    ShowWindow(splash, SW_SHOWNORMAL);
    UpdateWindow(splash);
    SetForegroundWindow(splash);

    MSG msg;
    while (IsWindow(splash) && GetMessageW(&msg, nullptr, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
}

// ============================================================
// 登录窗口布局
// ============================================================
struct LoginLayout {
    RECT client;
    int leftW;
    int formX;
    int formW;
    RECT userBorder, pwdBorder, capBorder, capBox, capHint;
    RECT remember, login, minBtn, closeBtn;
};

static LoginLayout GetLoginLayout(HWND hwnd) {
    LoginLayout L = {};
    GetClientRect(hwnd, &L.client);
    L.leftW = S(360);
    L.formX = S(408);
    L.formW = S(444);

    L.userBorder = {L.formX, S(170), L.formX + L.formW, S(212)};
    L.pwdBorder = {L.formX, S(250), L.formX + L.formW, S(292)};
    L.capBorder = {L.formX, S(330), L.formX + S(190), S(372)};
    L.capBox = {L.formX + S(206), S(330), L.formX + S(366), S(372)};
    L.capHint = {L.formX + S(374), S(338), L.formX + L.formW, S(366)};
    L.remember = {L.formX, S(388), L.formX + S(200), S(414)};
    L.login = {L.formX, S(450), L.formX + L.formW, S(496)};
    L.closeBtn = {L.client.right - S(48), 0, L.client.right, S(40)};
    L.minBtn = {L.client.right - S(92), 0, L.client.right - S(48), S(40)};
    return L;
}

// ============================================================
// 配置
// ============================================================
static void LoadLoginConfig(HWND hwnd) {
    std::wstring cfg = ConfigPath();
    wchar_t user[128] = {0};
    wchar_t pwd[128] = {0};

    GetPrivateProfileStringW(L"login", L"username", L"admin", user, 128, cfg.c_str());
    GetPrivateProfileStringW(L"login", L"password", L"", pwd, 128, cfg.c_str());
    int remember = GetPrivateProfileIntW(L"login", L"remember_pwd", 1, cfg.c_str());
    g_remember = remember != 0;

    if (!user[0]) wcscpy_s(user, L"admin");
    if (!g_remember) pwd[0] = 0;

    SetDlgItemTextW(hwnd, IDC_USER, user);
    SetDlgItemTextW(hwnd, IDC_PWD, pwd);
    SendDlgItemMessageW(hwnd, IDC_REMEMBER, BM_SETCHECK,
                        g_remember ? BST_CHECKED : BST_UNCHECKED, 0);
}

static void SaveLoginConfig(HWND hwnd, const std::wstring& user, const std::wstring& pwd) {
    std::wstring cfg = ConfigPath();
    WritePrivateProfileStringW(L"login", L"remember_user", g_remember ? L"1" : L"0", cfg.c_str());
    WritePrivateProfileStringW(L"login", L"remember_pwd", g_remember ? L"1" : L"0", cfg.c_str());
    WritePrivateProfileStringW(L"login", L"username", g_remember ? user.c_str() : L"", cfg.c_str());
    WritePrivateProfileStringW(L"login", L"password", g_remember ? pwd.c_str() : L"", cfg.c_str());
}

// ============================================================
// 验证码
// ============================================================
static void NewCaptcha() {
    static const wchar_t* chars = L"ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    static bool seeded = false;
    if (!seeded) {
        srand((unsigned)time(nullptr) ^ GetTickCount());
        seeded = true;
    }
    g_captcha.clear();
    for (int i = 0; i < 4; ++i) {
        g_captcha.push_back(chars[rand() % (int)wcslen(chars)]);
    }
    if (g_hLogin) InvalidateRect(g_hLogin, nullptr, FALSE);
}

// ============================================================
// 登录窗口绘制
// ============================================================
static void DrawPrimaryButton(LPDRAWITEMSTRUCT dis) {
    HDC hdc = dis->hDC;
    RECT rc = dis->rcItem;
    bool disabled = (dis->itemState & ODS_DISABLED) != 0;
    bool pressed = (dis->itemState & ODS_SELECTED) != 0;

    Graphics g(hdc);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);

    Color c1 = disabled ? Color(255, 178, 196, 214) : Color(255, 63, 168, 230);
    Color c2 = disabled ? Color(255, 154, 174, 194) : Color(255, 30, 94, 190);
    if (pressed && !disabled) {
        c1 = Color(255, 38, 126, 190);
        c2 = Color(255, 18, 72, 152);
    }
    LinearGradientBrush br(Point(rc.left, rc.top), Point(rc.left, rc.bottom), c1, c2);
    FillRoundRect(g, RectF((REAL)rc.left, (REAL)rc.top,
                           (REAL)(rc.right - rc.left), (REAL)(rc.bottom - rc.top)),
                  SR(8), Color(255, 255, 255, 255));
    SolidBrush fill(Color(255, 255, 255, 255));
    GraphicsPath path;
    REAL d = SR(16);
    REAL x = (REAL)rc.left, y = (REAL)rc.top;
    REAL w = (REAL)(rc.right - rc.left), h = (REAL)(rc.bottom - rc.top);
    path.AddArc(x, y, d, d, 180, 90);
    path.AddArc(x + w - d, y, d, d, 270, 90);
    path.AddArc(x + w - d, y + h - d, d, d, 0, 90);
    path.AddArc(x, y + h - d, d, d, 90, 90);
    path.CloseFigure();
    g.FillPath(&br, &path);

    wchar_t text[64] = {0};
    GetWindowTextW(dis->hwndItem, text, 64);
    DrawTextG(g, text, g_fButton, Color(255, 255, 255, 255),
              RectF((REAL)rc.left, (REAL)rc.top, w, h),
              StringAlignmentCenter, StringAlignmentCenter);
}

static void DrawCheckbox(LPDRAWITEMSTRUCT dis) {
    HDC hdc = dis->hDC;
    RECT rc = dis->rcItem;
    FillRect(hdc, &rc, g_hFormBrush);

    int box = S(17);
    int by = rc.top + ((rc.bottom - rc.top) - box) / 2;
    Rect boxRc(rc.left, by, box, box);
    bool checked = SendMessageW(dis->hwndItem, BM_GETCHECK, 0, 0) == BST_CHECKED;

    Graphics g(hdc);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    if (checked) {
        LinearGradientBrush br(Point(boxRc.X, boxRc.Y),
                               Point(boxRc.X + box, boxRc.Y + box),
                               Color(255, 63, 168, 230), Color(255, 30, 94, 190));
        g.FillRectangle(&br, boxRc);
        Pen pen(Color(255, 255, 255, 255), (REAL)S(2));
        g.DrawLine(&pen, (REAL)(boxRc.X + S(4)), (REAL)(boxRc.Y + S(9)),
                   (REAL)(boxRc.X + S(7)), (REAL)(boxRc.Y + S(12)));
        g.DrawLine(&pen, (REAL)(boxRc.X + S(7)), (REAL)(boxRc.Y + S(12)),
                   (REAL)(boxRc.X + S(13)), (REAL)(boxRc.Y + S(4)));
    } else {
        SolidBrush fill(Color(255, 255, 255, 255));
        g.FillRectangle(&fill, boxRc);
        Pen pen(Color(255, 190, 204, 220), 1.0f);
        g.DrawRectangle(&pen, boxRc);
    }

    RECT tr = {rc.left + box + S(8), rc.top, rc.right, rc.bottom};
    SetBkMode(hdc, TRANSPARENT);
    SetTextColor(hdc, RGB(64, 82, 104));
    HFONT old = (HFONT)SelectObject(hdc, g_hFontEdit);
    DrawTextW(hdc, L"记住密码", -1, &tr, DT_LEFT | DT_VCENTER | DT_SINGLELINE);
    SelectObject(hdc, old);
}

static void PaintLogin(HWND hwnd) {
    PAINTSTRUCT ps;
    HDC hdc = BeginPaint(hwnd, &ps);
    LoginLayout L = GetLoginLayout(hwnd);
    RECT rc = L.client;

    Graphics g(hdc);
    g.SetSmoothingMode(SmoothingModeAntiAlias);
    g.SetTextRenderingHint(TextRenderingHintClearTypeGridFit);
    g.SetInterpolationMode(InterpolationModeHighQualityBicubic);

    // 右侧白色表单区
    SolidBrush white(Color(255, 248, 250, 253));
    g.FillRectangle(&white, 0, 0, rc.right, rc.bottom);

    // 左侧品牌区
    {
        LinearGradientBrush brand(Point(0, 0), Point(L.leftW, rc.bottom),
            Color(255, 8, 24, 44), Color(255, 17, 52, 88));
        g.FillRectangle(&brand, 0, 0, L.leftW, rc.bottom);

        SolidBrush glow(Color(35, 52, 160, 225));
        g.FillEllipse(&glow, (REAL)-S(130), (REAL)(rc.bottom - S(260)),
                      (REAL)S(420), (REAL)S(420));
        SolidBrush glow2(Color(22, 64, 190, 240));
        g.FillEllipse(&glow2, (REAL)S(170), (REAL)(rc.bottom - S(120)),
                      (REAL)S(280), (REAL)S(280));

        SolidBrush line(Color(255, 48, 170, 232));
        g.FillRectangle(&line, (REAL)S(42), (REAL)S(118), (REAL)S(38), (REAL)S(3));

        DrawBadge(g, SR(42), SR(48), SR(58), 26);

        DrawTextG(g, L"旅客服务系统", g_fFormTitle, Color(255, 240, 247, 255),
                  RectF(SR(42), SR(124), SR(280), SR(38)));
        DrawTextG(g, L"智能管理广播平台", g_fFormTitle, Color(255, 160, 214, 246),
                  RectF(SR(42), SR(164), SR(290), SR(38)));

        DrawTextG(g, L"PASSENGER  SERVICE", g_fSmall, Color(255, 126, 164, 196),
                  RectF(SR(42), SR(226), SR(280), SR(20)));
        DrawTextG(g, L"BROADCAST  MANAGEMENT", g_fSmall, Color(255, 126, 164, 196),
                  RectF(SR(42), SR(246), SR(280), SR(20)));

        DrawTextG(g, L"铁路客运 · 智能广播调度平台", g_fTiny,
                  Color(255, 100, 132, 160),
                  RectF(SR(42), SR(296), SR(290), SR(20)));
        DrawTextG(g, L"V26.10.2  ·  C++ 启动器", g_fTiny,
                  Color(255, 82, 108, 136),
                  RectF(SR(42), (REAL)rc.bottom - SR(46), SR(270), SR(20)));
        DrawTextG(g, L"© 2026 丽水站", g_fTiny, Color(255, 70, 94, 122),
                  RectF(SR(42), (REAL)rc.bottom - SR(28), SR(220), SR(18)));
    }

    // 分隔线
    {
        Pen sep(Color(255, 255, 255, 255), 1.0f);
        g.DrawLine(&sep, (REAL)L.leftW, 0.0f, (REAL)L.leftW, (REAL)rc.bottom);
        Pen sep2(Color(255, 226, 232, 241), 1.0f);
        g.DrawLine(&sep2, (REAL)(L.leftW + 1), 0.0f, (REAL)(L.leftW + 1), (REAL)rc.bottom);
    }

    // 顶部最小化 / 关闭
    {
        SolidBrush gray(Color(255, 128, 145, 166));
        DrawTextG(g, L"—", g_fSmall, Color(255, 128, 145, 166),
                  RectF((REAL)L.minBtn.left, 0,
                        (REAL)(L.minBtn.right - L.minBtn.left), (REAL)S(40)),
                  StringAlignmentCenter, StringAlignmentCenter);
        DrawTextG(g, L"×", g_fFormSub, Color(255, 128, 145, 166),
                  RectF((REAL)L.closeBtn.left, 0,
                        (REAL)(L.closeBtn.right - L.closeBtn.left), (REAL)S(40)),
                  StringAlignmentCenter, StringAlignmentCenter);
    }

    // 表单标题
    DrawTextG(g, L"欢迎登录", g_fFormTitle, Color(255, 20, 38, 64),
              RectF((REAL)L.formX, SR(58), (REAL)L.formW, SR(38)));
    DrawTextG(g, L"请使用管理员账号进入广播控制台", g_fFormSub,
              Color(255, 112, 128, 148),
              RectF((REAL)L.formX, SR(100), (REAL)L.formW, SR(24)));

    // 标签
    DrawTextG(g, L"账号", g_fLabel, Color(255, 62, 80, 102),
              RectF((REAL)L.formX, SR(142), SR(120), SR(22)));
    DrawTextG(g, L"密码", g_fLabel, Color(255, 62, 80, 102),
              RectF((REAL)L.formX, SR(222), SR(120), SR(22)));
    DrawTextG(g, L"验证码", g_fLabel, Color(255, 62, 80, 102),
              RectF((REAL)L.formX, SR(302), SR(120), SR(22)));

    // 输入框边框（编辑框内缩 1px 创建）
    HWND focus = GetFocus();
    auto border = [&](RECT r, bool hot) {
        DrawRoundBorder(g, RectF((REAL)r.left, (REAL)r.top,
                                 (REAL)(r.right - r.left), (REAL)(r.bottom - r.top)),
                        SR(5), hot ? Color(255, 48, 152, 226) : Color(255, 205, 216, 230),
                        hot ? 2.0f : 1.0f);
    };
    border(L.userBorder, focus == GetDlgItem(hwnd, IDC_USER));
    border(L.pwdBorder, focus == GetDlgItem(hwnd, IDC_PWD));
    border(L.capBorder, focus == GetDlgItem(hwnd, IDC_CAPTCHA));

    // 验证码图片区
    {
        LinearGradientBrush capBg(Point(L.capBox.left, L.capBox.top),
                                  Point(L.capBox.right, L.capBox.bottom),
                                  Color(255, 235, 246, 255), Color(255, 215, 234, 251));
        g.FillRectangle(&capBg, (REAL)L.capBox.left, (REAL)L.capBox.top,
                        (REAL)(L.capBox.right - L.capBox.left),
                        (REAL)(L.capBox.bottom - L.capBox.top));
        DrawRoundBorder(g, RectF((REAL)L.capBox.left, (REAL)L.capBox.top,
                                 (REAL)(L.capBox.right - L.capBox.left),
                                 (REAL)(L.capBox.bottom - L.capBox.top)),
                        SR(5), Color(255, 186, 208, 230));

        // 干扰线
        Pen noise(Color(38, 80, 130, 180), 1.0f);
        g.DrawLine(&noise, (REAL)L.capBox.left + S(12), (REAL)L.capBox.top + S(28),
                   (REAL)L.capBox.right - S(18), (REAL)L.capBox.top + S(12));
        g.DrawLine(&noise, (REAL)L.capBox.left + S(20), (REAL)L.capBox.top + S(10),
                   (REAL)L.capBox.right - S(10), (REAL)L.capBox.top + S(32));

        Color colors[] = {
            Color(255, 28, 104, 188), Color(255, 194, 82, 30),
            Color(255, 34, 138, 86), Color(255, 118, 66, 170)
        };
        REAL cw = (REAL)(L.capBox.right - L.capBox.left) / 4.0f;
        for (int i = 0; i < (int)g_captcha.size() && i < 4; ++i) {
            std::wstring ch(1, g_captcha[i]);
            RectF cr((REAL)L.capBox.left + cw * i, (REAL)L.capBox.top,
                     cw, (REAL)(L.capBox.bottom - L.capBox.top));
            DrawTextG(g, ch, g_fCaptcha, colors[i], cr,
                      StringAlignmentCenter, StringAlignmentCenter);
        }

        DrawTextG(g, L"换一张", g_fSmall, Color(255, 44, 126, 196),
                  RectF((REAL)L.capHint.left, (REAL)L.capHint.top,
                        (REAL)(L.capHint.right - L.capHint.left),
                        (REAL)(L.capHint.bottom - L.capHint.top)),
                  StringAlignmentCenter, StringAlignmentCenter);
    }

    // 提示信息
    Color statusColor = Color(255, 108, 124, 144);
    if (g_statusKind == 1) statusColor = Color(255, 208, 64, 64);
    if (g_statusKind == 2) statusColor = Color(255, 30, 150, 92);
    DrawTextG(g, g_status, g_fSmall, statusColor,
              RectF((REAL)L.formX, SR(420), (REAL)L.formW, SR(22)));

    // 底部连接状态
    {
        SolidBrush dot(Color(255, 46, 176, 112));
        g.FillEllipse(&dot, (REAL)L.formX, (REAL)(rc.bottom - SR(34)), (REAL)S(7), (REAL)S(7));
        DrawTextG(g, L"本地调度模式 · 主界面可离线启动", g_fTiny,
                  Color(255, 104, 122, 142),
                  RectF((REAL)L.formX + S(13), (REAL)rc.bottom - SR(40),
                        (REAL)L.formW - S(13), SR(20)));
    }

    g_captchaRect = L.capBox;
    g_captchaHintRect = L.capHint;
    EndPaint(hwnd, &ps);
}

// ============================================================
// 登录逻辑
// ============================================================
static bool FocusExistingMainUi() {
    HWND h = FindWindowW(nullptr, kMainTitle);
    if (!h || !IsWindow(h)) return false;
    if (IsIconic(h)) ShowWindow(h, SW_RESTORE);
    else ShowWindow(h, SW_SHOW);
    BringWindowToTop(h);
    SetForegroundWindow(h);
    return true;
}

static bool LaunchMainUi(HWND owner) {
    std::wstring root = GetAppRoot();
    std::wstring exe = root + L"\\dist\\main_ui\\main_ui.exe";
    if (!FileExists(exe)) {
        std::wstring msg = L"未找到主界面程序：\n" + exe;
        MessageBoxW(owner, msg.c_str(), L"启动失败", MB_OK | MB_ICONERROR);
        return false;
    }
    HINSTANCE r = ShellExecuteW(owner, L"open", exe.c_str(), nullptr,
                                root.c_str(), SW_SHOWNORMAL);
    return (INT_PTR)r > 32;
}

static void DoLogin(HWND hwnd) {
    if (g_launching || g_loggedIn) return;

    wchar_t user[128] = {0};
    wchar_t pwd[128] = {0};
    wchar_t cap[32] = {0};
    GetDlgItemTextW(hwnd, IDC_USER, user, 128);
    GetDlgItemTextW(hwnd, IDC_PWD, pwd, 128);
    GetDlgItemTextW(hwnd, IDC_CAPTCHA, cap, 32);

    std::wstring u = user, p = pwd, c = cap;
    if (u.empty() || p.empty()) {
        g_status = L"请输入账号和密码";
        g_statusKind = 1;
        InvalidateRect(hwnd, nullptr, FALSE);
        SetFocus(GetDlgItem(hwnd, u.empty() ? IDC_USER : IDC_PWD));
        return;
    }
    if (_wcsicmp(c.c_str(), g_captcha.c_str()) != 0) {
        g_status = L"验证码错误，请重新输入";
        g_statusKind = 1;
        NewCaptcha();
        SetDlgItemTextW(hwnd, IDC_CAPTCHA, L"");
        InvalidateRect(hwnd, nullptr, FALSE);
        SetFocus(GetDlgItem(hwnd, IDC_CAPTCHA));
        return;
    }
    if (u != L"admin" || p != L"123456") {
        g_status = L"账号或密码错误，请重新输入";
        g_statusKind = 1;
        NewCaptcha();
        SetDlgItemTextW(hwnd, IDC_CAPTCHA, L"");
        InvalidateRect(hwnd, nullptr, FALSE);
        HWND pw = GetDlgItem(hwnd, IDC_PWD);
        SetFocus(pw);
        SendMessageW(pw, EM_SETSEL, 0, -1);
        return;
    }

    SaveLoginConfig(hwnd, u, p);
    g_status = L"登录成功，正在启动主界面…";
    g_statusKind = 2;
    g_launching = true;
    EnableWindow(GetDlgItem(hwnd, IDC_LOGIN), FALSE);
    InvalidateRect(hwnd, nullptr, FALSE);
    UpdateWindow(hwnd);
    SetTimer(hwnd, 2, 450, nullptr);
}

// ============================================================
// 登录窗口
// ============================================================
static LRESULT CALLBACK LoginProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        g_hLogin = hwnd;
        g_status = L"请输入账号、密码和验证码";
        g_statusKind = 0;

        BOOL dark = FALSE;
        DwmSetWindowAttribute(hwnd, 20, &dark, sizeof(dark));
        int corner = 2;
        DwmSetWindowAttribute(hwnd, 33, &corner, sizeof(corner));

        LoginLayout L = GetLoginLayout(hwnd);
        auto makeEdit = [&](int id, RECT r, DWORD extraStyle, const wchar_t* cue) {
            HWND e = CreateWindowExW(0, L"EDIT", L"",
                WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL | extraStyle,
                r.left + 1, r.top + 1, (r.right - r.left) - 2, (r.bottom - r.top) - 2,
                hwnd, (HMENU)(INT_PTR)id, g_inst, nullptr);
            SendMessageW(e, WM_SETFONT, (WPARAM)g_hFontEdit, TRUE);
            SendMessageW(e, EM_SETMARGINS, EC_LEFTMARGIN | EC_RIGHTMARGIN,
                         MAKELPARAM(S(10), S(8)));
            if (cue) SendMessageW(e, EM_SETCUEBANNER, TRUE, (LPARAM)cue);
            return e;
        };

        makeEdit(IDC_USER, L.userBorder, 0, L"请输入账号");
        makeEdit(IDC_PWD, L.pwdBorder, ES_PASSWORD, L"请输入密码");
        makeEdit(IDC_CAPTCHA, L.capBorder, ES_UPPERCASE, L"验证码");
        SendDlgItemMessageW(hwnd, IDC_CAPTCHA, EM_SETLIMITTEXT, 4, 0);

        CreateWindowExW(0, L"BUTTON", L"记住密码",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_OWNERDRAW,
            L.remember.left, L.remember.top,
            L.remember.right - L.remember.left, L.remember.bottom - L.remember.top,
            hwnd, (HMENU)IDC_REMEMBER, g_inst, nullptr);

        CreateWindowExW(0, L"BUTTON", L"登 录",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_OWNERDRAW,
            L.login.left, L.login.top,
            L.login.right - L.login.left, L.login.bottom - L.login.top,
            hwnd, (HMENU)IDC_LOGIN, g_inst, nullptr);

        LoadLoginConfig(hwnd);
        NewCaptcha();

        int w = L.client.right, h = L.client.bottom;
        HRGN rgn = CreateRoundRectRgn(0, 0, w + 1, h + 1, S(18), S(18));
        SetWindowRgn(hwnd, rgn, TRUE);

        PostMessageW(hwnd, WM_APP + 7, 0, 0);
        return 0;
    }
    case WM_APP + 7: {
        HWND user = GetDlgItem(hwnd, IDC_USER);
        wchar_t buf[128] = {0};
        GetWindowTextW(user, buf, 128);
        if (buf[0]) SetFocus(GetDlgItem(hwnd, IDC_PWD));
        else SetFocus(user);
        return 0;
    }
    case WM_ERASEBKGND:
        return 1;
    case WM_PAINT:
        PaintLogin(hwnd);
        return 0;
    case WM_CTLCOLOREDIT: {
        HDC hdc = (HDC)wp;
        SetTextColor(hdc, RGB(24, 38, 58));
        SetBkColor(hdc, RGB(255, 255, 255));
        return (LRESULT)g_hWhiteBrush;
    }
    case WM_DRAWITEM: {
        LPDRAWITEMSTRUCT dis = (LPDRAWITEMSTRUCT)lp;
        if (!dis) break;
        if (dis->CtlID == IDC_LOGIN) {
            DrawPrimaryButton(dis);
            return TRUE;
        }
        if (dis->CtlID == IDC_REMEMBER) {
            DrawCheckbox(dis);
            return TRUE;
        }
        break;
    }
    case WM_COMMAND: {
        int id = LOWORD(wp);
        int code = HIWORD(wp);
        if (id == IDC_LOGIN && code == BN_CLICKED) {
            DoLogin(hwnd);
            return 0;
        }
        if (id == IDC_REMEMBER && code == BN_CLICKED) {
            g_remember = !g_remember;
            SendDlgItemMessageW(hwnd, IDC_REMEMBER, BM_SETCHECK,
                                g_remember ? BST_CHECKED : BST_UNCHECKED, 0);
            InvalidateRect(GetDlgItem(hwnd, IDC_REMEMBER), nullptr, FALSE);
            return 0;
        }
        if ((id == IDC_USER || id == IDC_PWD || id == IDC_CAPTCHA) &&
            (code == EN_SETFOCUS || code == EN_KILLFOCUS)) {
            InvalidateRect(hwnd, nullptr, FALSE);
            return 0;
        }
        if (id == IDC_EXIT) {
            DestroyWindow(hwnd);
            return 0;
        }
        break;
    }
    case WM_LBUTTONDOWN: {
        POINT pt = {GET_X_LPARAM(lp), GET_Y_LPARAM(lp)};
        LoginLayout L = GetLoginLayout(hwnd);
        if (PtInRect(&L.closeBtn, pt)) {
            DestroyWindow(hwnd);
            return 0;
        }
        if (PtInRect(&L.minBtn, pt)) {
            ShowWindow(hwnd, SW_MINIMIZE);
            return 0;
        }
        if (PtInRect(&g_captchaRect, pt) || PtInRect(&g_captchaHintRect, pt)) {
            NewCaptcha();
            SetDlgItemTextW(hwnd, IDC_CAPTCHA, L"");
            SetFocus(GetDlgItem(hwnd, IDC_CAPTCHA));
            InvalidateRect(hwnd, nullptr, FALSE);
            return 0;
        }
        if (pt.y < S(40) || pt.x < L.leftW) {
            ReleaseCapture();
            SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0);
            return 0;
        }
        break;
    }
    case WM_TIMER:
        if (wp == 2) {
            KillTimer(hwnd, 2);
            if (FocusExistingMainUi() || LaunchMainUi(hwnd)) {
                g_loggedIn = true;
                ShowWindow(hwnd, SW_HIDE);
                DestroyWindow(hwnd);
            } else {
                g_launching = false;
                g_status = L"主界面启动失败，请检查程序目录";
                g_statusKind = 1;
                EnableWindow(GetDlgItem(hwnd, IDC_LOGIN), TRUE);
                InvalidateRect(hwnd, nullptr, FALSE);
            }
            return 0;
        }
        break;
    case WM_CLOSE:
        DestroyWindow(hwnd);
        return 0;
    case WM_DESTROY:
        g_hLogin = nullptr;
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

static HWND CreateLoginWindow() {
    WNDCLASSW wc = {0};
    wc.lpfnWndProc = LoginProc;
    wc.hInstance = g_inst;
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    wc.hbrBackground = nullptr;
    wc.lpszClassName = kLoginClass;
    RegisterClassW(&wc);

    int w = S(900), h = S(560);
    RECT work = {0, 0, 1536, 864};
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work, 0);
    int x = work.left + ((work.right - work.left) - w) / 2;
    int y = work.top + ((work.bottom - work.top) - h) / 2;

    HWND hwnd = CreateWindowExW(WS_EX_APPWINDOW | WS_EX_CONTROLPARENT,
        kLoginClass, L"旅客服务系统智能管理广播平台 - 登录",
        WS_POPUP | WS_SYSMENU | WS_MINIMIZEBOX,
        x, y, w, h, nullptr, nullptr, g_inst, nullptr);
    if (!hwnd) return nullptr;

    ShowWindow(hwnd, SW_SHOWNORMAL);
    UpdateWindow(hwnd);
    SetForegroundWindow(hwnd);
    SetFocus(hwnd);
    return hwnd;
}

// ============================================================
// 清理 / 入口
// ============================================================
static void Cleanup() {
    delete g_fBadge; g_fBadge = nullptr;
    delete g_fSplashTitle; g_fSplashTitle = nullptr;
    delete g_fSplashSub; g_fSplashSub = nullptr;
    delete g_fSplashStatus; g_fSplashStatus = nullptr;
    delete g_fSplashSmall; g_fSplashSmall = nullptr;
    delete g_fFormTitle; g_fFormTitle = nullptr;
    delete g_fFormSub; g_fFormSub = nullptr;
    delete g_fLabel; g_fLabel = nullptr;
    delete g_fSmall; g_fSmall = nullptr;
    delete g_fTiny; g_fTiny = nullptr;
    delete g_fCaptcha; g_fCaptcha = nullptr;
    delete g_fButton; g_fButton = nullptr;
    delete g_fCheck; g_fCheck = nullptr;

    if (g_hFontEdit) { DeleteObject(g_hFontEdit); g_hFontEdit = nullptr; }
    if (g_hWhiteBrush) { DeleteObject(g_hWhiteBrush); g_hWhiteBrush = nullptr; }
    if (g_hFormBrush) { DeleteObject(g_hFormBrush); g_hFormBrush = nullptr; }

    if (g_gdiToken) {
        GdiplusShutdown(g_gdiToken);
        g_gdiToken = 0;
    }
}

int APIENTRY wWinMain(HINSTANCE hInstance, HINSTANCE, LPWSTR, int) {
    g_inst = hInstance;
    InitDpiAndScale();

    SetCurrentProcessExplicitAppUserModelID(L"PassengerBroadcast.System.CppLauncher.V3");

    HANDLE mutex = CreateMutexW(nullptr, TRUE, L"Local\\PassengerBroadcastSys_CppLauncher_V3");
    if (mutex && GetLastError() == ERROR_ALREADY_EXISTS) {
        HWND existing = FindWindowW(kLoginClass, nullptr);
        if (existing && IsWindow(existing)) {
            ShowWindow(existing, SW_RESTORE);
            SetForegroundWindow(existing);
        } else {
            MessageBoxW(nullptr, L"启动器已经在运行中。", kMainTitle,
                        MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND);
        }
        CloseHandle(mutex);
        return 0;
    }

    GdiplusStartupInput gdiInput;
    if (GdiplusStartup(&g_gdiToken, &gdiInput, nullptr) != Ok) {
        MessageBoxW(nullptr, L"图形组件初始化失败，无法启动。", kMainTitle,
                    MB_OK | MB_ICONERROR);
        if (mutex) CloseHandle(mutex);
        return 1;
    }

    InitCommonControls();
    InitFonts();
    ShowSplash();

    HWND login = CreateLoginWindow();
    if (!login) {
        MessageBoxW(nullptr, L"登录窗口创建失败。", kMainTitle, MB_OK | MB_ICONERROR);
        Cleanup();
        if (mutex) CloseHandle(mutex);
        return 1;
    }

    MSG msg;
    while (GetMessageW(&msg, nullptr, 0, 0)) {
        if (msg.message == WM_KEYDOWN && msg.wParam == VK_RETURN &&
            g_hLogin && (msg.hwnd == g_hLogin || IsChild(g_hLogin, msg.hwnd))) {
            DoLogin(g_hLogin);
            continue;
        }
        if (msg.message == WM_KEYDOWN && msg.wParam == VK_ESCAPE &&
            g_hLogin && msg.hwnd == g_hLogin) {
            PostMessageW(g_hLogin, WM_CLOSE, 0, 0);
            continue;
        }
        if (g_hLogin && IsDialogMessageW(g_hLogin, &msg)) continue;
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    Cleanup();
    if (mutex) {
        ReleaseMutex(mutex);
        CloseHandle(mutex);
    }
    return 0;
}
