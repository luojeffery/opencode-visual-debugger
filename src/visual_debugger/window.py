"""Window detection and tracking — cross-platform.

Linux: uses xdotool
Windows: uses ctypes + user32.dll (zero dependencies)
"""
import os
import sys
import subprocess
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class WindowInfo:
    window_id: str
    title: str
    pid: int | None
    geometry: tuple[int, int, int, int]  # x, y, w, h


class BaseWindowManager(ABC):
    """Abstract window manager interface."""

    def __init__(self):
        self._tracked: WindowInfo | None = None

    @abstractmethod
    def find_by_pid(self, pid: int, timeout: int = 10) -> WindowInfo:
        """Find window by process ID."""

    @abstractmethod
    def find_by_title(self, title: str, timeout: int = 10) -> WindowInfo:
        """Find window by title substring."""

    @abstractmethod
    def list_windows(self) -> list[WindowInfo]:
        """List all visible windows."""

    @property
    def tracked(self) -> WindowInfo | None:
        return self._tracked

    def _set_tracked(self, info: WindowInfo) -> WindowInfo:
        self._tracked = info
        return info


class LinuxWindowManager(BaseWindowManager):
    """Window manager using xdotool (Linux/X11)."""

    def __init__(self, display: str | None = None):
        super().__init__()
        self.display = display or os.environ.get("DISPLAY", ":0")

    @property
    def env(self) -> dict:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        return env

    def find_by_pid(self, pid: int, timeout: int = 10) -> WindowInfo:
        cmd = f"xdotool search --sync --pid {pid} --onlyvisible"
        result = subprocess.run(
            shlex.split(cmd), capture_output=True, text=True,
            env=self.env, timeout=timeout + 5
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(f"No window found for PID {pid}: {result.stderr}")
        window_id = result.stdout.strip().split('\n')[0]
        return self._set_tracked(self._get_window_info(window_id))

    def find_by_title(self, title: str, timeout: int = 10) -> WindowInfo:
        cmd = f"xdotool search --sync --name {shlex.quote(title)}"
        result = subprocess.run(
            shlex.split(cmd), capture_output=True, text=True,
            env=self.env, timeout=timeout + 5
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(f"No window found with title '{title}': {result.stderr}")
        window_id = result.stdout.strip().split('\n')[0]
        return self._set_tracked(self._get_window_info(window_id))

    def list_windows(self) -> list[WindowInfo]:
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

        return WindowInfo(
            window_id=window_id,
            title=title,
            pid=pid,
            geometry=(geo["X"], geo["Y"], geo["WIDTH"], geo["HEIGHT"])
        )


class WindowsWindowManager(BaseWindowManager):
    """Window manager using ctypes + user32.dll (Windows)."""

    def __init__(self):
        super().__init__()
        import ctypes
        from ctypes import wintypes
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

    def find_by_pid(self, pid: int, timeout: int = 10) -> WindowInfo:
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            windows = self._enum_windows()
            for w in windows:
                if w.pid == pid:
                    return self._set_tracked(w)
            time.sleep(0.5)
        raise RuntimeError(f"No window found for PID {pid}")

    def find_by_title(self, title: str, timeout: int = 10) -> WindowInfo:
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            windows = self._enum_windows()
            for w in windows:
                if title.lower() in w.title.lower():
                    return self._set_tracked(w)
            time.sleep(0.5)
        raise RuntimeError(f"No window found with title '{title}'")

    def list_windows(self) -> list[WindowInfo]:
        return self._enum_windows()

    def _enum_windows(self) -> list[WindowInfo]:
        import ctypes
        from ctypes import wintypes

        windows = []

        def callback(hwnd, _):
            if not self._user32.IsWindowVisible(hwnd):
                return True
            length = self._user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            title_buf = ctypes.create_unicode_buffer(length + 1)
            self._user32.GetWindowTextW(hwnd, title_buf, length + 1)
            title = title_buf.value

            # Get PID
            pid = wintypes.DWORD()
            self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            # Get geometry
            rect = wintypes.RECT()
            self._user32.GetWindowRect(hwnd, ctypes.byref(rect))
            x, y = rect.left, rect.top
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            windows.append(WindowInfo(
                window_id=str(hwnd),
                title=title,
                pid=pid.value,
                geometry=(x, y, w, h)
            ))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        self._user32.EnumWindows(WNDENUMPROC(callback), 0)
        return windows


def create_window_manager(**kwargs) -> BaseWindowManager:
    """Create the appropriate WindowManager for the current platform."""
    if sys.platform == "win32":
        return WindowsWindowManager()
    else:
        return LinuxWindowManager(**kwargs)


# Backwards compatibility
WindowManager = LinuxWindowManager
