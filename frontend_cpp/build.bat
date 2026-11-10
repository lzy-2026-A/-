@echo off
chcp 65001 >nul
setlocal
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d "%~dp0"
if not exist obj mkdir obj
rc /nologo /fo obj\app.res app.rc
if errorlevel 1 exit /b 1
cl /nologo /EHsc /O2 /utf-8 /W3 /DUNICODE /D_UNICODE main.cpp obj\app.res ^
  /Fo:obj\ /Fe:frontend.exe ^
  /link /SUBSYSTEM:WINDOWS ws2_32.lib user32.lib gdi32.lib gdiplus.lib comctl32.lib shell32.lib dwmapi.lib advapi32.lib
if errorlevel 1 exit /b 1
echo BUILD_OK
