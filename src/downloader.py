"""Bulk download logic for Phase 2.

Downloads videos from a Telegram channel with:
- Duration filtering
- Daily download limits
- Security scanning (ClamAV/VirusTotal)
- Channel-to-folder mapping
- Progress tracking and resume support
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add project root to path for src module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient, errors, types
from telethon.tl.types import (
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    InputMessagesFilterVideo,
)
from tqdm import tqdm

from src.history import DownloadHistory
from src.scanner import ScanResult, SecurityScanner
from src.notifier import Notifier

logger = logging.getLogger(__name__)


def get_video_duration(video) -> Optional[float]:
    """Extract duration from video document attributes.

    Args:
        video: The video Document object.

    Returns:
        Duration in seconds, or None if not found.
    """
    for attr in video.attributes:
        if isinstance(attr, DocumentAttributeVideo):
            return attr.duration
    return None


def get_video_resolution(video) -> tuple[Optional[int], Optional[int]]:
    """Extract width and height from video document attributes.

    Args:
        video: The video Document object.

    Returns:
        Tuple of (width, height), or (None, None) if not found.
    """
    for attr in video.attributes:
        if isinstance(attr, DocumentAttributeVideo):
            return attr.w, attr.h
    return None, None


def get_filename(video) -> Optional[str]:
    """Extract original filename from video document attributes.

    Args:
        video: The video Document object.

    Returns:
        Original filename, or None if not found.
    """
    for attr in video.attributes:
        if isinstance(attr, DocumentAttributeFilename):
            return attr.file_name
    return None


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable size string.
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_folder_for_channel(
    channel_id: str, channel_folders: dict, default_folder: str
) -> str:
    """Get the destination folder for a channel.

    Args:
        channel_id: The channel ID (string).
        channel_folders: Mapping of channel IDs to folder names.
        default_folder: Default folder if channel not in mapping.

    Returns:
        Folder name for this channel.
    """
    return channel_folders.get(channel_id, default_folder)


def build_output_path(
    output_dir: str, folder: str, message_id: int, original_name: Optional[str]
) -> str:
    """Build the full file path for a downloaded video.

    Args:
        output_dir: Base output directory.
        folder: Subfolder for this channel.
        message_id: Telegram message ID (fallback for naming).
        original_name: Original filename from Telegram.

    Returns:
        Full path where the file will be saved.
    """
    folder_path = os.path.join(output_dir, folder)
    os.makedirs(folder_path, exist_ok=True)

    if original_name:
        return os.path.join(folder_path, original_name)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return os.path.join(folder_path, f"video_{message_id}_{timestamp}.mp4")


async def download_video(
    client: TelegramClient, message: types.Message, output_path: str
) -> int:
    """Download a video with progress bar.

    Args:
        client: Authenticated TelegramClient.
        message: The message containing the video.
        output_path: Full path to save the file.

    Returns:
        Size of downloaded file in bytes.
    """
    video = message.video
    file_size = video.size

    pbar = tqdm(
        total=file_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=f"  Descargando msg#{message.id}",
        colour="green",
    )

    def progress_callback(current: int, _total: int) -> None:
        pbar.n = current
        pbar.refresh()

    await client.download_file(
        input_location=video,
        file=output_path,
        progress_callback=progress_callback,
    )

    pbar.close()
    return os.path.getsize(output_path)


class DownloadSummary:
    """Tracks download statistics for a session."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.total_found = 0
        self.already_downloaded = 0
        self.skipped_short = 0
        self.downloaded = 0
        self.errors = 0
        self.dry_run_count = 0
        self.start_time = time.time()
        self.details: list[str] = []

    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time

    def format_elapsed(self) -> str:
        """Format elapsed time as human-readable string."""
        secs = self.elapsed()
        if secs < 60:
            return f"{secs:.0f}s"
        elif secs < 3600:
            return f"{secs / 60:.1f}m"
        else:
            hours = int(secs // 3600)
            mins = int((secs % 3600) // 60)
            return f"{hours}h {mins}m"

    def print_summary(self, channel_title: str, daily_remaining: int) -> None:
        """Print summary to logger.

        Args:
            channel_title: Name of the channel.
            daily_remaining: Remaining daily download quota.
        """
        lines = [
            "=" * 50,
            f"  DESCARGA MASIVA COMPLETADA",
            "=" * 50,
            f"  Canal: {channel_title}",
            f"  Vídeos encontrados:        {self.total_found}",
            f"  Ya descargados:            {self.already_downloaded}",
            f"  Saltados (cortos):         {self.skipped_short}",
            f"  Descargados correctamente: {self.downloaded}",
            f"  Dry-run (simulados):       {self.dry_run_count}",
            f"  Errores:                   {self.errors}",
            f"  Límite diario:             {daily_remaining} restantes",
            "-" * 50,
            f"  Tiempo total:          {self.format_elapsed()}",
            "=" * 50,
        ]
        for line in lines:
            logger.info(line)

    def save_to_log(self, output_dir: str, channel_title: str, daily_remaining: int) -> str:
        """Save summary to a log file.

        Args:
            output_dir: Base output directory.
            channel_title: Name of the channel.
            daily_remaining: Remaining daily download quota.

        Returns:
            Path to the log file.
        """
        log_dir = os.path.join(output_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"summary_{timestamp}.log")

        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"DESCARGA MASIVA - {channel_title}\n")
            f.write(f"Fecha: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"Vídeos encontrados: {self.total_found}\n")
            f.write(f"Ya descargados: {self.already_downloaded}\n")
            f.write(f"Saltados (cortos): {self.skipped_short}\n")
            f.write(f"Descargados: {self.downloaded}\n")
            f.write(f"Dry-run: {self.dry_run_count}\n")
            f.write(f"Errores: {self.errors}\n")
            f.write(f"Límite diario restante: {daily_remaining}\n")
            f.write(f"Tiempo total: {self.format_elapsed()}\n")

            if self.details:
                f.write("\nDetalles:\n")
                for detail in self.details:
                    f.write(f"  {detail}\n")

        logger.info("Resumen guardado en: %s", log_path)
        return log_path


async def run_bulk_download(
    client: TelegramClient,
    channel_entity: types.InputChannel,
    channel_id: str,
    channel_title: str,
    config: dict,
    history: DownloadHistory,
    scanner: SecurityScanner,
    notifier: Optional[Notifier] = None,
    dry_run: bool = False,
    from_start: bool = False,
) -> DownloadSummary:
    """Execute bulk download for a channel.

    Args:
        client: Authenticated TelegramClient.
        channel_entity: The channel entity.
        channel_id: Channel ID string.
        channel_title: Channel display name.
        config: Configuration dictionary.
        history: DownloadHistory instance.
        scanner: SecurityScanner instance.
        dry_run: If True, simulate without downloading.
        from_start: If True, scan from beginning (ignore checkpoint).

    Returns:
        DownloadSummary with statistics.
    """
    summary = DownloadSummary()

    output_dir = config.get("output_dir", "./downloads")
    channel_folders = config.get("channel_folders", {})
    default_folder = config.get("default_folder", "uncategorized")
    min_duration = config.get("min_duration_seconds", 300)
    delay = config.get("download_delay_seconds", 30)
    max_daily = config.get("max_daily_downloads", 50)

    folder = get_folder_for_channel(channel_id, channel_folders, default_folder)
    logger.info("Carpeta destino para este canal: %s", folder)

    checkpoint = 0
    if not from_start:
        state = history.get_channel_state(channel_id)
        checkpoint = state.get("last_processed_message_id", 0)
        if checkpoint > 0:
            logger.info("Resumiendo desde message_id=%d", checkpoint)
        else:
            logger.info("Primera ejecución para este canal")

    daily_count = history.get_daily_count()
    logger.info("Descargas hoy: %d/%d", daily_count, max_daily)

    total_videos = 0
    last_processed_id = 0

    async for message in client.iter_messages(
        channel_entity, filter=InputMessagesFilterVideo()
    ):
        total_videos += 1
        msg_id = message.id

        if not from_start and msg_id <= checkpoint:
            last_processed_id = max(last_processed_id, msg_id)
            continue

        summary.total_found += 1
        last_processed_id = max(last_processed_id, msg_id)

        video = message.video
        if not video:
            continue

        duration = get_video_duration(video) or 0
        original_name = get_filename(video)
        width, height = get_video_resolution(video)

        if history.is_downloaded(msg_id):
            summary.already_downloaded += 1
            logger.debug("msg#%d: ya descargado", msg_id)
            continue

        if history.is_skipped_short(msg_id):
            summary.skipped_short += 1
            logger.debug("msg#%d: ya saltado (corto)", msg_id)
            continue

        if duration < min_duration:
            history.record_skipped_short(msg_id, channel_id, duration, original_name)
            summary.skipped_short += 1
            logger.info(
                "msg#%d: saltado (%.0fs < %ds)", msg_id, duration, min_duration
            )
            continue

        if daily_count >= max_daily:
            logger.info("Límite diario alcanzado (%d/%d)", daily_count, max_daily)
            break

        if dry_run:
            summary.dry_run_count += 1
            size_str = format_size(video.size)
            dur_str = f"{duration:.0f}s" if duration else "?"
            logger.info(
                "msg#%d: [DRY-RUN] %s | %s | %s | carpeta: %s",
                msg_id,
                original_name or f"video_{msg_id}",
                size_str,
                dur_str,
                folder,
            )
            summary.details.append(
                f"msg#{msg_id}: {original_name or 'video'} | {size_str} | {dur_str}"
            )
            continue

        output_path = build_output_path(output_dir, folder, msg_id, original_name)

        try:
            start = time.time()
            downloaded_size = await download_video(client, message, output_path)
            elapsed = time.time() - start

            scan_result = scanner.scan(output_path)
            if scan_result.is_threat():
                history.record_error(msg_id, channel_id, "Amenaza detectada")
                summary.errors += 1
                summary.details.append(f"msg#{msg_id}: AMENAZA - {original_name}")
                logger.error("msg#%d: AMENAZA detectada", msg_id)
                
                if notifier:
                    notifier.notify_threat(
                        subject=f"Amenaza detectada en vídeo #{msg_id}",
                        message=f"Se detectó una amenaza en el vídeo descargado del canal {channel_title}",
                        metadata={
                            "channel_id": channel_id,
                            "channel_title": channel_title,
                            "video_id": str(msg_id),
                            "scan_result": scan_result.status,
                            "scan_details": scan_result.details,
                            "file_path": output_path
                        }
                    )
                continue

            history.record_downloaded(
                message_id=msg_id,
                channel_id=channel_id,
                filename=os.path.basename(output_path),
                original_name=original_name,
                size_bytes=downloaded_size,
                duration_seconds=duration,
                width=width or 0,
                height=height or 0,
                mime_type=video.mime_type or "",
                output_path=output_path,
                category=folder,
                scan_result=scan_result.status,
            )

            daily_count = history.increment_daily_count()
            summary.downloaded += 1
            summary.details.append(
                f"msg#{msg_id}: {original_name or 'video'} | {format_size(downloaded_size)} | {elapsed:.0f}s"
            )

            logger.info(
                "msg#%d: descargado (%s en %.0fs) | scan: %s",
                msg_id,
                format_size(downloaded_size),
                elapsed,
                scan_result.status,
            )

            if daily_count < max_daily:
                logger.info("Esperando %ds antes de la siguiente descarga...", delay)
                await asyncio.sleep(delay)

        except Exception as e:
            logger.error("msg#%d: error descargando: %s", msg_id, e)
            history.record_error(msg_id, channel_id, str(e))
            summary.errors += 1
            summary.details.append(f"msg#{msg_id}: ERROR - {e}")
            
            if notifier:
                notifier.notify_error(
                    subject=f"Error descargando vídeo #{msg_id}",
                    message=f"Error al descargar vídeo del canal {channel_title}",
                    metadata={
                        "channel_id": channel_id,
                        "channel_title": channel_title,
                        "video_id": str(msg_id),
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )

    history.update_channel_state(channel_id, last_processed_id, total_videos)

    daily_remaining = max(0, max_daily - daily_count)
    summary.print_summary(channel_title, daily_remaining)
    summary.save_to_log(output_dir, channel_title, daily_remaining)

    return summary
