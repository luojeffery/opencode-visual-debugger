# 🔍 Visual Debug MCP Server

**See your running graphics apps through AI eyes.**

An MCP (Model Context Protocol) server that lets AI coding agents visually debug graphics applications — OpenGL, GLFW, SDL, or any windowed program. It captures screenshots and video clips of running windows and analyzes them with a Vision Language Model.

**Works on Linux and Windows. Supports local open-source VLMs (Molmo2) and Gemini API.**

> **The problem:** AI coding agents can write graphics code but can't *see* the result. When a physics simulation has objects clipping through walls, or a shader produces wrong colors, the agent has no way to know without you describing the bug manually.
>
> **The solution:** This MCP server gives your AI agent eyes. It watches your app's window, captures what's on screen, and analyzes the visuals with a VLM — either a free, open-source model running on your GPU, or a cloud API.

## ✨ Features

- **🪟 Window Tracking** — Find and track windows by PID or title
- **📸 Screenshot Capture** — Instant window screenshots
- **🎬 Video Recording** — Record clips with configurable duration/framerate
- **🧠 VLM Analysis** — Analyze captures with a local model or Gemini API
- **🆓 Local VLM** — Run [Molmo2-4B](https://huggingface.co/allenai/Molmo2-4B) on your own GPU — free, private, no API key needed
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

### For local VLM (optional)
- **NVIDIA GPU** with 4GB+ VRAM (RTX 3060 or better recommended)
- **CUDA** — Install from [nvidia.com/cuda](https://developer.nvidia.com/cuda-downloads)

## 🚀 Installation

### Quick install (from GitHub)

**Using Gemini API** (recommended — cheap, no GPU needed):
```bash
pip install "visual-debugger-mcp[gemini] @ git+https://github.com/luojeffery/opencode-visual-debugger.git"
```

**Using a local VLM** (free, private, requires NVIDIA GPU with 4GB+ VRAM):
```bash
pip install "visual-debugger-mcp[local] @ git+https://github.com/luojeffery/opencode-visual-debugger.git"
```

> Works on both Linux and Windows — no platform-specific extras needed.

### From source

```bash
git clone https://github.com/luojeffery/opencode-visual-debugger.git
cd opencode-visual-debugger
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -e ".[local,dev]"
```

## 🧠 VLM Setup

The server supports two VLM backends. **Gemini API is recommended** — it's cheap, fast, and requires no GPU.

### Option A: Gemini API (recommended)

Get a free API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

```bash
export GEMINI_API_KEY=your-key-here
```

**Pricing:** The free tier has daily limits. With billing enabled, costs are negligible:

| Model | Input | Output | Best for |
|-------|-------|--------|----------|
| `gemini-2.0-flash` | $0.10/M | $0.40/M | Fast, reliable (default) |
| `gemini-2.5-flash` | $0.15/M | $0.60/M | Smarter reasoning |
| `gemini-2.5-flash-lite` | $0.05/M | $0.30/M | Cheapest option |

A typical screenshot analysis costs **< $0.001**. A video clip analysis costs **< $0.01**.

To change the model, set `GEMINI_MODEL`:

```bash
export GEMINI_MODEL=gemini-2.0-flash   # default
```

### Option B: Local model (free, private, requires GPU)

Run an open-source VLM on your own GPU — no API keys, no cost, fully private.

Set `VLM_MODEL_ID` to a HuggingFace model. The model downloads automatically on first use (~8GB for Molmo2-4B).

```bash
export VLM_MODEL_ID=allenai/Molmo2-4B
```

**Supported models:**
| Model | VRAM | Quality |
|-------|------|---------|
| [allenai/Molmo2-4B](https://huggingface.co/allenai/Molmo2-4B) | ~4 GB | Good — fast, lightweight |
| [allenai/Molmo2-8B](https://huggingface.co/allenai/Molmo2-8B) | ~8 GB | Better — more detailed analysis |

Any HuggingFace vision model compatible with `AutoModelForImageTextToText` should work.

### Priority

If both `VLM_MODEL_ID` and `GEMINI_API_KEY` are set, the local model takes priority.

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

> **Tip:** For local VLM, replace `GEMINI_API_KEY` with `"VLM_MODEL_ID": "allenai/Molmo2-4B"`. The first run downloads model weights (~8GB), then caches them in `~/.cache/huggingface/`.

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
server.py                         ← MCP tools (platform-agnostic)
analyzer.py                       ← VLM dispatch
  → LocalAnalyzer                   (transformers + Molmo2/any HF model)
  → GeminiAnalyzer                  (Google Gemini API)

window.py                         ← Window management
  → LinuxWindowManager              (xdotool)
  → WindowsWindowManager            (ctypes + user32.dll)

capture.py                        ← Screenshot & video
  → LinuxCaptureEngine              (ImageMagick + ffmpeg x11grab)
  → WindowsCaptureEngine            (PrintWindow + ffmpeg rawvideo pipe)
```

Platform and VLM backend are auto-detected at startup.

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
│   └── analyzer.py        # VLM analysis (local + Gemini)
├── tests/
│   ├── conftest.py
│   ├── test_window.py
│   ├── test_capture.py
│   └── test_analyzer.py
└── docs/plans/
    └── implementation-plan.md
```

## 📄 License

MIT
