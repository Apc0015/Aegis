"""
Audio transcriber — converts MP3/WAV/M4A to text via OpenAI Whisper.

Two modes:
  - Local Whisper (whisper package) — no API key, runs on CPU/GPU
  - OpenAI Whisper API — faster, requires OPENAI_API_KEY
"""
import io
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


async def transcribe(data: bytes, filename: str) -> str:
    """
    Transcribe audio file to text.
    Tries OpenAI Whisper API first, falls back to local Whisper model.
    """
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AEGIS_MAIN_API_KEY")

    if api_key and os.getenv("AEGIS_LLM_PROVIDER", "openai") == "openai":
        return await _transcribe_api(data, filename, api_key)
    else:
        return _transcribe_local(data, filename)


async def _transcribe_api(data: bytes, filename: str, api_key: str) -> str:
    """Transcribe using OpenAI Whisper API."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        file_tuple = (filename, io.BytesIO(data), _mime(filename))
        result = await client.audio.transcriptions.create(
            model="whisper-1",
            file=file_tuple,
            response_format="text",
        )
        return str(result).strip()
    except Exception as e:
        logger.warning(f"AudioTranscriber: API transcription failed ({e}), trying local")
        return _transcribe_local(data, filename)


def _transcribe_local(data: bytes, filename: str) -> str:
    """Transcribe using local openai-whisper package."""
    try:
        import whisper
        import tempfile

        suffix = Path(filename).suffix or ".mp3"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(data)
            tmp_path = f.name

        try:
            model = whisper.load_model("base")
            result = model.transcribe(tmp_path)
            return result.get("text", "").strip()
        finally:
            os.unlink(tmp_path)

    except ImportError:
        return f"[Audio transcription unavailable — install 'openai-whisper' or set OPENAI_API_KEY]"
    except Exception as e:
        logger.error(f"AudioTranscriber: local transcription failed: {e}")
        return f"[Audio '{filename}' could not be transcribed: {e}]"


def _mime(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }.get(ext, "audio/mpeg")
