"""应用图标定位：开发目录、打包目录和 PyInstaller 临时目录都能找到。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _roots() -> list[Path]:
    roots: list[Path] = []
    env = str(os.environ.get("QQCHATBOT_ICON") or "").strip()
    if env:
        p = Path(env).expanduser()
        roots.append(p if p.is_dir() else p.parent)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        roots.append(exe_dir)
        roots.append(exe_dir / "_internal")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass))
    try:
        roots.append(Path(__file__).resolve().parents[2])
    except IndexError:
        pass
    roots.append(Path.cwd())
    return roots


def icon_path(ext: str = "ico") -> Path | None:
    """返回可用的图标路径；优先指定格式，找不到再退回其它格式。"""
    names = [f"icon.{ext}"]
    names += [n for n in ("icon.ico", "icon.png", "icon.PNG") if n not in names]
    for root in _roots():
        try:
            for name in names:
                for candidate in (root / "assets" / name, root / name):
                    if candidate.is_file():
                        return candidate
        except OSError:
            continue
    return None


def load_tray_image(size: int = 64):
    """读取图标并缩放成托盘尺寸；失败返回 None，由调用方绘制兜底图。"""
    try:
        from PIL import Image

        path = icon_path()
        if path is None:
            return None
        with Image.open(path) as img:
            img = img.convert("RGBA")
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.paste(
                img,
                ((size - img.width) // 2, (size - img.height) // 2),
                img,
            )
            return canvas
    except Exception:
        return None
