"""
MediaPipeline — orchestrates all file processors.

Entry point: process(data, filename, question, llm_service)

Returns MediaResult:
  - text_content   : extracted text (for text/tabular/code/data/audio files)
  - image_b64      : base64 image (for vision LLM, None for others)
  - image_mime     : MIME type if image
  - category       : detected FileCategory
  - description    : human-readable summary of what was extracted
  - is_vision      : True if LLM should receive this as image_url content
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

from aegis.media.file_detector import FileCategory, detect
from aegis.media import text_extractor, image_processor, audio_transcriber

logger = logging.getLogger(__name__)

# Providers known to support vision
VISION_CAPABLE_PROVIDERS = {"openai", "anthropic", "google", "openrouter"}


@dataclass
class MediaResult:
    category: FileCategory
    text_content: Optional[str] = None      # extracted text for text-based files
    image_b64: Optional[str] = None         # base64 for vision LLM
    image_mime: Optional[str] = None
    description: str = ""                   # short description of what was extracted
    is_vision: bool = False                 # True = inject as image_url in message


async def process(
    data: bytes,
    filename: str,
    question: str,
    llm_service,
    llm_provider: str = "openai",
) -> MediaResult:
    """
    Process any uploaded file into LLM-ready content.

    - Text/tabular/code/data → extract text → inject as context
    - Image + vision LLM     → base64 → inject as image_url
    - Image + no vision      → describe via vision model → inject as text
    - Audio                  → transcribe → inject as text
    - Video                  → not yet supported, return message
    """
    category = detect(filename, data)
    logger.info(f"MediaPipeline: '{filename}' detected as {category}")

    if category == FileCategory.TEXT_DOC:
        text = text_extractor.extract(data, filename)
        return MediaResult(
            category=category,
            text_content=text,
            description=f"Document '{filename}' extracted ({len(text)} chars)",
        )

    elif category == FileCategory.TABULAR:
        text = text_extractor.extract(data, filename)
        return MediaResult(
            category=category,
            text_content=text,
            description=f"Spreadsheet '{filename}' parsed as table",
        )

    elif category == FileCategory.CODE:
        text = text_extractor.extract(data, filename)
        return MediaResult(
            category=category,
            text_content=f"[Code file: {filename}]\n{text}",
            description=f"Code file '{filename}' extracted",
        )

    elif category == FileCategory.DATA:
        text = text_extractor.extract(data, filename)
        return MediaResult(
            category=category,
            text_content=f"[Data file: {filename}]\n{text}",
            description=f"Data file '{filename}' parsed",
        )

    elif category == FileCategory.IMAGE:
        provider = llm_provider.lower()
        if provider in VISION_CAPABLE_PROVIDERS:
            # Vision LLM — send image directly
            b64, mime = image_processor.to_base64(data, filename)
            return MediaResult(
                category=category,
                image_b64=b64,
                image_mime=mime,
                description=f"Image '{filename}' ready for vision LLM",
                is_vision=True,
            )
        else:
            # Non-vision LLM — describe the image first
            logger.info(f"MediaPipeline: non-vision LLM '{provider}', describing image via text")
            description = await image_processor.describe_image(data, filename, question, llm_service)
            return MediaResult(
                category=category,
                text_content=f"[Image '{filename}' — Visual Description]:\n{description}",
                description=f"Image '{filename}' described as text (non-vision LLM)",
            )

    elif category == FileCategory.AUDIO:
        transcript = await audio_transcriber.transcribe(data, filename)
        return MediaResult(
            category=category,
            text_content=f"[Audio transcript from '{filename}']:\n{transcript}",
            description=f"Audio '{filename}' transcribed ({len(transcript)} chars)",
        )

    elif category == FileCategory.VIDEO:
        return MediaResult(
            category=category,
            text_content="[Video files are not yet supported. Please extract audio or screenshots first.]",
            description="Video file — not supported",
        )

    else:
        # Unknown — try plain text extraction anyway
        try:
            text = data.decode("utf-8", errors="replace")[:8000]
            return MediaResult(
                category=category,
                text_content=f"[File: {filename}]\n{text}",
                description=f"Unknown file type '{filename}' — read as plain text",
            )
        except Exception:
            return MediaResult(
                category=FileCategory.UNKNOWN,
                text_content=f"[File '{filename}' could not be processed — unsupported format]",
                description="Unsupported file format",
            )


def build_context_block(result: MediaResult, filename: str) -> str:
    """
    Format the extracted content as a labeled context block for R4 prompt injection.
    Only for text-based results (is_vision=False).
    """
    if result.is_vision or not result.text_content:
        return ""
    return (
        f"=== UPLOADED FILE: {filename} ===\n"
        f"{result.text_content}\n"
        f"=== END OF FILE ===\n"
    )
