# src/viewer/desktop.py
"""Desktop application entry point with tray icon"""
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

# Setup logging to file for debugging
log_file = Path(sys.argv[0]).parent / "history-ai-chat.log"


def log(msg: str):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


log("=" * 50)
log("Starting application")

# Ensure src is in path for PyInstaller
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    import uvicorn
    log("uvicorn imported")
except Exception as e:
    log(f"Failed to import uvicorn: {e}\n{traceback.format_exc()}")

try:
    from viewer.tray import TrayApp
    log("TrayApp imported")
except Exception as e:
    log(f"Failed to import TrayApp: {e}\n{traceback.format_exc()}")


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
    log(f"run_server() called, port={port}")
    try:
        uvicorn.run(
            "viewer.main:app",
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
            log_config=None,  # Disable logging to avoid console issues in PyInstaller
        )
    except Exception as e:
        log(f"uvicorn.run failed: {e}\n{traceback.format_exc()}")


def wait_for_server(port: int, timeout: float = 10.0) -> bool:
    """Wait for server to be ready"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def main():
    """Main entry point for desktop application"""
    log("main() called")
    port = 6300

    try:
        # Start server in background thread
        server_thread = threading.Thread(
            target=run_server,
            args=(port,),
            daemon=True
        )
        server_thread.start()
        log("Server thread started")

        # Wait for server to be ready
        if not wait_for_server(port):
            log("Failed to start server")
            return

        log("Server is ready")

        # Small delay to ensure server is fully ready
        time.sleep(0.2)

        # Open browser
        log(f"Opening browser http://127.0.0.1:{port}")
        webbrowser.open(f"http://127.0.0.1:{port}")

        # Create and run tray app
        def on_exit():
            log("Exit callback called")

        log("Creating tray app")
        tray = TrayApp(port=port, on_exit=on_exit)
        log("Running tray app")
        tray.run()
        log("Tray app finished")
    except Exception as e:
        log(f"Error in main: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()