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
