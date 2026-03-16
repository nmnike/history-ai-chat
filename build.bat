@echo off
chcp 65001 >nul
echo Building History AI Chat Desktop...
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo.
echo Running PyInstaller...
pyinstaller build.spec --clean

echo.
if exist "dist\history-ai-chat.exe" (
    echo Build successful!
    echo Output: dist\history-ai-chat.exe
    for %%I in (dist\history-ai-chat.exe) do echo Size: %%~zI bytes
) else (
    echo Build failed!
    exit /b 1
)