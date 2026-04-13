"""Screenshot and video capture for X11 windows."""
import subprocess
import os
import time
from pathlib import Path
from dataclasses import dataclass


@dataclass
class CaptureResult:
    path: str
    format: str  # "png" or "mp4"
    size_bytes: int
    duration: float | None = None  # seconds, for video only


class CaptureEngine:
    def __init__(self, display: str | None = None, output_dir: str | None = None):
        self.display = display or os.environ.get("DISPLAY", ":0")
        self.output_dir = Path(output_dir or "/tmp/visual-debugger")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def env(self) -> dict:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        return env

    def screenshot(self, window_id: str, filename: str | None = None) -> CaptureResult:
        """Capture screenshot of a window using ImageMagick import."""
        if not filename:
            filename = f"screenshot_{int(time.time() * 1000)}.png"

        output_path = self.output_dir / filename

        cmd = [
            "import", "-window", window_id,
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=10)

        if result.returncode != 0:
            raise RuntimeError(f"Screenshot failed: {result.stderr}")

        if not output_path.exists():
            raise RuntimeError(f"Screenshot file not created at {output_path}")

        return CaptureResult(
            path=str(output_path),
            format="png",
            size_bytes=output_path.stat().st_size
        )

    def record_clip(self, window_id: str, duration: int = 5,
                    framerate: int = 30, filename: str | None = None) -> CaptureResult:
        """Record video clip of a window using ffmpeg x11grab."""
        if not filename:
            filename = f"clip_{int(time.time() * 1000)}.mp4"

        output_path = self.output_dir / filename

        # Get window geometry for ffmpeg
        geo_result = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", window_id],
            capture_output=True, text=True, env=self.env
        )
        geo = {}
        for line in geo_result.stdout.strip().split('\n'):
            if '=' in line:
                k, v = line.split('=', 1)
                geo[k] = v

        x, y = geo.get("X", "0"), geo.get("Y", "0")
        w, h = geo.get("WIDTH", "1280"), geo.get("HEIGHT", "720")

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

        result = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=duration + 30)

        if result.returncode != 0:
            raise RuntimeError(f"Recording failed: {result.stderr}")

        if not output_path.exists():
            raise RuntimeError(f"Recording file not created at {output_path}")

        return CaptureResult(
            path=str(output_path),
            format="mp4",
            size_bytes=output_path.stat().st_size,
            duration=duration
        )

    def extract_frames(self, video_path: str, mode: str = "scene",
                       fps: int = 1, threshold: float = 0.3) -> list[str]:
        """Extract key frames from video.

        mode: 'scene' for scene-change detection, 'uniform' for fixed FPS sampling
        """
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

        subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=60)

        frames = sorted(str(f) for f in frames_dir.glob("frame_*.png"))
        return frames
