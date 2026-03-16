# History AI Chat Desktop - Design Document

**Date**: 2026-03-16
**Goal**: Create standalone Windows exe for distribution to other users

## Architecture

```
history-ai-chat.exe (PyInstaller bundle)
├── Python runtime
├── FastAPI app (existing code)
├── Tray icon (new module)
└── Static/Templates resources
```

## Runtime Flow

1. User launches `history-ai-chat.exe`
2. Hidden Python process starts FastAPI on localhost:6300
3. Tray icon appears in system tray
4. Browser automatically opens http://localhost:6300
5. User interacts via browser; tray provides control menu

## Components

### 1. Tray Module (`src/viewer/tray.py`)

- Library: `pystray`
- Features:
  - System tray icon
  - Menu: "Open in Browser", "Stop Server", "Exit"
  - Icon: embedded PNG/ICO

### 2. Entry Point (`src/viewer/desktop.py`)

- Starts uvicorn in background thread
- Initializes tray icon
- Handles graceful shutdown
- Auto-opens browser on start

### 3. Build Configuration (`build.spec`)

- PyInstaller options:
  - `--windowed` (no console)
  - `--onefile` (single exe)
  - `--add-data` for static/templates
  - Application icon

## Dependencies (New)

```
pystray>=0.19.0
Pillow>=10.0.0  # for pystray icon handling
pyinstaller>=6.0.0  # build-time only
```

## Expected Output

- Single exe file: ~45-60 MB
- No Python installation required on user machine
- Works offline

## User Experience

1. Download `history-ai-chat.exe`
2. Double-click to run
3. Browser opens automatically
4. Tray icon indicates running state
5. Tray menu: reopen browser, exit

## Non-Goals

- Auto-start on Windows boot (explicitly excluded)
- MSI installer (single exe preferred)
- Electron migration (PyInstaller chosen)