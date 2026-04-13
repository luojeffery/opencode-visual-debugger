# Visual Debug MCP Server — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build an MCP server that enables AI coding agents to visually debug graphics/OpenGL/GLFW applications by capturing screenshots and video clips of running X11 windows, with optional VLM analysis.

**Architecture:** A Python MCP server using FastMCP that exposes 4 tools: `watch_window`, `capture_screenshot`, `record_clip`, and `analyze_visual`. It uses xdotool for window detection, xwd/import for screenshots, ffmpeg for video recording, and Google Gemini for visual analysis. Purely non-invasive — no render loop modification.

**Tech Stack:** Python 3.12, FastMCP (MCP SDK), xdotool, ffmpeg, Pillow, google-genai (Gemini API), Click (CLI)

---

## Task 1: Project Setup — pyproject.toml, venv, dependencies

**Objective:** Create the Python project structure with proper packaging, virtual environment, and all dependencies installed.

**Files:**
- Create: `pyproject.toml`
- Create: `src/visual_debugger/__init__.py`
- Create: `README.md`
- Create: `.gitignore`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "visual-debugger-mcp"
version = "0.1.0"
description = "MCP server for visual debugging of graphics/OpenGL applications"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=1.0.0",
    "Pillow>=10.0.0",
    "click>=8.0.0",
    "google-genai>=1.0.0",
]

[project.scripts]
visual-debugger = "visual_debugger.cli:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```

**Step 2: Create .gitignore**

Standard Python gitignore + captures directory.

**Step 3: Create README.md**

Brief description, install instructions, usage.

**Step 4: Create src directory and __init__.py**

```python
# src/visual_debugger/__init__.py
"""Visual Debug MCP Server — see running graphics apps through AI eyes."""
__version__ = "0.1.0"
```

**Step 5: Create venv and install dependencies**

```bash
cd ~/GitHub/opencode-visual-debugger
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: project setup with pyproject.toml and dependencies"
```

---

## Task 2: Window Manager — xdotool wrapper for finding and tracking windows

**Objective:** Create the window management module that finds X11 windows by PID or title using xdotool.

**Files:**
- Create: `src/visual_debugger/window.py`
- Create: `tests/test_window.py`

**Implementation:**

`src/visual_debugger/window.py`:
```python
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
        # Get window name
        name_result = subprocess.run(
            ["xdotool", "getwindowname", window_id],
            capture_output=True, text=True, env=self.env
        )
        title = name_result.stdout.strip() if name_result.returncode == 0 else "Unknown"
        
        # Get window PID
        pid_result = subprocess.run(
            ["xdotool", "getwindowpid", window_id],
            capture_output=True, text=True, env=self.env
        )
        pid = int(pid_result.stdout.strip()) if pid_result.returncode == 0 and pid_result.stdout.strip() else None
        
        # Get window geometry
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
```

**Tests:** Unit tests that mock subprocess calls to verify find_by_pid, find_by_title, list_windows, and geometry parsing.

**Commit:**
```bash
git add -A && git commit -m "feat: window manager with xdotool-based detection"
```

---

## Task 3: Capture Module — screenshots and video recording

**Objective:** Create the capture module that takes screenshots (via `import` from ImageMagick) and records video clips (via ffmpeg).

**Files:**
- Create: `src/visual_debugger/capture.py`
- Create: `tests/test_capture.py`

**Implementation:**

`src/visual_debugger/capture.py`:
```python
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
```

**Commit:**
```bash
git add -A && git commit -m "feat: capture engine with screenshot and video recording"
```

---

## Task 4: Vision Analyzer — VLM integration with Gemini

**Objective:** Create the vision analysis module that sends screenshots/videos to Google Gemini for visual analysis.

**Files:**
- Create: `src/visual_debugger/analyzer.py`
- Create: `tests/test_analyzer.py`

**Implementation:**

`src/visual_debugger/analyzer.py`:
```python
"""Visual analysis via VLM (Google Gemini)."""
import base64
import os
from pathlib import Path

class VisionAnalyzer:
    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model
        self._client = None
    
    @property
    def available(self) -> bool:
        return bool(self.api_key)
    
    def _get_client(self):
        if not self._client:
            if not self.api_key:
                raise RuntimeError("GEMINI_API_KEY not set. Set it to enable visual analysis.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client
    
    def analyze_image(self, image_path: str, prompt: str | None = None) -> str:
        """Analyze a screenshot with Gemini."""
        client = self._get_client()
        
        if not prompt:
            prompt = (
                "You are a visual debugger for a graphics application. "
                "Describe what you see in this screenshot. Note any visual artifacts, "
                "rendering issues, incorrect colors, missing elements, or anything "
                "that looks like a bug. Be specific about positions and colors."
            )
        
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # Upload and analyze
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        response = client.models.generate_content(
            model=self.model,
            contents=[
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": f"image/{image_path.suffix.lstrip('.')}",
                                "data": base64.b64encode(image_data).decode()
                            }
                        }
                    ]
                }
            ]
        )
        
        return response.text
    
    def analyze_video(self, video_path: str, prompt: str | None = None) -> str:
        """Analyze a video clip with Gemini (native video support)."""
        client = self._get_client()
        
        if not prompt:
            prompt = (
                "You are a visual debugger for a graphics application. "
                "Watch this video clip and describe the behavior. Note any visual "
                "artifacts, physics bugs, rendering glitches, incorrect animations, "
                "or unexpected behavior. Be specific about timing and what changes."
            )
        
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        # Upload file for video
        uploaded = client.files.upload(file=video_path)
        
        response = client.models.generate_content(
            model=self.model,
            contents=[
                {
                    "parts": [
                        {"text": prompt},
                        {"file_data": {"file_uri": uploaded.uri, "mime_type": uploaded.mime_type}}
                    ]
                }
            ]
        )
        
        return response.text
    
    def analyze_frames(self, frame_paths: list[str], prompt: str | None = None) -> str:
        """Analyze a sequence of extracted frames."""
        client = self._get_client()
        
        if not prompt:
            prompt = (
                "You are a visual debugger. These are sequential frames from a graphics "
                "application. Describe the progression and note any visual bugs, "
                "artifacts, or unexpected changes between frames."
            )
        
        parts = [{"text": prompt}]
        for fp in frame_paths:
            with open(fp, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": data
                }
            })
        
        response = client.models.generate_content(
            model=self.model,
            contents=[{"parts": parts}]
        )
        
        return response.text
```

**Commit:**
```bash
git add -A && git commit -m "feat: vision analyzer with Gemini VLM integration"
```

---

## Task 5: MCP Server — FastMCP server exposing all 4 tools

**Objective:** Create the MCP server that exposes `watch_window`, `capture_screenshot`, `record_clip`, and `analyze_visual` as MCP tools.

**Files:**
- Create: `src/visual_debugger/server.py`

**Implementation:**

`src/visual_debugger/server.py`:
```python
"""MCP Server for visual debugging of graphics applications."""
from mcp.server.fastmcp import FastMCP
from visual_debugger.window import WindowManager
from visual_debugger.capture import CaptureEngine
from visual_debugger.analyzer import VisionAnalyzer
import json

mcp = FastMCP(
    "visual-debugger",
    description="Visual debugging MCP server for graphics/OpenGL applications. "
                "Captures screenshots and video of running windows for AI analysis."
)

# Global state
_wm = WindowManager()
_capture = CaptureEngine()
_analyzer = VisionAnalyzer()


@mcp.tool()
def watch_window(
    title: str | None = None,
    pid: int | None = None,
    timeout: int = 10
) -> str:
    """Find and start tracking an X11 window by title or PID.
    
    Use this first to select which window to debug. The agent typically knows
    the PID because it launched the process, or the title from the GLFW/SDL 
    window creation code.
    
    Args:
        title: Window title substring to search for (e.g. "My Physics Sim")
        pid: Process ID of the application
        timeout: Max seconds to wait for window to appear (default 10)
    
    Returns:
        JSON with window info: id, title, pid, geometry
    """
    if not title and not pid:
        return json.dumps({"error": "Provide either 'title' or 'pid' to find a window"})
    
    try:
        if pid:
            info = _wm.find_by_pid(pid, timeout=timeout)
        else:
            info = _wm.find_by_title(title, timeout=timeout)
        
        return json.dumps({
            "status": "tracking",
            "window_id": info.window_id,
            "title": info.title,
            "pid": info.pid,
            "geometry": {
                "x": info.geometry[0],
                "y": info.geometry[1],
                "width": info.geometry[2],
                "height": info.geometry[3]
            }
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def list_windows() -> str:
    """List all visible X11 windows. Useful to discover available windows
    before using watch_window.
    
    Returns:
        JSON array of window info objects
    """
    try:
        windows = _wm.list_windows()
        return json.dumps([
            {
                "window_id": w.window_id,
                "title": w.title,
                "pid": w.pid,
                "geometry": {
                    "x": w.geometry[0], "y": w.geometry[1],
                    "width": w.geometry[2], "height": w.geometry[3]
                }
            }
            for w in windows
        ])
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def capture_screenshot(prompt: str | None = None) -> str:
    """Capture a screenshot of the currently tracked window.
    
    Must call watch_window first to select a window. Optionally analyzes 
    the screenshot with a VLM if GEMINI_API_KEY is set.
    
    Args:
        prompt: Optional custom prompt for VLM analysis. If not provided,
                uses a default visual debugging prompt. Set to empty string
                to skip analysis and just capture.
    
    Returns:
        JSON with file path, size, and optional VLM analysis
    """
    if not _wm.tracked:
        return json.dumps({"error": "No window tracked. Call watch_window first."})
    
    try:
        result = _capture.screenshot(_wm.tracked.window_id)
        response = {
            "status": "captured",
            "path": result.path,
            "size_bytes": result.size_bytes,
            "format": result.format,
            "window": _wm.tracked.title
        }
        
        # Auto-analyze if VLM available and prompt isn't empty string
        if prompt != "" and _analyzer.available:
            try:
                analysis = _analyzer.analyze_image(result.path, prompt=prompt or None)
                response["analysis"] = analysis
            except Exception as e:
                response["analysis_error"] = str(e)
        elif not _analyzer.available:
            response["note"] = "Set GEMINI_API_KEY to enable automatic visual analysis"
        
        return json.dumps(response)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def record_clip(
    duration: int = 5,
    framerate: int = 30,
    prompt: str | None = None
) -> str:
    """Record a video clip of the currently tracked window.
    
    Must call watch_window first. Records for the specified duration
    and optionally analyzes with a VLM.
    
    Args:
        duration: Recording length in seconds (default 5, max 60)
        framerate: Video framerate (default 30)
        prompt: Optional custom prompt for VLM analysis
    
    Returns:
        JSON with file path, size, duration, and optional analysis
    """
    if not _wm.tracked:
        return json.dumps({"error": "No window tracked. Call watch_window first."})
    
    duration = min(duration, 60)
    
    try:
        result = _capture.record_clip(
            _wm.tracked.window_id,
            duration=duration,
            framerate=framerate
        )
        response = {
            "status": "recorded",
            "path": result.path,
            "size_bytes": result.size_bytes,
            "duration": result.duration,
            "format": result.format,
            "window": _wm.tracked.title
        }
        
        if prompt != "" and _analyzer.available:
            try:
                analysis = _analyzer.analyze_video(result.path, prompt=prompt or None)
                response["analysis"] = analysis
            except Exception as e:
                response["analysis_error"] = str(e)
        elif not _analyzer.available:
            response["note"] = "Set GEMINI_API_KEY to enable automatic visual analysis"
        
        return json.dumps(response)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def analyze_visual(
    mode: str = "screenshot",
    prompt: str | None = None,
    sampling: str = "scene",
    fps: int = 1
) -> str:
    """Capture and analyze the tracked window with a Vision Language Model.
    
    Combines capture + analysis in one call. For video mode, can extract 
    key frames using scene detection or uniform sampling.
    
    Args:
        mode: "screenshot" for single frame, "video" for 5-second clip
        prompt: Custom analysis prompt (default: visual debugging prompt)
        sampling: For video frame extraction — "scene" (detect changes) or "uniform" (fixed fps). 
                  Only used if sending frames instead of native video.
        fps: Frames per second for uniform sampling (default 1)
    
    Returns:
        JSON with VLM analysis results
    """
    if not _wm.tracked:
        return json.dumps({"error": "No window tracked. Call watch_window first."})
    
    if not _analyzer.available:
        return json.dumps({"error": "GEMINI_API_KEY not set. Cannot perform analysis."})
    
    try:
        if mode == "screenshot":
            cap = _capture.screenshot(_wm.tracked.window_id)
            analysis = _analyzer.analyze_image(cap.path, prompt=prompt)
        elif mode == "video":
            cap = _capture.record_clip(_wm.tracked.window_id, duration=5)
            analysis = _analyzer.analyze_video(cap.path, prompt=prompt)
        else:
            return json.dumps({"error": f"Unknown mode '{mode}'. Use 'screenshot' or 'video'."})
        
        return json.dumps({
            "status": "analyzed",
            "mode": mode,
            "capture_path": cap.path,
            "analysis": analysis,
            "window": _wm.tracked.title
        })
    except Exception as e:
        return json.dumps({"error": str(e)})
```

**Commit:**
```bash
git add -A && git commit -m "feat: MCP server with all 4 visual debugging tools"
```

---

## Task 6: CLI Entry Point — Click-based CLI for running the server

**Objective:** Create a CLI with `visual-debugger serve` command to start the MCP server.

**Files:**
- Create: `src/visual_debugger/cli.py`

**Implementation:**

```python
"""CLI for visual-debugger MCP server."""
import click
import sys

@click.group()
@click.version_option()
def main():
    """Visual Debug MCP Server — see running graphics apps through AI eyes."""
    pass

@main.command()
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio",
              help="MCP transport (default: stdio)")
@click.option("--display", default=None, help="X11 display (default: $DISPLAY or :0)")
@click.option("--output-dir", default=None, help="Directory for captures (default: /tmp/visual-debugger)")
def serve(transport, display, output_dir):
    """Start the MCP server."""
    from visual_debugger.server import mcp, _wm, _capture
    
    if display:
        _wm.display = display
        _capture.display = display
    if output_dir:
        from pathlib import Path
        _capture.output_dir = Path(output_dir)
        _capture.output_dir.mkdir(parents=True, exist_ok=True)
    
    click.echo(f"Starting visual-debugger MCP server (transport={transport})...", err=True)
    mcp.run(transport=transport)

if __name__ == "__main__":
    main()
```

**Commit:**
```bash
git add -A && git commit -m "feat: CLI entry point with serve command"
```

---

## Task 7: Tests — Unit tests with mocked subprocess calls

**Objective:** Write comprehensive unit tests for window manager and capture engine.

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_window.py`
- Create: `tests/test_capture.py`
- Create: `tests/conftest.py`

**Commit:**
```bash
git add -A && git commit -m "test: unit tests for window manager and capture engine"
```

---

## Task 8: README and Documentation

**Objective:** Write comprehensive README with install instructions, MCP config examples, and usage guide.

**Commit:**
```bash
git add -A && git commit -m "docs: comprehensive README with setup and usage guide"
```
