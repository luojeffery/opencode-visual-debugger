# 🔍 Visual Debug MCP Server

**See your running graphics apps through AI eyes.**

An MCP (Model Context Protocol) server that lets AI coding agents visually debug graphics applications — OpenGL, GLFW, SDL, or any X11 windowed program. It captures screenshots and video clips of running windows and optionally analyzes them with a Vision Language Model (Google Gemini).

> **The problem:** AI coding agents can write graphics code but can't *see* the result. When a physics simulation has objects clipping through walls, or a shader produces wrong colors, the agent has no way to know without you describing the bug manually.
>
> **The solution:** This MCP server gives your AI agent eyes. It watches your app's window, captures what's on screen, and can even analyze the visuals automatically.

## ✨ Features

- **🪟 Window Tracking** — Find and track windows by PID or title via `xdotool`
- **📸 Screenshot Capture** — Instant window screenshots via ImageMagick
- **🎬 Video Recording** — Record clips with ffmpeg (x11grab), configurable duration/framerate
- **🧠 VLM Analysis** — Optional Gemini-powered visual analysis of captures
- **🔌 MCP Protocol** — Works with any MCP-compatible agent (OpenCode, Claude Code, Cline, etc.)
- **🚫 Non-invasive** — No render loop modification needed. Purely external observation.

## 📋 Prerequisites

- **Linux with X11** (Wayland not yet supported)
- **Python 3.10+**
- **System packages:**
  ```bash
  sudo apt install xdotool imagemagick ffmpeg
  ```

## 🚀 Installation

```bash
# Clone the repo
git clone https://github.com/luojeffery/opencode-visual-debugger.git
cd opencode-visual-debugger

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
```

## ⚙️ Configuration

### MCP Client Configuration

Add to your MCP client's config (e.g. `~/.config/opencode/config.yaml`, `claude_desktop_config.json`, etc.):

**For stdio transport (recommended):**

```json
{
  "mcpServers": {
    "visual-debugger": {
      "command": "/path/to/opencode-visual-debugger/.venv/bin/visual-debugger",
      "args": ["serve"],
      "env": {
        "DISPLAY": ":0",
        "GEMINI_API_KEY": "your-key-here"
      }
    }
  }
}
```

**For OpenCode (`~/.config/opencode/config.yaml`):**

```yaml
mcpServers:
  visual-debugger:
    command: /path/to/opencode-visual-debugger/.venv/bin/visual-debugger
    args:
      - serve
    env:
      DISPLAY: ":0"
      GEMINI_API_KEY: "your-key-here"
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISPLAY` | Yes | X11 display (usually `:0`) |
| `GEMINI_API_KEY` | No | Google Gemini API key for visual analysis. Without it, capture still works but analysis is disabled. |

## 🛠️ MCP Tools

### `list_windows`
List all visible X11 windows. Use this to discover what's running.

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
analyze_visual(mode="screenshot")                      # Analyze a screenshot
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
│   ├── window.py          # Window detection via xdotool
│   ├── capture.py         # Screenshot & video capture
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

- [ ] Wayland support (via `wlr-screencopy` or PipeWire)
- [ ] Diff-based change detection (only analyze when visuals change)
- [ ] Multi-window tracking
- [ ] Frame-by-frame stepping integration
- [ ] Support for additional VLM providers (OpenAI, Anthropic)

## 📄 License

MIT
