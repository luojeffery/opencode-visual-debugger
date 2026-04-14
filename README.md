# 🔍 Visual Debug MCP Server

**See your running graphics apps through AI eyes.**

An MCP (Model Context Protocol) server that lets AI coding agents visually debug graphics applications — OpenGL, GLFW, SDL, or any windowed program. It captures screenshots and video clips of running windows and optionally analyzes them with a Vision Language Model (Google Gemini).

**Works on Linux and Windows.**

> **The problem:** AI coding agents can write graphics code but can't *see* the result. When a physics simulation has objects clipping through walls, or a shader produces wrong colors, the agent has no way to know without you describing the bug manually.
>
> **The solution:** This MCP server gives your AI agent eyes. It watches your app's window, captures what's on screen, and can even analyze the visuals automatically.

## ✨ Features

- **🪟 Window Tracking** — Find and track windows by PID or title
- **📸 Screenshot Capture** — Instant window screenshots
- **🎬 Video Recording** — Record clips with configurable duration/framerate
- **🧠 VLM Analysis** — Optional Gemini-powered visual analysis of captures
- **🔌 MCP Protocol** — Works with any MCP-compatible agent (OpenCode, Claude Code, Cline, Cursor, VS Code Copilot)
- **🚫 Non-invasive** — No render loop modification needed. Purely external observation.
- **🖥️ Cross-platform** — Linux (X11) and Windows support

## 📋 Prerequisites

### Linux
```bash
sudo apt install xdotool imagemagick ffmpeg
```

### Windows
- **Python 3.10+**
- **ffmpeg** — Download from [ffmpeg.org](https://ffmpeg.org/download.html), extract, and add the `bin/` folder to your PATH. Or install via [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/): `winget install ffmpeg`
- That's it! Window capture uses native Windows APIs (no extra tools needed)

## 🚀 Installation

### Quick install (from GitHub)

**Linux / macOS:**
```bash
pip install git+https://github.com/luojeffery/opencode-visual-debugger.git
```

**Windows:**
```bash
pip install "visual-debugger-mcp[windows] @ git+https://github.com/luojeffery/opencode-visual-debugger.git"
```

### From source

```bash
git clone https://github.com/luojeffery/opencode-visual-debugger.git
cd opencode-visual-debugger
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -e ".[dev]"
```

## ⚙️ MCP Configuration

Add the server to your AI coding agent's MCP config:

### VS Code Copilot (`.vscode/mcp.json`)

```json
{
  "servers": {
    "visual-debugger": {
      "type": "stdio",
      "command": "visual-debugger",
      "args": ["serve"],
      "env": {
        "DISPLAY": ":0",
        "GEMINI_API_KEY": "your-key-here"
      }
    }
  }
}
```

### OpenCode (`~/.config/opencode/config.yaml`)

```yaml
mcpServers:
  visual-debugger:
    command: visual-debugger
    args: ["serve"]
    env:
      DISPLAY: ":0"
      GEMINI_API_KEY: "your-key-here"
```

### Claude Code (`~/.claude.json`)

```json
{
  "mcpServers": {
    "visual-debugger": {
      "command": "visual-debugger",
      "args": ["serve"],
      "env": {
        "DISPLAY": ":0",
        "GEMINI_API_KEY": "your-key-here"
      }
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "visual-debugger": {
      "command": "visual-debugger",
      "args": ["serve"],
      "env": {
        "GEMINI_API_KEY": "your-key-here"
      }
    }
  }
}
```

> **Note:** On Linux, include `"DISPLAY": ":0"` in env. On Windows, omit it — not needed.

> **Note:** `GEMINI_API_KEY` is optional. Without it, capture still works but VLM analysis is disabled.

## 🛠️ MCP Tools

### `list_windows`
List all visible windows. Use this to discover what's running.

### `watch_window`
Start tracking a specific window by title or PID.

```
watch_window(title="My OpenGL App")
watch_window(pid=12345)
```

### `capture_screenshot`
Take a screenshot of the tracked window. Optionally analyze with VLM.

```
capture_screenshot()                              # Capture + auto-analyze
capture_screenshot(prompt="Is the cube red?")     # Custom analysis prompt
capture_screenshot(prompt="")                     # Capture only, no analysis
```

### `record_clip`
Record a video clip of the tracked window.

```
record_clip()                      # 5-second clip at 30fps
record_clip(duration=10)           # 10-second clip
record_clip(duration=3, fps=60)    # 3 seconds at 60fps
```

### `analyze_visual`
One-shot capture + VLM analysis.

```
analyze_visual(mode="screenshot")                        # Analyze a screenshot
analyze_visual(mode="video", prompt="Is it flickering?") # Analyze video
```

## 💡 Example Workflow

Here's how an AI coding agent would use this to debug a bouncing ball simulation:

```
Agent: I'll compile and run the simulation, then check if it looks right.

1. terminal("./bouncing_ball &")          → PID 54321
2. watch_window(pid=54321)                → Tracking "Bouncing Ball Sim" (800x600)
3. capture_screenshot()                   → Analysis: "A red circle at the bottom
                                             of the screen. It appears to be
                                             partially below the floor boundary."
4. // Agent recognizes the collision bug, fixes the code
5. terminal("./bouncing_ball &")          → PID 54322
6. watch_window(pid=54322)
7. record_clip(duration=3)                → Analysis: "A red circle bounces
                                             smoothly off the floor, gaining
                                             height with each bounce. No clipping."
```

## 🏗️ Architecture

```
server.py / analyzer.py       ← platform-agnostic
        ↓
window.py   → LinuxWindowManager     (xdotool)
            → WindowsWindowManager   (ctypes + user32.dll)

capture.py  → LinuxCaptureEngine     (ImageMagick + ffmpeg x11grab)
            → WindowsCaptureEngine   (mss + ffmpeg gdigrab)
```

The platform is auto-detected at startup. Linux uses X11 tools, Windows uses native Win32 APIs.

## 🧪 Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## 📁 Project Structure

```
opencode-visual-debugger/
├── pyproject.toml
├── src/visual_debugger/
│   ├── __init__.py        # Package metadata
│   ├── server.py          # MCP server with tool definitions
│   ├── cli.py             # Click CLI (visual-debugger serve)
│   ├── window.py          # Window detection (Linux + Windows)
│   ├── capture.py         # Screenshot & video capture (Linux + Windows)
│   └── analyzer.py        # VLM analysis via Google Gemini
├── tests/
│   ├── conftest.py
│   ├── test_window.py
│   ├── test_capture.py
│   └── test_analyzer.py
└── docs/plans/
    └── implementation-plan.md
```

## 🗺️ Roadmap

- [ ] macOS support (screencapture + CoreGraphics)
- [ ] Wayland support (wlr-screencopy / PipeWire)
- [ ] Diff-based change detection (only analyze when visuals change)
- [ ] Background monitoring mode
- [ ] Multi-window tracking
- [ ] Support for additional VLM providers (OpenAI, Anthropic)
- [ ] Publish to PyPI for `uvx` one-liner install

## 📄 License

MIT
