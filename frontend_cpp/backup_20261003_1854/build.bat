@echo off
chcp 65001 >nul
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d "D:\桌面\旅客服务系统智能管理广播平台\frontend_cpp"
if not exist obj mkdir obj
cl /nologo /EHsc /O2 /utf-8 /W3 main.cpp /Fo:obj\ /Fe:广播系统前端.exe /link ws2_32.lib user32.lib gdi32.lib comctl32.lib winmm.lib
echo EXITCODE=%ERRORLEVEL%
