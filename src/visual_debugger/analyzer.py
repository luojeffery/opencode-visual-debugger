"""Visual analysis via VLM — supports Gemini API and local models (e.g. Molmo2).

Backend selection:
- If VLM_MODEL_ID is set → use local HuggingFace model via transformers
- If GEMINI_API_KEY is set → use Gemini API
- If neither → analysis disabled (capture still works)
"""
import base64
import os
from abc import ABC, abstractmethod
from pathlib import Path


DEFAULT_IMAGE_PROMPT = (
    "You are a visual debugger for a graphics application. "
    "Describe what you see in this screenshot. Note any visual artifacts, "
    "rendering issues, incorrect colors, missing elements, or anything "
    "that looks like a bug. Be specific about positions and colors."
)

DEFAULT_VIDEO_PROMPT = (
    "You are a visual debugger for a graphics application. "
    "Watch this video clip and describe the behavior. Note any visual "
    "artifacts, physics bugs, rendering glitches, incorrect animations, "
    "or unexpected behavior. Be specific about timing and what changes."
)

DEFAULT_FRAMES_PROMPT = (
    "You are a visual debugger. These are sequential frames from a graphics "
    "application. Describe the progression and note any visual bugs, "
    "artifacts, or unexpected changes between frames."
)


class BaseAnalyzer(ABC):
    """Abstract VLM analyzer interface."""

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether this analyzer is ready to use."""

    @abstractmethod
    def analyze_image(self, image_path: str, prompt: str | None = None) -> str:
        """Analyze a screenshot."""

    @abstractmethod
    def analyze_video(self, video_path: str, prompt: str | None = None) -> str:
        """Analyze a video clip."""

    @abstractmethod
    def analyze_frames(self, frame_paths: list[str], prompt: str | None = None) -> str:
        """Analyze a sequence of extracted frames."""


class GeminiAnalyzer(BaseAnalyzer):
    """VLM analyzer using Google Gemini API."""

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
                raise RuntimeError("GEMINI_API_KEY not set. Set it to enable Gemini analysis.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def analyze_image(self, image_path: str, prompt: str | None = None) -> str:
        client = self._get_client()
        prompt = prompt or DEFAULT_IMAGE_PROMPT

        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path, "rb") as f:
            image_data = f.read()

        response = client.models.generate_content(
            model=self.model,
            contents=[{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {
                        "mime_type": f"image/{image_path.suffix.lstrip('.')}",
                        "data": base64.b64encode(image_data).decode()
                    }}
                ]
            }]
        )
        return response.text

    def analyze_video(self, video_path: str, prompt: str | None = None) -> str:
        client = self._get_client()
        prompt = prompt or DEFAULT_VIDEO_PROMPT

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        uploaded = client.files.upload(file=video_path)
        response = client.models.generate_content(
            model=self.model,
            contents=[{
                "parts": [
                    {"text": prompt},
                    {"file_data": {"file_uri": uploaded.uri, "mime_type": uploaded.mime_type}}
                ]
            }]
        )
        return response.text

    def analyze_frames(self, frame_paths: list[str], prompt: str | None = None) -> str:
        client = self._get_client()
        prompt = prompt or DEFAULT_FRAMES_PROMPT

        parts = [{"text": prompt}]
        for fp in frame_paths:
            with open(fp, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            parts.append({"inline_data": {"mime_type": "image/png", "data": data}})

        response = client.models.generate_content(
            model=self.model,
            contents=[{"parts": parts}]
        )
        return response.text


class LocalAnalyzer(BaseAnalyzer):
    """VLM analyzer using a local HuggingFace model (e.g. Molmo2-4B).

    Loads the model into GPU on first use. Subsequent calls reuse the
    loaded model. Supports image and video analysis via transformers.
    """

    def __init__(self, model_id: str | None = None):
        self.model_id = model_id if model_id is not None else os.environ.get("VLM_MODEL_ID", "allenai/Molmo2-4B")
        self._model = None
        self._processor = None

    @property
    def available(self) -> bool:
        return bool(self.model_id)

    def _load_model(self):
        """Load model and processor on first use."""
        if self._model is not None:
            return

        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText

        self._processor = AutoProcessor.from_pretrained(
            self.model_id, trust_remote_code=True, dtype="auto", device_map="auto"
        )
        self._model = AutoModelForImageTextToText.from_pretrained(
            self.model_id, trust_remote_code=True, dtype="auto", device_map="auto"
        )

    def _generate(self, messages: list[dict]) -> str:
        """Run inference with the loaded model."""
        import torch

        self._load_model()

        inputs = self._processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_tensors="pt", return_dict=True,
        )
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        with torch.inference_mode():
            generated_ids = self._model.generate(**inputs, max_new_tokens=2048)

        generated_tokens = generated_ids[0, inputs["input_ids"].size(1):]
        return self._processor.tokenizer.decode(generated_tokens, skip_special_tokens=True)

    def analyze_image(self, image_path: str, prompt: str | None = None) -> str:
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        prompt = prompt or DEFAULT_IMAGE_PROMPT

        messages = [{
            "role": "user",
            "content": [
                dict(type="text", text=prompt),
                dict(type="image", image=str(image_path)),
            ],
        }]

        return self._generate(messages)

    def analyze_video(self, video_path: str, prompt: str | None = None) -> str:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        prompt = prompt or DEFAULT_VIDEO_PROMPT

        messages = [{
            "role": "user",
            "content": [
                dict(type="text", text=prompt),
                dict(type="video", video=str(video_path)),
            ],
        }]

        return self._generate(messages)

    def analyze_frames(self, frame_paths: list[str], prompt: str | None = None) -> str:
        prompt = prompt or DEFAULT_FRAMES_PROMPT

        content = [dict(type="text", text=prompt)]
        for fp in frame_paths:
            if not Path(fp).exists():
                raise FileNotFoundError(f"Frame not found: {fp}")
            content.append(dict(type="image", image=fp))

        messages = [{"role": "user", "content": content}]
        return self._generate(messages)


def create_analyzer(**kwargs) -> BaseAnalyzer:
    """Create the appropriate analyzer based on environment.

    Priority:
    1. VLM_MODEL_ID set → LocalAnalyzer (free, runs on your GPU)
    2. GEMINI_API_KEY set → GeminiAnalyzer (API, requires key)
    3. Neither → returns a LocalAnalyzer with default model (available=True,
       will download on first use)

    Override with explicit kwargs:
        create_analyzer(backend="local", model_id="allenai/Molmo2-4B")
        create_analyzer(backend="gemini", api_key="...")
    """
    backend = kwargs.get("backend")

    if backend == "local":
        return LocalAnalyzer(model_id=kwargs.get("model_id"))
    elif backend == "gemini":
        return GeminiAnalyzer(api_key=kwargs.get("api_key"), model=kwargs.get("model", "gemini-2.5-flash"))

    # Auto-detect
    if os.environ.get("VLM_MODEL_ID"):
        return LocalAnalyzer()
    elif os.environ.get("GEMINI_API_KEY"):
        return GeminiAnalyzer()
    else:
        # Default to local — it's free and will download on first use
        return LocalAnalyzer()


# Backwards compatibility
VisionAnalyzer = GeminiAnalyzer
