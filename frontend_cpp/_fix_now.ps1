$src = 'D:\桌面\旅客服务系统智能管理广播平台\frontend_cpp\main.cpp'
$rep = 'D:\桌面\旅客服务系统智能管理广播平台\frontend_cpp\fix_report_20260926.txt'
$lines = [System.IO.File]::ReadAllLines($src)
$out = New-Object System.Collections.Generic.List[string]
$out.Add(('TOTAL=' + $lines.Length))
$out.Add(('SIZE=' + (Get-Item -LiteralPath $src).Length))
$out.Add(('MTIME=' + (Get-Item -LiteralPath $src).LastWriteTime.ToString('o')))
$joined = [string]::Join("`n", $lines)
$out.Add(('HAS_ShowLoginWindow=' + $joined.Contains('static void ShowLoginWindow()')))
$out.Add(('HAS_ShowMainWindow=' + $joined.Contains('static void ShowMainWindow()')))
$out.Add(('HAS_g_hLoginWin=' + $joined.Contains('g_hLoginWin')))
$out.Add(('HAS_g_hLogin=' + $joined.Contains('static HWND g_hLogin')))
$out.Add(('HAS_g_loggedIn=' + $joined.Contains('g_loggedIn')))
$out.Add(('HAS_ShowMainCall=' + $joined.Contains('ShowMainWindow();')))
$out.Add(('HAS_ShowLoginCall=' + $joined.Contains('ShowLoginWindow();')))
$out.Add(('HAS_SW_HIDE=' + $joined.Contains('ShowWindow(main, SW_HIDE)')))
$out.Add(('HAS_outer=' + $joined.Contains([char]0x5916 + [char]0x5C42 + [char]0x5FAA + [char]0x73AF)))
$out.Add(('HAS_formY118=' + $joined.Contains('int formY = 118')))
$out.Add(('HAS_IDC_LBL_BTYPE=' + $joined.Contains('IDC_LBL_BTYPE')))
$out.Add(('HAS_Destroyhwnd=' + $joined.Contains('DestroyWindow(hwnd)')))
$out.Add(('GETMESSAGE_COUNT=' + ([regex]::Matches($joined, 'GetMessageW\s*\(')).Count))
$out.Add('---- HITS ----')
for ($i = 0; $i -lt $lines.Length; $i++) {
    $t = $lines[$i]
    if ($t -match 'ShowLoginWindow|ShowMainWindow|g_hLogin|g_hLoginWin|g_loggedIn|IDC_BTN_LOGOUT|IDC_BTN_EXIT|PostQuitMessage|DestroyWindow\(hwnd\)|ShowWindow\(main|formY|IDC_LBL_|g_hMain = hwnd|g_hLogin = hwnd|GetMessageW|while \(true\)|int msgY|int audioY|int volY|IDC_STOP|IDC_PAUSE|IDC_RESUME') {
        $out.Add((($i + 1).ToString() + ':' + $t.TrimEnd()))
    }
}
[System.IO.File]::WriteAllLines($rep, $out.ToArray())
Write-Output ('DUMP_OK lines=' + $lines.Length)