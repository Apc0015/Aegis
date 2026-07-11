"""
Image processor — prepares images for vision-capable LLMs.

Two outputs:
  - base64_payload()  → base64 string for vision LLM message content
  - describe()        → text description via vision LLM (for non-vision LLMs)
"""
import base64
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MAX_DIMENSION = 1568   # OpenAI/Anthropic recommended max edge
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB limit


def to_base64(data: bytes, filename: str) -> tuple[str, str]:
    """
    Resize + compress image if needed, return (base64_string, mime_type).
    Safe to pass directly into vision LLM message content.
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))

        # Convert RGBA/P → RGB for JPEG compatibility
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize if too large
        w, h = img.size
        if max(w, h) > MAX_DIMENSION:
            ratio = MAX_DIMENSION / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

        # Re-encode as JPEG for size
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        compressed = buf.getvalue()

        # If still too large, reduce quality further
        if len(compressed) > MAX_SIZE_BYTES:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=60, optimize=True)
            compressed = buf.getvalue()

        return base64.b64encode(compressed).decode("utf-8"), "image/jpeg"

    except ImportError:
        # Pillow not installed — pass raw bytes as-is
        logger.warning("ImageProcessor: Pillow not installed — skipping resize/compress")
        ext = filename.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/jpeg")
        return base64.b64encode(data).decode("utf-8"), mime

    except Exception as e:
        logger.error(f"ImageProcessor: failed to process image: {e}")
        raise


def build_vision_message(data: bytes, filename: str, user_text: str) -> list[dict]:
    """
    Build the messages list for a vision LLM call.
    Returns content array with text + image_url parts.
    """
    b64, mime = to_base64(data, filename)
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                },
            ],
        }
    ]


async def describe_image(
    data: bytes,
    filename: str,
    question: str,
    llm_service,
) -> str:
    """
    Get a text description of an image using the LLM's vision capability.
    Falls back gracefully if vision is not supported.
    """
    try:
        messages = build_vision_message(data, filename, question)
        return await llm_service.chat(messages, temperature=0.1)
    except Exception as e:
        logger.warning(f"ImageProcessor: vision description failed: {e}")
        return f"[Image '{filename}' could not be analyzed: {e}]"
