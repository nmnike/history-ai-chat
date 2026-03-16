# Desktop EXE Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create standalone Windows exe with tray icon for easy distribution.

**Architecture:** PyInstaller bundles Python runtime + FastAPI app + pystray tray module into single exe. On launch, starts uvicorn in background thread, shows tray icon, opens browser.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, pystray, Pillow, PyInstaller

---

## Task 1: Add Desktop Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

**Step 1: Add new dependencies to pyproject.toml**

Add to `dependencies` array:
```toml
    "pystray>=0.19.0",
    "Pillow>=10.0.0",
```

Add new optional-dependencies section for build:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.26.0",
]
build = [
    "pyinstaller>=6.0.0",
]
```

**Step 2: Update requirements.txt**

```
fastapi>=0.109.0
uvicorn>=0.27.0
jinja2>=3.1.0
pygments>=2.17.0
python-dateutil>=2.8.0
pystray>=0.19.0
Pillow>=10.0.0
```

**Step 3: Install new dependencies**

Run: `pip install -e ".[build]"`
Expected: Dependencies installed successfully

**Step 4: Commit**

```bash
git add pyproject.toml requirements.txt
git commit -m "feat: add pystray and pillow dependencies for desktop app"
```

---

## Task 2: Create Application Icon

**Files:**
- Create: `src/viewer/assets/icon.png`
- Create: `src/viewer/assets/icon.ico`

**Step 1: Create assets directory**

Run: `mkdir -p src/viewer/assets`

**Step 2: Create icon.png (placeholder - simple colored square)**

Use Python to generate a simple icon:
```python
from PIL import Image, ImageDraw

# Create 256x256 icon with gradient
img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Draw rounded rectangle with gradient-like effect
draw.rounded_rectangle([20, 20, 236, 236], radius=40, fill='#4A90D9')
draw.rounded_rectangle([40, 40, 216, 216], radius=30, fill='#2E5A8C')

# Add "HC" text (History Chat)
draw.text((70, 90), "HC", fill='white', font=None)

img.save('src/viewer/assets/icon.png')
img.save('src/viewer/assets/icon.ico', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
```

Run this script from project root.

**Step 3: Verify icons created**

Run: `ls -la src/viewer/assets/`
Expected: icon.png and icon.ico present

**Step 4: Commit**

```bash
git add src/viewer/assets/
git commit -m "feat: add application icons for desktop app"
```

---

## Task 3: Create Tray Module

**Files:**
- Create: `src/viewer/tray.py`

**Step 1: Create tray module**

```python
# src/viewer/tray.py
"""System tray icon for desktop application"""
import webbrowser
from typing import Callable, Optional

import pystray
from PIL import Image


class TrayApp:
    """System tray application controller"""

    def __init__(
        self,
        port: int = 6300,
        on_exit: Optional[Callable] = None
    ):
        self.port = port
        self.on_exit = on_exit
        self._icon: Optional[pystray.Icon] = None
        self._is_running = False

    def _create_icon_image(self) -> Image.Image:
        """Load icon image from assets or create default"""
        try:
            import importlib.resources
            icon_path = importlib.resources.files("viewer.assets") / "icon.png"
            with icon_path.open("rb") as f:
                return Image.open(f).resize((64, 64))
        except Exception:
            # Fallback: create simple colored circle
            img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.ellipse([4, 4, 60, 60], fill='#4A90D9')
            return img

    def _open_browser(self):
        """Open application URL in default browser"""
        webbrowser.open(f"http://127.0.0.1:{self.port}")

    def _exit_app(self, icon: pystray.Icon):
        """Stop the application"""
        self._is_running = False
        icon.stop()
        if self.on_exit:
            self.on_exit()

    def _create_menu(self) -> pystray.Menu:
        """Create tray context menu"""
        return pystray.Menu(
            pystray.MenuItem(
                "Open in Browser",
                lambda: self._open_browser(),
                default=True
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Exit",
                lambda icon: self._exit_app(icon)
            ),
        )

    def run(self):
        """Run the tray icon (blocking)"""
        self._is_running = True
        self._icon = pystray.Icon(
            "history_ai_chat",
            icon=self._create_icon_image(),
            title="History AI Chat",
            menu=self._create_menu()
        )
        self._icon.run()

    def stop(self):
        """Stop the tray icon"""
        self._is_running = False
        if self._icon:
            self._icon.stop()

    @property
    def is_running(self) -> bool:
        return self._is_running
```

**Step 2: Verify syntax**

Run: `python -m py_compile src/viewer/tray.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add src/viewer/tray.py
git commit -m "feat: add tray module with pystray integration"
```

---

## Task 4: Create Desktop Entry Point

**Files:**
- Create: `src/viewer/desktop.py`

**Step 1: Create desktop entry point**

```python
# src/viewer/desktop.py
"""Desktop application entry point with tray icon"""
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .tray import TrayApp


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder in _MEIPASS
        base_path = Path(sys._MEIPASS)  # type: ignore
    except AttributeError:
        base_path = Path(__file__).parent
    return base_path / relative_path


def run_server(port: int = 6300):
    """Run uvicorn server in current thread"""
    uvicorn.run(
        "viewer.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False
    )


def main():
    """Main entry point for desktop application"""
    port = 6300

    # Start server in background thread
    server_thread = threading.Thread(
        target=run_server,
        args=(port,),
        daemon=True
    )
    server_thread.start()

    # Wait for server to start
    time.sleep(0.5)

    # Open browser
    webbrowser.open(f"http://127.0.0.1:{port}")

    # Create and run tray app
    def on_exit():
        print("Shutting down...")

    tray = TrayApp(port=port, on_exit=on_exit)
    tray.run()


if __name__ == "__main__":
    main()
```

**Step 2: Verify syntax**

Run: `python -m py_compile src/viewer/desktop.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add src/viewer/desktop.py
git commit -m "feat: add desktop entry point with server and tray"
```

---

## Task 5: Update pyproject.toml Entry Point

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add desktop script entry point**

Change `[project.scripts]` section:
```toml
[project.scripts]
history-ai-chat = "viewer.cli:main"
history-ai-chat-desktop = "viewer.desktop:main"
```

**Step 2: Reinstall to register new entry point**

Run: `pip install -e .`
Expected: Successfully installed

**Step 3: Test entry point**

Run: `python -c "from viewer.desktop import main; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add desktop entry point to pyproject.toml"
```

---

## Task 6: Create PyInstaller Spec File

**Files:**
- Create: `build.spec`

**Step 1: Create spec file**

```python
# build.spec
"""PyInstaller spec file for History AI Chat Desktop"""
import sys
from pathlib import Path

# Get the src directory
src_dir = Path('src')

a = Analysis(
    ['src/viewer/desktop.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/viewer/static', 'viewer/static'),
        ('src/viewer/templates', 'viewer/templates'),
        ('src/viewer/assets', 'viewer/assets'),
    ],
    hiddenimports=[
        'viewer',
        'viewer.main',
        'viewer.tray',
        'viewer.parsers',
        'viewer.parsers.claude',
        'viewer.parsers.codex',
        'viewer.db',
        'viewer.db.cache',
        'pystray._win32',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='history-ai-chat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Enable UPX compression if available
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/viewer/assets/icon.ico',
)
```

**Step 2: Verify syntax**

Run: `python -m py_compile build.spec`
Expected: No output (success)

**Step 3: Commit**

```bash
git add build.spec
git commit -m "feat: add PyInstaller spec file for desktop build"
```

---

## Task 7: Create Build Script

**Files:**
- Create: `build.bat`

**Step 1: Create build script**

```batch
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
```

**Step 2: Commit**

```bash
git add build.bat
git commit -m "feat: add build script for desktop exe"
```

---

## Task 8: Create Assets Package Init

**Files:**
- Create: `src/viewer/assets/__init__.py`

**Step 1: Create init file**

```python
# src/viewer/assets/__init__.py
"""Assets package for icons and resources"""
```

**Step 2: Commit**

```bash
git add src/viewer/assets/__init__.py
git commit -m "feat: add assets package init"
```

---

## Task 9: Test Desktop App (Development Mode)

**Files:**
- Test: `src/viewer/desktop.py`

**Step 1: Run desktop app in development mode**

Run: `python -m viewer.desktop`
Expected:
- Browser opens at http://localhost:6300
- Tray icon appears in system tray
- Right-click tray shows menu

**Step 2: Test tray functionality**

- Click "Open in Browser" - should open/focus browser
- Click "Exit" - should close application

**Step 3: Stop the app**

If it doesn't stop cleanly, use Ctrl+C in terminal.

---

## Task 10: Build and Test EXE

**Files:**
- Build: `build.bat`

**Step 1: Run build**

Run: `build.bat`
Expected: Build completes, exe created at `dist\history-ai-chat.exe`

**Step 2: Test the exe**

Run: `dist\history-ai-chat.exe`
Expected:
- Browser opens automatically
- Tray icon appears
- Application works identically to dev mode

**Step 3: Verify exe size**

Run: `ls -la dist/history-ai-chat.exe`
Expected: ~45-80 MB

**Step 4: Test on clean machine (optional)**

Copy exe to another Windows machine without Python and run.

---

## Task 11: Update README

**Files:**
- Modify: `README.md`

**Step 1: Add desktop section**

Add after "## Usage" section:
```markdown
## Desktop Application

For Windows users without Python:

1. Download `history-ai-chat.exe` from [Releases](releases link)
2. Double-click to run
3. Browser opens automatically
4. Use tray icon to reopen or exit

### Building from Source

```cmd
pip install -e ".[build]"
build.bat
```

Output: `dist\history-ai-chat.exe`
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add desktop application instructions to README"
```

---

## Summary

| Task | Description | Estimated Time |
|------|-------------|----------------|
| 1 | Add dependencies | 2 min |
| 2 | Create icons | 3 min |
| 3 | Create tray module | 5 min |
| 4 | Create desktop entry point | 5 min |
| 5 | Update pyproject.toml | 2 min |
| 6 | Create PyInstaller spec | 5 min |
| 7 | Create build script | 2 min |
| 8 | Create assets init | 1 min |
| 9 | Test dev mode | 5 min |
| 10 | Build and test exe | 10 min |
| 11 | Update README | 3 min |

**Total: ~45 minutes**

---

## Files Changed Summary

**Created:**
- `src/viewer/assets/__init__.py`
- `src/viewer/assets/icon.png`
- `src/viewer/assets/icon.ico`
- `src/viewer/tray.py`
- `src/viewer/desktop.py`
- `build.spec`
- `build.bat`

**Modified:**
- `pyproject.toml`
- `requirements.txt`
- `README.md`