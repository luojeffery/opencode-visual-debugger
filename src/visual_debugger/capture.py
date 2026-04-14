"""Screenshot and video capture — cross-platform.

Linux: ImageMagick import + ffmpeg x11grab
Windows: mss (or Pillow ImageGrab) + ffmpeg gdigrab
"""
import subprocess
import os
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass


@dataclass
class CaptureResult:
    path: str
    format: str  # "png" or "mp4"
    size_bytes: int
    duration: float | None = None  # seconds, for video only


class BaseCaptureEngine(ABC):
    """Abstract capture engine interface."""

    def __init__(self, output_dir: str | None = None):
        self.output_dir = Path(output_dir or self._default_output_dir())
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _default_output_dir(self) -> str:
        if sys.platform == "win32":
            return os.path.join(os.environ.get("TEMP", "C:\\Temp"), "visual-debugger")
        return "/tmp/visual-debugger"

    @abstractmethod
    def screenshot(self, window_id: str, filename: str | None = None) -> CaptureResult:
        """Capture screenshot of a window."""

    @abstractmethod
    def record_clip(self, window_id: str, duration: int = 5,
                    framerate: int = 30, filename: str | None = None) -> CaptureResult:
        """Record video clip of a window."""

    @abstractmethod
    def get_window_geometry(self, window_id: str) -> tuple[int, int, int, int]:
        """Get window position and size: (x, y, width, height)."""

    def extract_frames(self, video_path: str, mode: str = "scene",
                       fps: int = 1, threshold: float = 0.3) -> list[str]:
        """Extract key frames from video. Works on both platforms (ffmpeg)."""
        frames_dir = self.output_dir / f"frames_{int(time.time() * 1000)}"
        frames_dir.mkdir(exist_ok=True)

        if mode == "scene":
            vf = f"select='gt(scene\\,{threshold})',setpts=N/FRAME_RATE/TB"
        else:
            vf = f"fps={fps}"

        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", vf,
            "-vsync", "vfr",
            str(frames_dir / "frame_%04d.png")
        ]

        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return sorted(str(f) for f in frames_dir.glob("frame_*.png"))


class LinuxCaptureEngine(BaseCaptureEngine):
    """Capture engine using ImageMagick + ffmpeg x11grab (Linux/X11)."""

    def __init__(self, display: str | None = None, output_dir: str | None = None):
        super().__init__(output_dir)
        self.display = display or os.environ.get("DISPLAY", ":0")

    @property
    def env(self) -> dict:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        return env

    def get_window_geometry(self, window_id: str) -> tuple[int, int, int, int]:
        geo_result = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", window_id],
            capture_output=True, text=True, env=self.env
        )
        geo = {"X": 0, "Y": 0, "WIDTH": 0, "HEIGHT": 0}
        if geo_result.returncode == 0:
            for line in geo_result.stdout.strip().split('\n'):
                if '=' in line:
                    k, v = line.split('=', 1)
                    if k in geo:
                        geo[k] = int(v)
        return (geo["X"], geo["Y"], geo["WIDTH"], geo["HEIGHT"])

    def screenshot(self, window_id: str, filename: str | None = None) -> CaptureResult:
        if not filename:
            filename = f"screenshot_{int(time.time() * 1000)}.png"
        output_path = self.output_dir / filename

        cmd = ["import", "-window", window_id, str(output_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=10)

        if result.returncode != 0:
            raise RuntimeError(f"Screenshot failed: {result.stderr}")
        if not output_path.exists():
            raise RuntimeError(f"Screenshot file not created at {output_path}")

        return CaptureResult(
            path=str(output_path), format="png",
            size_bytes=output_path.stat().st_size
        )

    def record_clip(self, window_id: str, duration: int = 5,
                    framerate: int = 30, filename: str | None = None) -> CaptureResult:
        if not filename:
            filename = f"clip_{int(time.time() * 1000)}.mp4"
        output_path = self.output_dir / filename

        x, y, w, h = self.get_window_geometry(window_id)

        cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab",
            "-framerate", str(framerate),
            "-video_size", f"{w}x{h}",
            "-i", f"{self.display}+{x},{y}",
            "-t", str(duration),
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True,
                                env=self.env, timeout=duration + 30)

        if result.returncode != 0:
            raise RuntimeError(f"Recording failed: {result.stderr}")
        if not output_path.exists():
            raise RuntimeError(f"Recording file not created at {output_path}")

        return CaptureResult(
            path=str(output_path), format="mp4",
            size_bytes=output_path.stat().st_size, duration=duration
        )


class WindowsCaptureEngine(BaseCaptureEngine):
    """Capture engine using mss + ffmpeg gdigrab (Windows)."""

    def __init__(self, output_dir: str | None = None):
        super().__init__(output_dir)

    def get_window_geometry(self, window_id: str) -> tuple[int, int, int, int]:
        import ctypes
        from ctypes import wintypes
        hwnd = int(window_id)
        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        x, y = rect.left, rect.top
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        return (x, y, w, h)

    def screenshot(self, window_id: str, filename: str | None = None) -> CaptureResult:
        import mss
        from PIL import Image

        if not filename:
            filename = f"screenshot_{int(time.time() * 1000)}.png"
        output_path = self.output_dir / filename

        x, y, w, h = self.get_window_geometry(window_id)
        monitor = {"left": x, "top": y, "width": w, "height": h}

        with mss.mss() as sct:
            img = sct.grab(monitor)
            Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX").save(str(output_path))

        if not output_path.exists():
            raise RuntimeError(f"Screenshot file not created at {output_path}")

        return CaptureResult(
            path=str(output_path), format="png",
            size_bytes=output_path.stat().st_size
        )

    def record_clip(self, window_id: str, duration: int = 5,
                    framerate: int = 30, filename: str | None = None) -> CaptureResult:
        if not filename:
            filename = f"clip_{int(time.time() * 1000)}.mp4"
        output_path = self.output_dir / filename

        # Get window title for gdigrab
        import ctypes
        hwnd = int(window_id)
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, title_buf, length + 1)
        window_title = title_buf.value

        cmd = [
            "ffmpeg", "-y",
            "-f", "gdigrab",
            "-framerate", str(framerate),
            "-i", f"title={window_title}",
            "-t", str(duration),
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 30)

        if result.returncode != 0:
            raise RuntimeError(f"Recording failed: {result.stderr}")
        if not output_path.exists():
            raise RuntimeError(f"Recording file not created at {output_path}")

        return CaptureResult(
            path=str(output_path), format="mp4",
            size_bytes=output_path.stat().st_size, duration=duration
        )


def create_capture_engine(**kwargs) -> BaseCaptureEngine:
    """Create the appropriate CaptureEngine for the current platform."""
    if sys.platform == "win32":
        return WindowsCaptureEngine(output_dir=kwargs.get("output_dir"))
    else:
        return LinuxCaptureEngine(
            display=kwargs.get("display"),
            output_dir=kwargs.get("output_dir")
        )


# Backwards compatibility
CaptureEngine = LinuxCaptureEngine
