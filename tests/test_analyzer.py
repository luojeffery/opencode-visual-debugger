"""Tests for VisionAnalyzer."""
import os
from unittest.mock import patch, MagicMock
import pytest

from visual_debugger.analyzer import VisionAnalyzer


class TestAvailability:
    def test_available_without_key(self, monkeypatch):
        """available is False when no API key is set."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = VisionAnalyzer()
        assert analyzer.available is False

    def test_available_with_key(self, monkeypatch):
        """available is True when GEMINI_API_KEY is set."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        analyzer = VisionAnalyzer()
        assert analyzer.available is True

    def test_available_with_explicit_key(self, monkeypatch):
        """available is True when key passed directly."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = VisionAnalyzer(api_key="explicit-key")
        assert analyzer.available is True

    def test_explicit_key_overrides_env(self, monkeypatch):
        """Explicit key takes precedence over env var."""
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        analyzer = VisionAnalyzer(api_key="explicit-key")
        assert analyzer.api_key == "explicit-key"


class TestAnalyzeImageErrors:
    def test_analyze_image_no_key(self, monkeypatch):
        """RuntimeError raised when no API key is available."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = VisionAnalyzer()
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY not set"):
            analyzer.analyze_image("/tmp/test.png")

    def test_analyze_image_file_not_found(self, monkeypatch, tmp_path):
        """FileNotFoundError raised for nonexistent image path."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = VisionAnalyzer()

        # Mock google.genai so _get_client doesn't actually import it
        mock_client = MagicMock()
        analyzer._client = mock_client

        nonexistent = str(tmp_path / "nonexistent.png")
        with pytest.raises(FileNotFoundError, match="Image not found"):
            analyzer.analyze_image(nonexistent)


class TestAnalyzeVideoErrors:
    def test_analyze_video_no_key(self, monkeypatch):
        """RuntimeError raised when no API key for video analysis."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = VisionAnalyzer()
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY not set"):
            analyzer.analyze_video("/tmp/test.mp4")

    def test_analyze_video_file_not_found(self, monkeypatch, tmp_path):
        """FileNotFoundError raised for nonexistent video path."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = VisionAnalyzer()
        analyzer._client = MagicMock()

        nonexistent = str(tmp_path / "nonexistent.mp4")
        with pytest.raises(FileNotFoundError, match="Video not found"):
            analyzer.analyze_video(nonexistent)


class TestAnalyzeImageSuccess:
    def test_analyze_image_with_mock_client(self, monkeypatch, tmp_path):
        """analyze_image calls Gemini API and returns text response."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = VisionAnalyzer()

        # Create a real image file
        image_file = tmp_path / "test_image.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        # Mock the client
        mock_response = MagicMock()
        mock_response.text = "I see a window with a blue background and a button."
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        analyzer._client = mock_client

        result = analyzer.analyze_image(str(image_file))

        assert result == "I see a window with a blue background and a button."
        mock_client.models.generate_content.assert_called_once()

    def test_analyze_image_custom_prompt(self, monkeypatch, tmp_path):
        """analyze_image uses custom prompt when provided."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = VisionAnalyzer()

        image_file = tmp_path / "test.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        mock_response = MagicMock()
        mock_response.text = "Custom analysis result"
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        analyzer._client = mock_client

        custom_prompt = "Count the number of buttons"
        result = analyzer.analyze_image(str(image_file), prompt=custom_prompt)

        assert result == "Custom analysis result"
        call_args = mock_client.models.generate_content.call_args
        contents = call_args[1]["contents"]
        # The prompt should be in the parts
        parts = contents[0]["parts"]
        assert parts[0]["text"] == custom_prompt


class TestAnalyzeVideoSuccess:
    def test_analyze_video_with_mock_client(self, monkeypatch, tmp_path):
        """analyze_video uploads file and calls Gemini API."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = VisionAnalyzer()

        video_file = tmp_path / "test_clip.mp4"
        video_file.write_bytes(b"\x00" * 500)

        mock_uploaded = MagicMock()
        mock_uploaded.uri = "gs://test/video.mp4"
        mock_uploaded.mime_type = "video/mp4"

        mock_response = MagicMock()
        mock_response.text = "The video shows animation artifacts."

        mock_client = MagicMock()
        mock_client.files.upload.return_value = mock_uploaded
        mock_client.models.generate_content.return_value = mock_response
        analyzer._client = mock_client

        result = analyzer.analyze_video(str(video_file))

        assert result == "The video shows animation artifacts."
        mock_client.files.upload.assert_called_once()
        mock_client.models.generate_content.assert_called_once()


class TestAnalyzeFrames:
    def test_analyze_frames_with_mock_client(self, monkeypatch, tmp_path):
        """analyze_frames sends multiple images to Gemini."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = VisionAnalyzer()

        frame1 = tmp_path / "frame_0001.png"
        frame2 = tmp_path / "frame_0002.png"
        frame1.write_bytes(b"\x89PNG" + b"\x00" * 50)
        frame2.write_bytes(b"\x89PNG" + b"\x00" * 50)

        mock_response = MagicMock()
        mock_response.text = "Frame progression shows a color shift."
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        analyzer._client = mock_client

        result = analyzer.analyze_frames([str(frame1), str(frame2)])

        assert result == "Frame progression shows a color shift."
        call_args = mock_client.models.generate_content.call_args
        contents = call_args[1]["contents"]
        parts = contents[0]["parts"]
        # 1 text prompt + 2 inline_data parts
        assert len(parts) == 3
        assert parts[0]["text"]  # prompt
        assert "inline_data" in parts[1]
        assert "inline_data" in parts[2]

    def test_analyze_frames_no_key(self, monkeypatch):
        """RuntimeError raised when no API key for frames analysis."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = VisionAnalyzer()
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY not set"):
            analyzer.analyze_frames(["/tmp/f1.png"])


class TestGetClient:
    def test_get_client_caches(self, monkeypatch):
        """_get_client reuses existing client instance."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = VisionAnalyzer()
        mock_client = MagicMock()
        analyzer._client = mock_client

        client = analyzer._get_client()
        assert client is mock_client

    def test_model_default(self, monkeypatch):
        """Default model is gemini-2.5-flash."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = VisionAnalyzer()
        assert analyzer.model == "gemini-2.5-flash"

    def test_model_custom(self, monkeypatch):
        """Custom model can be specified."""
        analyzer = VisionAnalyzer(model="gemini-2.0-flash")
        assert analyzer.model == "gemini-2.0-flash"
