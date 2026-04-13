"""Tests for CaptureEngine and CaptureResult."""
import subprocess
from unittest.mock import patch, MagicMock
import pytest

from visual_debugger.capture import CaptureEngine, CaptureResult


def _make_subprocess_result(stdout="", stderr="", returncode=0):
    """Helper to create a mock subprocess.CompletedProcess."""
    result = MagicMock(spec=subprocess.CompletedProcess)
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


GEO_SHELL_OUTPUT = "WINDOW=12345\nX=100\nY=200\nWIDTH=800\nHEIGHT=600"


class TestCaptureEngineInit:
    def test_output_dir_creation(self, tmp_path, mock_display):
        """CaptureEngine creates output_dir on initialization."""
        out = tmp_path / "captures" / "nested"
        engine = CaptureEngine(display=":99", output_dir=str(out))
        assert out.exists()
        assert out.is_dir()

    def test_default_display(self, mock_display):
        """Uses DISPLAY env var when no display parameter given."""
        engine = CaptureEngine(output_dir="/tmp/test-cap")
        assert engine.display == ":99"

    def test_explicit_display(self, mock_display):
        """Explicit display parameter overrides env."""
        engine = CaptureEngine(display=":42", output_dir="/tmp/test-cap")
        assert engine.display == ":42"


class TestScreenshot:
    @patch("visual_debugger.capture.subprocess.run")
    def test_screenshot_success(self, mock_run, tmp_path, mock_display):
        """Successful screenshot returns CaptureResult with correct fields."""
        out_dir = tmp_path / "screenshots"
        engine = CaptureEngine(display=":99", output_dir=str(out_dir))

        # Create the expected file so output_path.exists() passes
        expected_file = out_dir / "test_shot.png"
        expected_file.write_bytes(b"\x89PNG" + b"\x00" * 100)

        mock_run.return_value = _make_subprocess_result()

        result = engine.screenshot("12345", filename="test_shot.png")

        assert isinstance(result, CaptureResult)
        assert result.path == str(expected_file)
        assert result.format == "png"
        assert result.size_bytes == 104
        assert result.duration is None

        # Verify import command was called
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "import"
        assert "-window" in call_args
        assert "12345" in call_args

    @patch("visual_debugger.capture.subprocess.run")
    def test_screenshot_failure(self, mock_run, tmp_path, mock_display):
        """RuntimeError raised when import command fails."""
        engine = CaptureEngine(display=":99", output_dir=str(tmp_path))

        mock_run.return_value = _make_subprocess_result(
            stderr="import: unable to read X window", returncode=1
        )

        with pytest.raises(RuntimeError, match="Screenshot failed"):
            engine.screenshot("12345")

    @patch("visual_debugger.capture.subprocess.run")
    def test_screenshot_file_not_created(self, mock_run, tmp_path, mock_display):
        """RuntimeError raised when import succeeds but file not found."""
        engine = CaptureEngine(display=":99", output_dir=str(tmp_path))

        mock_run.return_value = _make_subprocess_result()

        with pytest.raises(RuntimeError, match="Screenshot file not created"):
            engine.screenshot("12345", filename="missing.png")

    @patch("visual_debugger.capture.subprocess.run")
    def test_screenshot_default_filename(self, mock_run, tmp_path, mock_display):
        """Default filename is auto-generated with timestamp."""
        engine = CaptureEngine(display=":99", output_dir=str(tmp_path))

        def side_effect(cmd, **kwargs):
            # Create the file that the auto-generated name would have
            # We need to extract the filename from the command
            output_path = cmd[-1]
            from pathlib import Path
            Path(output_path).write_bytes(b"\x89PNG" + b"\x00" * 50)
            return _make_subprocess_result()

        mock_run.side_effect = side_effect

        result = engine.screenshot("12345")
        assert result.format == "png"
        assert "screenshot_" in result.path
        assert result.path.endswith(".png")


class TestRecordClip:
    @patch("visual_debugger.capture.subprocess.run")
    def test_record_clip_success(self, mock_run, tmp_path, mock_display):
        """Successful recording returns CaptureResult with duration."""
        out_dir = tmp_path / "clips"
        engine = CaptureEngine(display=":99", output_dir=str(out_dir))

        expected_file = out_dir / "test_clip.mp4"
        expected_file.write_bytes(b"\x00" * 5000)

        mock_run.side_effect = [
            # xdotool getwindowgeometry --shell
            _make_subprocess_result(stdout=GEO_SHELL_OUTPUT),
            # ffmpeg
            _make_subprocess_result(),
        ]

        result = engine.record_clip("12345", duration=5, filename="test_clip.mp4")

        assert isinstance(result, CaptureResult)
        assert result.format == "mp4"
        assert result.duration == 5
        assert result.size_bytes == 5000
        assert result.path == str(expected_file)

    @patch("visual_debugger.capture.subprocess.run")
    def test_record_clip_failure(self, mock_run, tmp_path, mock_display):
        """RuntimeError raised when ffmpeg fails."""
        engine = CaptureEngine(display=":99", output_dir=str(tmp_path))

        mock_run.side_effect = [
            _make_subprocess_result(stdout=GEO_SHELL_OUTPUT),
            _make_subprocess_result(stderr="ffmpeg error", returncode=1),
        ]

        with pytest.raises(RuntimeError, match="Recording failed"):
            engine.record_clip("12345", duration=3, filename="fail.mp4")

    @patch("visual_debugger.capture.subprocess.run")
    def test_record_clip_uses_geometry(self, mock_run, tmp_path, mock_display):
        """ffmpeg command includes correct geometry from xdotool."""
        engine = CaptureEngine(display=":99", output_dir=str(tmp_path))

        clip_file = tmp_path / "geo_clip.mp4"
        clip_file.write_bytes(b"\x00" * 100)

        mock_run.side_effect = [
            _make_subprocess_result(stdout="WINDOW=12345\nX=50\nY=75\nWIDTH=1024\nHEIGHT=768"),
            _make_subprocess_result(),
        ]

        engine.record_clip("12345", duration=2, filename="geo_clip.mp4")

        ffmpeg_call = mock_run.call_args_list[1]
        ffmpeg_cmd = ffmpeg_call[0][0]
        assert "-video_size" in ffmpeg_cmd
        size_idx = ffmpeg_cmd.index("-video_size")
        assert ffmpeg_cmd[size_idx + 1] == "1024x768"

        input_idx = ffmpeg_cmd.index("-i")
        assert ":99+50,75" in ffmpeg_cmd[input_idx + 1]

    @patch("visual_debugger.capture.subprocess.run")
    def test_record_clip_file_not_created(self, mock_run, tmp_path, mock_display):
        """RuntimeError raised when ffmpeg succeeds but file doesn't exist."""
        engine = CaptureEngine(display=":99", output_dir=str(tmp_path))

        mock_run.side_effect = [
            _make_subprocess_result(stdout=GEO_SHELL_OUTPUT),
            _make_subprocess_result(),
        ]

        with pytest.raises(RuntimeError, match="Recording file not created"):
            engine.record_clip("12345", duration=2, filename="ghost.mp4")


class TestExtractFrames:
    @patch("visual_debugger.capture.subprocess.run")
    def test_extract_frames_scene_mode(self, mock_run, tmp_path, mock_display):
        """extract_frames in scene mode creates frame files and returns paths."""
        engine = CaptureEngine(display=":99", output_dir=str(tmp_path))

        def side_effect(cmd, **kwargs):
            # Create frame files in the frames directory
            output_pattern = cmd[-1]
            from pathlib import Path
            frames_dir = Path(output_pattern).parent
            frames_dir.mkdir(parents=True, exist_ok=True)
            (frames_dir / "frame_0001.png").write_bytes(b"\x89PNG")
            (frames_dir / "frame_0002.png").write_bytes(b"\x89PNG")
            return _make_subprocess_result()

        mock_run.side_effect = side_effect

        frames = engine.extract_frames("/tmp/video.mp4", mode="scene")
        assert len(frames) == 2
        assert all("frame_" in f for f in frames)

        # Check ffmpeg was called with scene filter
        ffmpeg_cmd = mock_run.call_args[0][0]
        vf_idx = ffmpeg_cmd.index("-vf")
        assert "scene" in ffmpeg_cmd[vf_idx + 1]

    @patch("visual_debugger.capture.subprocess.run")
    def test_extract_frames_uniform_mode(self, mock_run, tmp_path, mock_display):
        """extract_frames in uniform mode uses fps filter."""
        engine = CaptureEngine(display=":99", output_dir=str(tmp_path))

        def side_effect(cmd, **kwargs):
            from pathlib import Path
            output_pattern = cmd[-1]
            frames_dir = Path(output_pattern).parent
            frames_dir.mkdir(parents=True, exist_ok=True)
            (frames_dir / "frame_0001.png").write_bytes(b"\x89PNG")
            return _make_subprocess_result()

        mock_run.side_effect = side_effect

        frames = engine.extract_frames("/tmp/video.mp4", mode="uniform", fps=2)
        assert len(frames) == 1

        ffmpeg_cmd = mock_run.call_args[0][0]
        vf_idx = ffmpeg_cmd.index("-vf")
        assert "fps=2" in ffmpeg_cmd[vf_idx + 1]

    @patch("visual_debugger.capture.subprocess.run")
    def test_extract_frames_no_frames(self, mock_run, tmp_path, mock_display):
        """extract_frames returns empty list when no frames extracted."""
        engine = CaptureEngine(display=":99", output_dir=str(tmp_path))

        def side_effect(cmd, **kwargs):
            # Create the directory but no frames
            from pathlib import Path
            output_pattern = cmd[-1]
            frames_dir = Path(output_pattern).parent
            frames_dir.mkdir(parents=True, exist_ok=True)
            return _make_subprocess_result()

        mock_run.side_effect = side_effect

        frames = engine.extract_frames("/tmp/video.mp4")
        assert frames == []


class TestCaptureResult:
    def test_capture_result_dataclass(self):
        """CaptureResult stores all fields correctly."""
        r = CaptureResult(path="/tmp/test.png", format="png", size_bytes=1024)
        assert r.path == "/tmp/test.png"
        assert r.format == "png"
        assert r.size_bytes == 1024
        assert r.duration is None

    def test_capture_result_with_duration(self):
        """CaptureResult stores duration for video."""
        r = CaptureResult(path="/tmp/test.mp4", format="mp4", size_bytes=50000, duration=10.5)
        assert r.duration == 10.5
