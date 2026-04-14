"""MCP Server for visual debugging of graphics applications."""
import sys
from mcp.server.fastmcp import FastMCP
from visual_debugger.window import create_window_manager
from visual_debugger.capture import create_capture_engine
from visual_debugger.analyzer import create_analyzer
import json

mcp = FastMCP(
    "visual-debugger",
    instructions="Visual debugging MCP server for graphics/OpenGL applications. "
                 "Captures screenshots and video of running windows for AI analysis. "
                 f"Platform: {sys.platform}"
)

# Global state — auto-detects platform (Linux/Windows)
_wm = create_window_manager()
_capture = create_capture_engine()
_analyzer = create_analyzer()


@mcp.tool()
def watch_window(
    title: str | None = None,
    pid: int | None = None,
    timeout: int = 10
) -> str:
    """Find and start tracking a window by title or PID.
    
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
    """List all visible windows. Useful to discover available windows
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
    the screenshot with a VLM (local model or Gemini API).
    
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
        
        if prompt != "" and _analyzer.available:
            try:
                analysis = _analyzer.analyze_image(result.path, prompt=prompt or None)
                response["analysis"] = analysis
            except Exception as e:
                response["analysis_error"] = str(e)
        elif not _analyzer.available:
            response["note"] = "No VLM configured. Set VLM_MODEL_ID or GEMINI_API_KEY for analysis."
        
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
            response["note"] = "No VLM configured. Set VLM_MODEL_ID or GEMINI_API_KEY for analysis."
        
        return json.dumps(response)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def analyze_visual(
    mode: str = "screenshot",
    prompt: str | None = None,
) -> str:
    """Capture and analyze the tracked window with a Vision Language Model.
    
    Combines capture + analysis in one call. Requires either a local VLM
    (VLM_MODEL_ID) or Gemini API key (GEMINI_API_KEY).
    
    Args:
        mode: "screenshot" for single frame, "video" for 5-second clip
        prompt: Custom analysis prompt (default: visual debugging prompt)
    
    Returns:
        JSON with VLM analysis results
    """
    if not _wm.tracked:
        return json.dumps({"error": "No window tracked. Call watch_window first."})
    
    if not _analyzer.available:
        return json.dumps({"error": "No VLM configured. Set VLM_MODEL_ID for local model or GEMINI_API_KEY for Gemini."})
    
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
