# Apply remaining A-L patches to main.cpp
$ErrorActionPreference = 'Stop'
$src = 'D:\桌面\旅客服务系统智能管理广播平台\frontend_cpp\main.cpp'
$bak = 'D:\桌面\旅客服务系统智能管理广播平台\frontend_cpp\main.cpp.prepatch'
$rep = 'D:\桌面\旅客服务系统智能管理广播平台\frontend_cpp\patchlog_k7x9m2.txt'

function Log([string]$s) { $script:log += $s + "`r`n" }

$script:log = ''
Log "START $(Get-Date -Format o)"
Log "SRC=$src"

# backup once
if (-not (Test-Path -LiteralPath $bak)) {
    Copy-Item -LiteralPath $src -Destination $bak -Force
    Log "BACKUP_CREATED=$bak"
} else {
    Log "BACKUP_EXISTS=$bak"
}

$bytes = [System.IO.File]::ReadAllBytes($src)
$enc = New-Object System.Text.UTF8Encoding $false
$text = $enc.GetString($bytes)
if ($text.Contains([char]0xFFFD) -and $bytes[0] -ne 0xEF) {
    $enc = [System.Text.Encoding]::GetEncoding(936)
    $text = $enc.GetString($bytes)
    Log "ENCODING=GBK"
} else {
    Log "ENCODING=UTF8"
}
Log "ORIG_LEN=$($text.Length) BYTES=$($bytes.Length)"

$orig = $text
$changes = @()

function DoReplace([string]$name, [string]$old, [string]$new) {
    if ($script:text.Contains($old)) {
        $c = ([regex]::Matches($script:text, [regex]::Escape($old))).Count
        $script:text = $script:text.Replace($old, $new)
        $script:changes += "$name x$c"
        Log "OK $name count=$c"
        return $true
    } else {
        Log "MISS $name"
        return $false
    }
}

# ---- A: unify globals ----
DoReplace 'add_loggedIn_and_rename_login' `
"static HWND g_hMain = nullptr;`r`nstatic HWND g_hLoginWin = nullptr;" `
"static bool g_loggedIn = false;`r`nstatic HWND g_hMain = nullptr;`r`nstatic HWND g_hLogin = nullptr;"

if ($text.Contains('g_hLoginWin')) {
    $c = ([regex]::Matches($text, 'g_hLoginWin')).Count
    $text = $text.Replace('g_hLoginWin', 'g_hLogin')
    $changes += "rename_g_hLoginWin x$c"
    Log "OK rename_g_hLoginWin count=$c"
} else {
    Log "INFO g_hLoginWin already gone or never present after first replace"
}

if (-not $text.Contains('static bool g_loggedIn')) {
    if ($text.Contains('static bool g_isLogout = false;')) {
        DoReplace 'insert_g_loggedIn' `
"static bool g_isLogout = false;" `
"static bool g_isLogout = false;`r`nstatic bool g_loggedIn = false;"
    }
}

# ---- label IDs 2610-2614 ----
if (-not $text.Contains('#define IDC_LBL_BTYPE')) {
    DoReplace 'add_lbl_ids' `
"#define IDC_BTN_LOGOUT 2801`r`n#define IDC_BTN_EXIT 2802" `
"#define IDC_BTN_LOGOUT 2801`r`n#define IDC_BTN_EXIT 2802`r`n#define IDC_LBL_BTYPE 2610`r`n#define IDC_LBL_PRI 2611`r`n#define IDC_LBL_MSG 2612`r`n#define IDC_LBL_AUDIO 2613`r`n#define IDC_LBL_VOL 2614"
}

# ---- B: Main WM_CREATE g_hMain = hwnd ----
# insert after first occurrence of Main create-related WM_CREATE if missing
if ($text -notmatch 'g_hMain\s*=\s*hwnd') {
    # typical pattern: case WM_CREATE: near MainProc
    $m = [regex]::Match($text, '(static LRESULT CALLBACK MainProc[\s\S]{0,400}case WM_CREATE:\s*\{)')
    if ($m.Success) {
        $old = $m.Groups[1].Value
        $new = $old + "`r`n        g_hMain = hwnd;"
        $text = $text.Replace($old, $new)
        $changes += 'main_wm_create_assign'
        Log 'OK main_wm_create_assign'
    } else {
        Log 'MISS main_wm_create_assign_anchor'
    }
} else {
    Log 'INFO g_hMain=hwnd already present'
}

# ---- C + I: Login WM_CREATE / WM_DESTROY ----
if ($text -notmatch 'g_hLogin\s*=\s*hwnd') {
    $m = [regex]::Match($text, '(static LRESULT CALLBACK LoginProc[\s\S]{0,500}case WM_CREATE:\s*\{)')
    if ($m.Success) {
        $old = $m.Groups[1].Value
        $new = $old + "`r`n        g_hLogin = hwnd;"
        $text = $text.Replace($old, $new)
        $changes += 'login_wm_create_assign'
        Log 'OK login_wm_create_assign'
    } else {
        Log 'MISS login_wm_create_assign_anchor'
    }
} else {
    Log 'INFO g_hLogin=hwnd already present'
}

if ($text -notmatch 'g_hLogin\s*=\s*nullptr') {
    $m = [regex]::Match($text, '(static LRESULT CALLBACK LoginProc[\s\S]*?case WM_DESTROY:\s*\{)')
    if ($m.Success) {
        $old = $m.Groups[1].Value
        $new = $old + "`r`n        g_hLogin = nullptr;"
        $text = $text.Replace($old, $new)
        $changes += 'login_wm_destroy_null'
        Log 'OK login_wm_destroy_null'
    } else {
        # try simpler
        Log 'MISS login_wm_destroy_anchor'
    }
} else {
    Log 'INFO g_hLogin=nullptr already present'
}

# ---- D: logout button ----
# If still DestroyWindow on logout, replace with ShowLoginWindow
$logoutPat = '(?s)(case IDC_BTN_LOGOUT:.*?)(DestroyWindow\s*\(\s*hwnd\s*\)\s*;(?:\s*PostQuitMessage\s*\(\s*0\s*\)\s*;)?)'
$logoutM = [regex]::Match($text, $logoutPat)
if ($logoutM.Success -and $logoutM.Groups[2].Value -match 'DestroyWindow') {
    $text = $text.Remove($logoutM.Groups[2].Index, $logoutM.Groups[2].Length).Insert($logoutM.Groups[2].Index, "g_isLogout = true;`r`n                ShowLoginWindow();")
    $changes += 'logout_hide_not_destroy'
    Log 'OK logout_hide_not_destroy'
} elseif ($text.Contains('ShowLoginWindow();')) {
    Log 'INFO logout already uses ShowLoginWindow or function exists'
} else {
    Log 'MISS logout_handler_pattern'
}

# Ensure g_isLogout = true near ShowLoginWindow call in logout if missing
if ($text -match 'case IDC_BTN_LOGOUT:' -and $text -notmatch '(?s)case IDC_BTN_LOGOUT:.{0,400}g_isLogout\s*=\s*true') {
    $m = [regex]::Match($text, '(case IDC_BTN_LOGOUT:\s*\{)')
    if ($m.Success) {
        $text = $text.Remove($m.Index, $m.Length).Insert($m.Index, "case IDC_BTN_LOGOUT: {`r`n                g_isLogout = true;")
        $changes += 'logout_set_flag'
        Log 'OK logout_set_flag'
    }
}

# ---- E: exit button: keep PostQuitMessage, no DestroyWindow if it would recurse ----
# Already specified: confirm, g_isLogout=false, shutdown, tcpClose, PostQuitMessage
# Don't force-change if already correct.

# ---- F: Main WM_DESTROY ----
if ($text -notmatch '(?s)case WM_DESTROY:.{0,300}if\s*\(\s*!g_isLogout\s*\)') {
    $m = [regex]::Match($text, '(static LRESULT CALLBACK MainProc[\s\S]*?case WM_DESTROY:\s*\{)([\s\S]*?)(PostQuitMessage\s*\(\s*0\s*\)\s*;)')
    if ($m.Success) {
        $old = $m.Value
        $new = $m.Groups[1].Value + $m.Groups[2].Value + "g_hMain = nullptr;`r`n        if (!g_isLogout) PostQuitMessage(0);"
        $text = $text.Replace($old, $new)
        $changes += 'main_wm_destroy_guard'
        Log 'OK main_wm_destroy_guard'
    } else {
        Log 'MISS main_wm_destroy_guard_anchor'
    }
} else {
    Log 'INFO main WM_DESTROY already guarded'
}

# ---- G: login success DestroyWindow+PostQuitMessage -> ShowMainWindow ----
# Look for login success block
$loginOkPats = @(
    @{old="DestroyWindow(hwnd);`r`n                PostQuitMessage(0);"; new="ShowMainWindow();"},
    @{old="DestroyWindow(hwnd);`r`n            PostQuitMessage(0);"; new="ShowMainWindow();"},
    @{old="DestroyWindow(hwnd); PostQuitMessage(0);"; new="ShowMainWindow();"}
)
$didLoginOk = $false
foreach ($p in $loginOkPats) {
    if ($text.Contains($p.old)) {
        # only replace the FIRST occurrence after Login / 登录成功 context if possible
        $idx = $text.IndexOf($p.old)
        # check nearby context for login
        $ctxStart = [Math]::Max(0, $idx - 400)
        $ctx = $text.Substring($ctxStart, [Math]::Min(500, $text.Length - $ctxStart))
        if ($ctx -match '登录成功|Login|IDC_BTN_LOGIN|g_loggedIn|ShowMain') {
            $text = $text.Remove($idx, $p.old.Length).Insert($idx, $p.new)
            $changes += 'login_success_showmain'
            Log 'OK login_success_showmain'
            $didLoginOk = $true
            break
        } else {
            Log "WARN found Destroy+Quit but context not login: $($ctx.Substring(0,[Math]::Min(80,$ctx.Length)))"
        }
    }
}
if (-not $didLoginOk) {
    if ($text.Contains('ShowMainWindow();')) {
        Log 'INFO ShowMainWindow() call exists (login success maybe already patched)'
    } else {
        Log 'MISS login_success_replace'
    }
}

# ---- K: broadcast overlap ----
# Create: type/priority y=70 -> 118, give IDs
# Common patterns in this file:
DoReplace 'bc_type_label_y' `
'L"类型：", WS_VISIBLE | WS_CHILD, 20, 70, 50, 22, panel2, nullptr,' `
'L"类型：", WS_VISIBLE | WS_CHILD, 20, 118, 50, 22, panel2, (HMENU)IDC_LBL_BTYPE,'

DoReplace 'bc_type_label_y2' `
'L"类型：", WS_CHILD | WS_VISIBLE, 20, 70, 50, 22, panel2, nullptr,' `
'L"类型：", WS_CHILD | WS_VISIBLE, 20, 118, 50, 22, panel2, (HMENU)IDC_LBL_BTYPE,'

# combo y=68 -> 116
DoReplace 'bc_combo_y' '70, 68, 120, 180, panel2, (HMENU)IDC_BTYPE_CMB' '70, 116, 120, 180, panel2, (HMENU)IDC_BTYPE_CMB'

DoReplace 'bc_pri_label_y' `
'L"优先级：", WS_VISIBLE | WS_CHILD, 210, 70, 55, 22, panel2, nullptr,' `
'L"优先级：", WS_VISIBLE | WS_CHILD, 210, 118, 55, 22, panel2, (HMENU)IDC_LBL_PRI,'

DoReplace 'bc_pri_label_y2' `
'L"优先级：", WS_CHILD | WS_VISIBLE, 210, 70, 55, 22, panel2, nullptr,' `
'L"优先级：", WS_CHILD | WS_VISIBLE, 210, 118, 55, 22, panel2, (HMENU)IDC_LBL_PRI,'

# Also try without exact style order - regex fallback
if ($text -match '类型：.{0,80}20,\s*70,') {
    $text = [regex]::Replace($text, '(类型：.{0,80}20,\s*)70(,)', '${1}118${2}', 1)
    $changes += 'bc_type_y_regex'
    Log 'OK bc_type_y_regex'
}
if ($text -match '优先级：.{0,80}210,\s*70,') {
    $text = [regex]::Replace($text, '(优先级：.{0,80}210,\s*)70(,)', '${1}118${2}', 1)
    $changes += 'bc_pri_y_regex'
    Log 'OK bc_pri_y_regex'
}

# Content / audio / volume y shifts if they are still too high
# Typical: content label around y=110-120, we want 158
# We'll regex-scan nearby CreateWindow y values after 优先级

# LayoutMain sync
DoReplace 'layout_msgy' `
"        int msgY = 120;" `
"        int formY = 118;`r`n        int msgY = 158;"

# Add MoveWindow for labels / stop/pause/resume after msgY block if missing
if ($text.Contains('int formY = 118;') -and -not $text.Contains('IDC_LBL_BTYPE')) {
    Log 'WARN formY set but IDC_LBL_BTYPE not in LayoutMain yet'
}

if ($text.Contains('int formY = 118;') -and $text -notmatch 'MoveWindow\(GetDlgItem\(hwnd, IDC_LBL_BTYPE\)') {
    $anchor = "        int formY = 118;`r`n        int msgY = 158;"
    if ($text.Contains($anchor)) {
        $insert = @"
        int formY = 118;
        int msgY = 158;
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_BTYPE), 20, formY, 50, 22, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_BTYPE_CMB), 70, formY - 2, 120, 24, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_PRI), 210, formY, 55, 22, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_PRI_CMB), 270, formY - 2, 80, 24, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_MSG), 20, msgY, 90, 22, TRUE);
"@
        # Don't assume IDC_PRI_CMB exists - check
        if (-not $text.Contains('IDC_PRI_CMB')) {
            $insert = @"
        int formY = 118;
        int msgY = 158;
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_BTYPE), 20, formY, 50, 22, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_BTYPE_CMB), 70, formY - 2, 120, 24, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_PRI), 210, formY, 55, 22, TRUE);
        MoveWindow(GetDlgItem(hwnd, IDC_LBL_MSG), 20, msgY, 90, 22, TRUE);
"@
        }
        $text = $text.Replace($anchor, $insert)
        $changes += 'layout_move_labels'
        Log 'OK layout_move_labels'
    }
}

# audioY / volY
DoReplace 'layout_audioY' "        int audioY = msgY + 50;" "        int audioY = 206;"
DoReplace 'layout_volY' "        int volY = audioY + 60;" "        int volY = 256;"

# STOP/PAUSE/RESUME MoveWindow if missing
if ($text.Contains('IDC_STOP') -or $text.Contains('IDC_BTN_STOP') -or $text.Contains('IDC_PB_STOP')) {
    Log 'INFO stop-like IDs present'
}

# Try common IDs
$stopIds = @('IDC_STOP','IDC_BTN_STOP','IDC_PB_STOP','IDC_BC_STOP')
$pauseIds = @('IDC_PAUSE','IDC_BTN_PAUSE','IDC_PB_PAUSE','IDC_BC_PAUSE')
$resumeIds = @('IDC_RESUME','IDC_BTN_RESUME','IDC_PB_RESUME','IDC_BC_RESUME')

function FirstPresent($arr) {
    foreach ($id in $arr) { if ($script:text.Contains($id)) { return $id } }
    return $null
}
$sid = FirstPresent $stopIds
$pid = FirstPresent $pauseIds
$rid = FirstPresent $resumeIds
Log "STOP_ID=$sid PAUSE_ID=$pid RESUME_ID=$rid"

if ($sid -and $text -notmatch "MoveWindow\(GetDlgItem\(hwnd, $sid\)") {
    # insert after volY layout if possible
    $m = [regex]::Match($text, 'int volY = 256;')
    if ($m.Success) {
        $extra = "`r`n        MoveWindow(GetDlgItem(hwnd, $sid), 20, volY + 40, 80, 28, TRUE);"
        if ($pid) { $extra += "`r`n        MoveWindow(GetDlgItem(hwnd, $pid), 110, volY + 40, 80, 28, TRUE);" }
        if ($rid) { $extra += "`r`n        MoveWindow(GetDlgItem(hwnd, $rid), 200, volY + 40, 80, 28, TRUE);" }
        $text = $text.Remove($m.Index + $m.Length, 0).Insert($m.Index + $m.Length, $extra)
        $changes += 'layout_move_stop_pause_resume'
        Log 'OK layout_move_stop_pause_resume'
    }
}

# ---- J: WinMain single loop ----
# If outer login loop comment still exists, try to replace the well-known structure.
# We'll detect current WinMain shape and log it.
$wm = [regex]::Match($text, 'int WINAPI w?WinMain[\s\S]+')
if ($wm.Success) {
    $tail = $wm.Value
    $hasOuter = $tail.Contains('外层循环') -or $tail.Contains('while (true)') -or $tail.Contains('while(true)')
    $hasSingle = $tail.Contains('ShowWindow(main, SW_HIDE)') -or $tail.Contains('ShowWindow(g_hMain, SW_HIDE)')
    $loopCount = ([regex]::Matches($tail, 'GetMessageW\s*\(')).Count
    Log "WINMAIN_HAS_OUTER=$hasOuter SINGLE_HIDE=$hasSingle GETMESSAGE_COUNT=$loopCount"

    # If there are 2+ GetMessage loops, collapse to one.
    # Safer approach: if we find the classic create-login then GetMessage then create-main then GetMessage,
    # rewrite the section from first CreateWindowExW LoginWin to cleanup.
}

# Try replace classic dual-loop WinMain body if present
$dual = [regex]::Match($text, '(?s)(// 外层循环：登录.*?)(cleanup:)')
if ($dual.Success) {
    $replacement = @"
    // 登录窗口与主窗口各创建一次，全程只跑一个消息循环
    g_loggedIn = false;
    g_isLogout = false;
    HWND login = CreateWindowExW(0, L"LoginWin", L"旅客服务系统 - 登录",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, 520, 420, nullptr, nullptr, hInst, nullptr);
    g_hLogin = login;
    HWND main = CreateWindowExW(0, L"MainWin", L"旅客服务系统智能管理广播平台",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT, 1280, 800, nullptr, nullptr, hInst, nullptr);
    g_hMain = main;
    ShowWindow(main, SW_HIDE);
    ShowWindow(login, nCmdShow);
    UpdateWindow(login);
    MSG msg;
    while (GetMessageW(&msg, nullptr, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    if (g_hMain && IsWindow(g_hMain)) DestroyWindow(g_hMain);
    if (g_hLogin && IsWindow(g_hLogin)) DestroyWindow(g_hLogin);
    cleanup:
"@
    # This replacement may break if CreateWindowExW signatures differ.
    # Don't apply blindly - log the old snippet instead if signatures unknown.
    Log 'FOUND dual-loop comment block - attempting structured rewrite is risky; checking CreateWindow class names'
}

# More conservative WinMain fix: if we see a while(true) around login create, log line context
$lines = $text -split "`r`n", -1
if ($lines.Count -eq 1) { $lines = $text -split "`n", -1 }
Log "TOTAL_LINES=$($lines.Count)"

# Collect hits
Log '---- HITS ----'
for ($i=0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match 'ShowLoginWindow|ShowMainWindow|g_hLogin|g_hLoginWin|g_loggedIn|IDC_BTN_LOGOUT|IDC_BTN_EXIT|PostQuitMessage|DestroyWindow\(hwnd\)|外层循环|ShowWindow\(main|formY|IDC_LBL_|g_hMain = hwnd|g_hLogin = hwnd|GetMessageW|while \(true\)|while\(true\)|类型：|优先级：|int msgY|int audioY|int volY|IDC_STOP|IDC_PAUSE|IDC_RESUME') {
        Log ('{0}:{1}' -f ($i+1), $lines[$i].TrimEnd())
    }
}

# Write file only if changed
if ($text -ne $orig) {
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($src, $text, $utf8)
    Log "WRITTEN=YES NEW_LEN=$($text.Length) CHANGES=$($changes -join ', ')"
} else {
    Log 'WRITTEN=NO (no text change)'
}

Log "CHANGE_LIST=$($changes -join ' | ')"
Log "END $(Get-Date -Format o)"
[System.IO.File]::WriteAllText($rep, $script:log, [System.Text.UTF8Encoding]::new($false))
Write-Output "PATCH_SCRIPT_DONE report=$rep changes=$($changes.Count)"
