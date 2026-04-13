@echo off
chcp 65001 >nul
echo Stopping History AI Chat Viewer...
echo.

set FOUND=
for /f %%P in ('powershell -NoProfile -Command "$processes = Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|pythonw)\.exe$' -and $_.CommandLine -match 'viewer\.main:app' -and $_.CommandLine -match '--port 6300' }; $processes | ForEach-Object { $_.ProcessId }"') do (
    echo Stopping PID %%P...
    taskkill /PID %%P /T /F >nul
    set FOUND=1
)

if not defined FOUND (
    echo Service is not running.
    exit /b 0
)

echo.
echo Service stopped.