"""System tray icon for the frozen build.

The packaged .exe runs windowless (frostgrave.spec, console=False), so once
the browser tab is closed there's normally no sign the app is still running
and no way to close it short of Task Manager. This gives it a tray icon with
an explicit Quit, plus a way to reopen the browser if it got closed by
mistake.
"""

from __future__ import annotations

import os
import webbrowser

from PIL import Image, ImageDraw

_BG = (23, 55, 94, 255)
_FG = (190, 225, 255, 255)


def _icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((3, 3, 61, 61), fill=_BG, outline=_FG, width=3)
    for x0, y0, x1, y1 in ((32, 10, 32, 54), (12, 32, 52, 32), (17, 17, 47, 47), (17, 47, 47, 17)):
        draw.line((x0, y0, x1, y1), fill=_FG, width=3)
    return img


def run(url: str) -> None:
    """Blocks on the tray icon's event loop until Quit is chosen. Call from the main thread."""
    import pystray

    def _open(_icon=None, _item=None) -> None:
        webbrowser.open(url)

    def _quit(icon, _item) -> None:
        icon.stop()
        os._exit(0)

    icon = pystray.Icon(
        "FrostgraveWarbandKeeper",
        _icon_image(),
        "Frostgrave Warband Keeper",
        menu=pystray.Menu(
            pystray.MenuItem("Open Warband Keeper", _open, default=True),
            pystray.MenuItem("Quit", _quit),
        ),
    )
    icon.run()
