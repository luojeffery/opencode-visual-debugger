"""Tests for VisionAnalyzer / analyzer module."""
import os
from unittest.mock import patch, MagicMock
import pytest

from visual_debugger.analyzer import (
    GeminiAnalyzer, LocalAnalyzer, create_analyzer, VisionAnalyzer,
    DEFAULT_IMAGE_PROMPT, DEFAULT_VIDEO_PROMPT, DEFAULT_FRAMES_PROMPT,
)


# ── GeminiAnalyzer tests ──────────────────────────────────────────────

class TestGeminiAvailability:
    def test_available_without_key(self, monkeypatch):
        """available is False when no API key is set."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = GeminiAnalyzer()
        assert analyzer.available is False

    def test_available_with_key(self, monkeypatch):
        """available is True when GEMINI_API_KEY is set."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        analyzer = GeminiAnalyzer()
        assert analyzer.available is True

    def test_available_with_explicit_key(self, monkeypatch):
        """available is True when key passed directly."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = GeminiAnalyzer(api_key="explicit-key")
        assert analyzer.available is True

    def test_explicit_key_overrides_env(self, monkeypatch):
        """Explicit key takes precedence over env var."""
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        analyzer = GeminiAnalyzer(api_key="explicit-key")
        assert analyzer.api_key == "explicit-key"


class TestGeminiAnalyzeImageErrors:
    def test_analyze_image_no_key(self, monkeypatch):
        """RuntimeError raised when no API key is available."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = GeminiAnalyzer()
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY not set"):
            analyzer.analyze_image("/tmp/test.png")

    def test_analyze_image_file_not_found(self, monkeypatch, tmp_path):
        """FileNotFoundError raised for nonexistent image path."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = GeminiAnalyzer()
        analyzer._client = MagicMock()

        nonexistent = str(tmp_path / "nonexistent.png")
        with pytest.raises(FileNotFoundError, match="Image not found"):
            analyzer.analyze_image(nonexistent)


class TestGeminiAnalyzeVideoErrors:
    def test_analyze_video_no_key(self, monkeypatch):
        """RuntimeError raised when no API key for video analysis."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = GeminiAnalyzer()
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY not set"):
            analyzer.analyze_video("/tmp/test.mp4")

    def test_analyze_video_file_not_found(self, monkeypatch, tmp_path):
        """FileNotFoundError raised for nonexistent video path."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = GeminiAnalyzer()
        analyzer._client = MagicMock()

        nonexistent = str(tmp_path / "nonexistent.mp4")
        with pytest.raises(FileNotFoundError, match="Video not found"):
            analyzer.analyze_video(nonexistent)


class TestGeminiAnalyzeImageSuccess:
    def test_analyze_image_with_mock_client(self, monkeypatch, tmp_path):
        """analyze_image calls Gemini API and returns text response."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = GeminiAnalyzer()

        image_file = tmp_path / "test_image.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

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
        analyzer = GeminiAnalyzer()

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
        parts = contents[0]["parts"]
        assert parts[0]["text"] == custom_prompt


class TestGeminiAnalyzeVideoSuccess:
    def test_analyze_video_with_mock_client(self, monkeypatch, tmp_path):
        """analyze_video uploads file and calls Gemini API."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = GeminiAnalyzer()

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


class TestGeminiAnalyzeFrames:
    def test_analyze_frames_with_mock_client(self, monkeypatch, tmp_path):
        """analyze_frames sends multiple images to Gemini."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = GeminiAnalyzer()

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
        assert len(parts) == 3
        assert parts[0]["text"]
        assert "inline_data" in parts[1]
        assert "inline_data" in parts[2]

    def test_analyze_frames_no_key(self, monkeypatch):
        """RuntimeError raised when no API key for frames analysis."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = GeminiAnalyzer()
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY not set"):
            analyzer.analyze_frames(["/tmp/f1.png"])


class TestGeminiGetClient:
    def test_get_client_caches(self, monkeypatch):
        """_get_client reuses existing client instance."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = GeminiAnalyzer()
        mock_client = MagicMock()
        analyzer._client = mock_client

        client = analyzer._get_client()
        assert client is mock_client

    def test_model_default(self, monkeypatch):
        """Default model is gemini-2.5-flash."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = GeminiAnalyzer()
        assert analyzer.model == "gemini-2.5-flash"

    def test_model_custom(self, monkeypatch):
        """Custom model can be specified."""
        analyzer = GeminiAnalyzer(model="gemini-2.0-flash")
        assert analyzer.model == "gemini-2.0-flash"


# ── LocalAnalyzer tests ──────────────────────────────────────────────

class TestLocalAnalyzerAvailability:
    def test_available_with_default(self):
        """LocalAnalyzer is always available (defaults to Molmo2-4B)."""
        analyzer = LocalAnalyzer()
        assert analyzer.available is True
        assert analyzer.model_id == "allenai/Molmo2-4B"

    def test_available_with_env(self, monkeypatch):
        """LocalAnalyzer uses VLM_MODEL_ID from env."""
        monkeypatch.setenv("VLM_MODEL_ID", "allenai/Molmo2-8B")
        analyzer = LocalAnalyzer()
        assert analyzer.model_id == "allenai/Molmo2-8B"

    def test_available_with_explicit_id(self):
        """LocalAnalyzer uses explicitly passed model_id."""
        analyzer = LocalAnalyzer(model_id="allenai/Molmo2-8B")
        assert analyzer.model_id == "allenai/Molmo2-8B"

    def test_not_available_with_empty_string(self):
        """LocalAnalyzer is unavailable if model_id is empty."""
        analyzer = LocalAnalyzer(model_id="")
        assert analyzer.available is False


class TestLocalAnalyzerErrors:
    def test_analyze_image_file_not_found(self, tmp_path):
        """FileNotFoundError raised for nonexistent image path."""
        analyzer = LocalAnalyzer()
        nonexistent = str(tmp_path / "nonexistent.png")
        with pytest.raises(FileNotFoundError, match="Image not found"):
            analyzer.analyze_image(nonexistent)

    def test_analyze_video_file_not_found(self, tmp_path):
        """FileNotFoundError raised for nonexistent video path."""
        analyzer = LocalAnalyzer()
        nonexistent = str(tmp_path / "nonexistent.mp4")
        with pytest.raises(FileNotFoundError, match="Video not found"):
            analyzer.analyze_video(nonexistent)

    def test_analyze_frames_file_not_found(self, tmp_path):
        """FileNotFoundError raised for nonexistent frame path."""
        analyzer = LocalAnalyzer()
        nonexistent = str(tmp_path / "nonexistent.png")
        with pytest.raises(FileNotFoundError, match="Frame not found"):
            analyzer.analyze_frames([nonexistent])


class TestLocalAnalyzerSuccess:
    def test_analyze_image_with_mock_model(self, tmp_path):
        """analyze_image loads model and returns generated text."""
        analyzer = LocalAnalyzer(model_id="test/model")

        image_file = tmp_path / "test.png"
        image_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        # Mock the model and processor
        mock_processor = MagicMock()
        mock_model = MagicMock()

        # Mock apply_chat_template return
        mock_input_ids = MagicMock()
        mock_input_ids.size.return_value = 10
        mock_inputs = {"input_ids": mock_input_ids}
        mock_processor.apply_chat_template.return_value = mock_inputs

        # Mock generate return — use a simple MagicMock instead of real torch tensor
        mock_generated_ids = MagicMock()
        mock_generated_ids.__getitem__ = MagicMock(return_value=MagicMock())
        mock_model.generate.return_value = mock_generated_ids
        mock_model.device = "cpu"

        # Mock tokenizer decode
        mock_processor.tokenizer.decode.return_value = "I see a blue sphere."

        analyzer._model = mock_model
        analyzer._processor = mock_processor

        # Mock torch.inference_mode
        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock(return_value=False))
        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = analyzer.analyze_image(str(image_file))

        assert result == "I see a blue sphere."
        mock_processor.apply_chat_template.assert_called_once()

    def test_analyze_video_with_mock_model(self, tmp_path):
        """analyze_video builds correct messages with video type."""
        analyzer = LocalAnalyzer(model_id="test/model")

        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"\x00" * 500)

        mock_processor = MagicMock()
        mock_model = MagicMock()

        mock_input_ids = MagicMock()
        mock_input_ids.size.return_value = 10
        mock_inputs = {"input_ids": mock_input_ids}
        mock_processor.apply_chat_template.return_value = mock_inputs

        mock_generated_ids = MagicMock()
        mock_generated_ids.__getitem__ = MagicMock(return_value=MagicMock())
        mock_model.generate.return_value = mock_generated_ids
        mock_model.device = "cpu"
        mock_processor.tokenizer.decode.return_value = "The animation looks smooth."

        analyzer._model = mock_model
        analyzer._processor = mock_processor

        mock_torch = MagicMock()
        mock_torch.inference_mode.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock(return_value=False))
        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = analyzer.analyze_video(str(video_file))

        assert result == "The animation looks smooth."

        # Verify the messages contain video type
        call_args = mock_processor.apply_chat_template.call_args
        messages = call_args[0][0]
        content = messages[0]["content"]
        assert any(c.get("type") == "video" for c in content)


# ── Factory tests ──────────────────────────────────────────────────

class TestCreateAnalyzer:
    def test_auto_local_with_env(self, monkeypatch):
        """Auto-detect returns LocalAnalyzer when VLM_MODEL_ID is set."""
        monkeypatch.setenv("VLM_MODEL_ID", "allenai/Molmo2-4B")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = create_analyzer()
        assert isinstance(analyzer, LocalAnalyzer)

    def test_auto_gemini_with_env(self, monkeypatch):
        """Auto-detect returns GeminiAnalyzer when GEMINI_API_KEY is set."""
        monkeypatch.delenv("VLM_MODEL_ID", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = create_analyzer()
        assert isinstance(analyzer, GeminiAnalyzer)

    def test_auto_local_priority_over_gemini(self, monkeypatch):
        """VLM_MODEL_ID takes priority over GEMINI_API_KEY."""
        monkeypatch.setenv("VLM_MODEL_ID", "allenai/Molmo2-4B")
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        analyzer = create_analyzer()
        assert isinstance(analyzer, LocalAnalyzer)

    def test_auto_default_local(self, monkeypatch):
        """Defaults to LocalAnalyzer when neither env var is set."""
        monkeypatch.delenv("VLM_MODEL_ID", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        analyzer = create_analyzer()
        assert isinstance(analyzer, LocalAnalyzer)

    def test_explicit_local(self, monkeypatch):
        """Explicit backend='local' returns LocalAnalyzer."""
        monkeypatch.delenv("VLM_MODEL_ID", raising=False)
        analyzer = create_analyzer(backend="local", model_id="test/model")
        assert isinstance(analyzer, LocalAnalyzer)
        assert analyzer.model_id == "test/model"

    def test_explicit_gemini(self, monkeypatch):
        """Explicit backend='gemini' returns GeminiAnalyzer."""
        analyzer = create_analyzer(backend="gemini", api_key="test-key")
        assert isinstance(analyzer, GeminiAnalyzer)
        assert analyzer.api_key == "test-key"


# ── Backwards compatibility ─────────────────────────────────────────

class TestBackwardsCompat:
    def test_vision_analyzer_alias(self):
        """VisionAnalyzer is aliased to GeminiAnalyzer for backwards compat."""
        assert VisionAnalyzer is GeminiAnalyzer
