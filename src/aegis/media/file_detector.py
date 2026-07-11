"""
File type detector — identifies category from extension + magic bytes.
Returns a FileCategory used by MediaPipeline to route to correct processor.
"""
from enum import Enum
from pathlib import Path


class FileCategory(str, Enum):
    TEXT_DOC  = "text_doc"   # PDF, DOCX, TXT, MD
    TABULAR   = "tabular"    # CSV, XLSX, XLS
    IMAGE     = "image"      # JPG, PNG, GIF, WEBP, BMP, TIFF
    AUDIO     = "audio"      # MP3, WAV, M4A, OGG
    VIDEO     = "video"      # MP4, MOV, AVI, MKV
    CODE      = "code"       # .py .js .ts .go .java .sql etc.
    DATA      = "data"       # JSON, XML, YAML
    UNKNOWN   = "unknown"


_EXT_MAP: dict[str, FileCategory] = {
    # Text documents
    ".pdf":  FileCategory.TEXT_DOC,
    ".docx": FileCategory.TEXT_DOC,
    ".doc":  FileCategory.TEXT_DOC,
    ".txt":  FileCategory.TEXT_DOC,
    ".md":   FileCategory.TEXT_DOC,
    ".rtf":  FileCategory.TEXT_DOC,
    # Tabular
    ".csv":  FileCategory.TABULAR,
    ".xlsx": FileCategory.TABULAR,
    ".xls":  FileCategory.TABULAR,
    ".tsv":  FileCategory.TABULAR,
    # Images
    ".jpg":  FileCategory.IMAGE,
    ".jpeg": FileCategory.IMAGE,
    ".png":  FileCategory.IMAGE,
    ".gif":  FileCategory.IMAGE,
    ".webp": FileCategory.IMAGE,
    ".bmp":  FileCategory.IMAGE,
    ".tiff": FileCategory.IMAGE,
    ".tif":  FileCategory.IMAGE,
    # Audio
    ".mp3":  FileCategory.AUDIO,
    ".wav":  FileCategory.AUDIO,
    ".m4a":  FileCategory.AUDIO,
    ".ogg":  FileCategory.AUDIO,
    ".flac": FileCategory.AUDIO,
    # Video
    ".mp4":  FileCategory.VIDEO,
    ".mov":  FileCategory.VIDEO,
    ".avi":  FileCategory.VIDEO,
    ".mkv":  FileCategory.VIDEO,
    ".webm": FileCategory.VIDEO,
    # Code
    ".py":   FileCategory.CODE,
    ".js":   FileCategory.CODE,
    ".ts":   FileCategory.CODE,
    ".go":   FileCategory.CODE,
    ".java": FileCategory.CODE,
    ".cpp":  FileCategory.CODE,
    ".c":    FileCategory.CODE,
    ".rs":   FileCategory.CODE,
    ".sql":  FileCategory.CODE,
    ".sh":   FileCategory.CODE,
    ".yaml": FileCategory.CODE,
    ".toml": FileCategory.CODE,
    # Data
    ".json": FileCategory.DATA,
    ".xml":  FileCategory.DATA,
}

# Magic bytes for reliable type detection regardless of extension
_MAGIC: list[tuple[bytes, FileCategory]] = [
    (b"%PDF",           FileCategory.TEXT_DOC),
    (b"PK\x03\x04",    FileCategory.TEXT_DOC),   # DOCX/XLSX (ZIP-based)
    (b"\xff\xd8\xff",  FileCategory.IMAGE),        # JPEG
    (b"\x89PNG",       FileCategory.IMAGE),
    (b"GIF8",          FileCategory.IMAGE),
    (b"RIFF",          FileCategory.AUDIO),        # WAV
    (b"ID3",           FileCategory.AUDIO),        # MP3
    (b"\x00\x00\x00",  FileCategory.VIDEO),        # MP4 ftyp box
]


def detect(filename: str, data: bytes) -> FileCategory:
    """Detect file category. Magic bytes take priority over extension."""
    ext = Path(filename).suffix.lower()

    # Magic bytes check first (more reliable)
    for magic, category in _MAGIC:
        if data[:len(magic)] == magic:
            # Disambiguate DOCX vs XLSX (both are ZIP)
            if magic == b"PK\x03\x04":
                return FileCategory.TABULAR if ext in (".xlsx", ".xls") else FileCategory.TEXT_DOC
            return category

    # Fall back to extension
    return _EXT_MAP.get(ext, FileCategory.UNKNOWN)
