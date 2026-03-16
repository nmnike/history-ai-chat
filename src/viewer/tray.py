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