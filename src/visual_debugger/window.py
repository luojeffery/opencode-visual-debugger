"""Window detection and tracking via xdotool."""
import subprocess
import shlex
import os
from dataclasses import dataclass


@dataclass
class WindowInfo:
    window_id: str
    title: str
    pid: int | None
    geometry: tuple[int, int, int, int]  # x, y, w, h


class WindowManager:
    def __init__(self, display: str | None = None):
        self.display = display or os.environ.get("DISPLAY", ":0")
        self._tracked: WindowInfo | None = None

    @property
    def env(self) -> dict:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        return env

    def find_by_pid(self, pid: int, timeout: int = 10) -> WindowInfo:
        """Find window by process ID. Waits up to timeout seconds."""
        cmd = f"xdotool search --sync --pid {pid} --onlyvisible"
        result = subprocess.run(
            shlex.split(cmd), capture_output=True, text=True,
            env=self.env, timeout=timeout + 5
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(f"No window found for PID {pid}: {result.stderr}")
        window_id = result.stdout.strip().split('\n')[0]
        return self._get_window_info(window_id)

    def find_by_title(self, title: str, timeout: int = 10) -> WindowInfo:
        """Find window by title substring. Waits up to timeout seconds."""
        cmd = f"xdotool search --sync --name {shlex.quote(title)}"
        result = subprocess.run(
            shlex.split(cmd), capture_output=True, text=True,
            env=self.env, timeout=timeout + 5
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(f"No window found with title '{title}': {result.stderr}")
        window_id = result.stdout.strip().split('\n')[0]
        return self._get_window_info(window_id)

    def list_windows(self) -> list[WindowInfo]:
        """List all visible windows."""
        cmd = "xdotool search --onlyvisible --name ''"
        result = subprocess.run(
            shlex.split(cmd), capture_output=True, text=True, env=self.env
        )
        windows = []
        for wid in result.stdout.strip().split('\n'):
            if wid:
                try:
                    windows.append(self._get_window_info(wid))
                except Exception:
                    continue
        return windows

    def _get_window_info(self, window_id: str) -> WindowInfo:
        """Get detailed info about a window."""
        name_result = subprocess.run(
            ["xdotool", "getwindowname", window_id],
            capture_output=True, text=True, env=self.env
        )
        title = name_result.stdout.strip() if name_result.returncode == 0 else "Unknown"

        pid_result = subprocess.run(
            ["xdotool", "getwindowpid", window_id],
            capture_output=True, text=True, env=self.env
        )
        pid = int(pid_result.stdout.strip()) if pid_result.returncode == 0 and pid_result.stdout.strip() else None

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

        info = WindowInfo(
            window_id=window_id,
            title=title,
            pid=pid,
            geometry=(geo["X"], geo["Y"], geo["WIDTH"], geo["HEIGHT"])
        )
        self._tracked = info
        return info

    @property
    def tracked(self) -> WindowInfo | None:
        return self._tracked
