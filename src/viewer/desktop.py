# src/viewer/desktop.py
"""Desktop application entry point with tray icon"""
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Ensure src is in path for PyInstaller
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import uvicorn

from viewer.tray import TrayApp


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