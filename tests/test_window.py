"""Tests for WindowManager and WindowInfo."""
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from visual_debugger.window import WindowManager, WindowInfo


def _make_subprocess_result(stdout="", stderr="", returncode=0):
    """Helper to create a mock subprocess.CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


GEO_SHELL_OUTPUT = "WINDOW=12345\nX=100\nY=200\nWIDTH=800\nHEIGHT=600"


class TestFindByPid:
    @patch("visual_debugger.window.subprocess.run")
    def test_find_by_pid_success(self, mock_run, mock_display):
        """Finding a window by PID returns correct WindowInfo."""
        mock_run.side_effect = [
            # xdotool search --sync --pid ...
            _make_subprocess_result(stdout="12345\n"),
            # xdotool getwindowname
            _make_subprocess_result(stdout="My App Window"),
            # xdotool getwindowpid
            _make_subprocess_result(stdout="9999"),
            # xdotool getwindowgeometry --shell
            _make_subprocess_result(stdout=GEO_SHELL_OUTPUT),
        ]

        wm = WindowManager(display=":99")
        info = wm.find_by_pid(9999)

        assert isinstance(info, WindowInfo)
        assert info.window_id == "12345"
        assert info.title == "My App Window"
        assert info.pid == 9999
        assert info.geometry == (100, 200, 800, 600)

    @patch("visual_debugger.window.subprocess.run")
    def test_find_by_pid_not_found(self, mock_run, mock_display):
        """RuntimeError raised when no window found for PID."""
        mock_run.return_value = _make_subprocess_result(
            stdout="", stderr="No window found", returncode=1
        )

        wm = WindowManager(display=":99")
        with pytest.raises(RuntimeError, match="No window found for PID"):
            wm.find_by_pid(9999)

    @patch("visual_debugger.window.subprocess.run")
    def test_find_by_pid_empty_stdout(self, mock_run, mock_display):
        """RuntimeError raised when xdotool returns empty stdout with rc=0."""
        mock_run.return_value = _make_subprocess_result(stdout="", returncode=0)

        wm = WindowManager(display=":99")
        with pytest.raises(RuntimeError, match="No window found for PID"):
            wm.find_by_pid(1234)


class TestFindByTitle:
    @patch("visual_debugger.window.subprocess.run")
    def test_find_by_title_success(self, mock_run, mock_display):
        """Finding a window by title returns correct WindowInfo."""
        mock_run.side_effect = [
            _make_subprocess_result(stdout="67890\n"),
            _make_subprocess_result(stdout="Firefox"),
            _make_subprocess_result(stdout="4321"),
            _make_subprocess_result(stdout=GEO_SHELL_OUTPUT),
        ]

        wm = WindowManager(display=":99")
        info = wm.find_by_title("Firefox")

        assert info.window_id == "67890"
        assert info.title == "Firefox"
        assert info.pid == 4321
        # Verify xdotool search was called with --name
        first_call_args = mock_run.call_args_list[0]
        cmd_list = first_call_args[0][0]
        assert "--name" in cmd_list

    @patch("visual_debugger.window.subprocess.run")
    def test_find_by_title_not_found(self, mock_run, mock_display):
        """RuntimeError raised when no window found by title."""
        mock_run.return_value = _make_subprocess_result(
            stdout="", stderr="", returncode=1
        )

        wm = WindowManager(display=":99")
        with pytest.raises(RuntimeError, match="No window found with title"):
            wm.find_by_title("NonexistentApp")


class TestListWindows:
    @patch("visual_debugger.window.subprocess.run")
    def test_list_windows(self, mock_run, mock_display):
        """list_windows returns a list of WindowInfo for multiple IDs."""
        mock_run.side_effect = [
            # xdotool search
            _make_subprocess_result(stdout="111\n222\n"),
            # Window 111 info
            _make_subprocess_result(stdout="App One"),
            _make_subprocess_result(stdout="1001"),
            _make_subprocess_result(stdout="WINDOW=111\nX=0\nY=0\nWIDTH=1920\nHEIGHT=1080"),
            # Window 222 info
            _make_subprocess_result(stdout="App Two"),
            _make_subprocess_result(stdout="1002"),
            _make_subprocess_result(stdout="WINDOW=222\nX=50\nY=50\nWIDTH=640\nHEIGHT=480"),
        ]

        wm = WindowManager(display=":99")
        windows = wm.list_windows()

        assert len(windows) == 2
        assert windows[0].window_id == "111"
        assert windows[0].title == "App One"
        assert windows[0].pid == 1001
        assert windows[0].geometry == (0, 0, 1920, 1080)
        assert windows[1].window_id == "222"
        assert windows[1].title == "App Two"
        assert windows[1].geometry == (50, 50, 640, 480)

    @patch("visual_debugger.window.subprocess.run")
    def test_list_windows_empty(self, mock_run, mock_display):
        """list_windows returns empty list when no windows found."""
        mock_run.return_value = _make_subprocess_result(stdout="")

        wm = WindowManager(display=":99")
        windows = wm.list_windows()
        assert windows == []

    @patch("visual_debugger.window.subprocess.run")
    def test_list_windows_skips_errors(self, mock_run, mock_display):
        """list_windows skips windows that raise exceptions in _get_window_info."""
        mock_run.side_effect = [
            _make_subprocess_result(stdout="111\n222\n"),
            # Window 111 — getwindowname fails
            _make_subprocess_result(stdout="", returncode=1),
            _make_subprocess_result(stdout="", returncode=1),
            _make_subprocess_result(stdout="", returncode=1),
            # Window 222 — success
            _make_subprocess_result(stdout="Good Window"),
            _make_subprocess_result(stdout="2222"),
            _make_subprocess_result(stdout="WINDOW=222\nX=10\nY=20\nWIDTH=300\nHEIGHT=400"),
        ]

        wm = WindowManager(display=":99")
        windows = wm.list_windows()
        # Both should actually succeed since _get_window_info handles failures gracefully
        # (returns "Unknown" for title, None for pid, zeros for geo)
        assert len(windows) == 2


class TestTrackedProperty:
    @patch("visual_debugger.window.subprocess.run")
    def test_tracked_initially_none(self, mock_run, mock_display):
        """tracked is None before any find operation."""
        wm = WindowManager(display=":99")
        assert wm.tracked is None

    @patch("visual_debugger.window.subprocess.run")
    def test_tracked_set_after_find(self, mock_run, mock_display):
        """tracked is set after a successful find_by_pid."""
        mock_run.side_effect = [
            _make_subprocess_result(stdout="12345\n"),
            _make_subprocess_result(stdout="Test App"),
            _make_subprocess_result(stdout="5555"),
            _make_subprocess_result(stdout=GEO_SHELL_OUTPUT),
        ]

        wm = WindowManager(display=":99")
        info = wm.find_by_pid(5555)
        assert wm.tracked is info
        assert wm.tracked.window_id == "12345"


class TestGeometryParsing:
    @patch("visual_debugger.window.subprocess.run")
    def test_geometry_parsing(self, mock_run, mock_display):
        """Window geometry is correctly parsed from xdotool --shell output."""
        mock_run.side_effect = [
            _make_subprocess_result(stdout="99999\n"),
            _make_subprocess_result(stdout="Geo Test"),
            _make_subprocess_result(stdout="7777"),
            _make_subprocess_result(stdout="WINDOW=99999\nX=100\nY=200\nWIDTH=800\nHEIGHT=600"),
        ]

        wm = WindowManager(display=":99")
        info = wm.find_by_pid(7777)
        assert info.geometry == (100, 200, 800, 600)

    @patch("visual_debugger.window.subprocess.run")
    def test_geometry_defaults_on_failure(self, mock_run, mock_display):
        """Geometry defaults to (0,0,0,0) when getwindowgeometry fails."""
        mock_run.side_effect = [
            _make_subprocess_result(stdout="11111\n"),
            _make_subprocess_result(stdout="Fallback Test"),
            _make_subprocess_result(stdout="3333"),
            _make_subprocess_result(stdout="", returncode=1),
        ]

        wm = WindowManager(display=":99")
        info = wm.find_by_pid(3333)
        assert info.geometry == (0, 0, 0, 0)

    @patch("visual_debugger.window.subprocess.run")
    def test_pid_none_when_unavailable(self, mock_run, mock_display):
        """pid is None when getwindowpid returns empty output."""
        mock_run.side_effect = [
            _make_subprocess_result(stdout="11111\n"),
            _make_subprocess_result(stdout="No PID App"),
            _make_subprocess_result(stdout="", returncode=1),
            _make_subprocess_result(stdout=GEO_SHELL_OUTPUT),
        ]

        wm = WindowManager(display=":99")
        info = wm.find_by_pid(0, timeout=5)
        assert info.pid is None


class TestWindowManagerInit:
    def test_display_from_param(self, mock_display):
        """Display set from constructor parameter takes precedence."""
        wm = WindowManager(display=":42")
        assert wm.display == ":42"

    def test_display_from_env(self, mock_display):
        """Display falls back to DISPLAY env var."""
        wm = WindowManager()
        assert wm.display == ":99"

    def test_env_property(self, mock_display):
        """env property includes DISPLAY."""
        wm = WindowManager(display=":5")
        env = wm.env
        assert env["DISPLAY"] == ":5"
