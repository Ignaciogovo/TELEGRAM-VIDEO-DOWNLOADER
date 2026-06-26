"""Utilidades compartidas para Telegram Video Downloader."""

from typing import Optional

from telethon.tl.types import DocumentAttributeVideo, DocumentAttributeFilename


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_video_duration(video) -> Optional[float]:
    """Extract duration from video document attributes."""
    for attr in video.attributes:
        if isinstance(attr, DocumentAttributeVideo):
            return attr.duration
    return None


def get_video_resolution(video) -> tuple[Optional[int], Optional[int]]:
    """Extract width and height from video document attributes."""
    for attr in video.attributes:
        if isinstance(attr, DocumentAttributeVideo):
            return attr.w, attr.h
    return None, None


def get_filename(video) -> Optional[str]:
    """Extract original filename from video document attributes."""
    for attr in video.attributes:
        if isinstance(attr, DocumentAttributeFilename):
            return attr.file_name
    return None
