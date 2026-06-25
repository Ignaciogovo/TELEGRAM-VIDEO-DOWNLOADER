"""Bulk download logic for Phase 2.

Downloads videos from a Telegram channel with:
- Duration filtering
- Daily download limits
- Security scanning (ClamAV/VirusTotal)
- Channel-to-folder mapping
- Progress tracking and resume support
- File integrity validation
- Partial download cleanup
- Session summary and notifications
- Disk space validation
- Configurable timeouts and retries
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import uuid
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
from src.utils import format_size, get_video_duration, get_video_resolution, get_filename

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".flv", ".wmv"}
PART_EXTENSIONS = {".part", ".tmp", ".temp", ".download"}


def get_folder_for_channel(
    channel_index: int, channel_folders: dict, default_folder: str
) -> str:
    """Get the destination folder for a channel by its position in TELEGRAM_CHANNELS."""
    return channel_folders.get(channel_index, default_folder)


def build_output_path(
    output_dir: str, folder: str, message_id: int, original_name: Optional[str]
) -> str:
    """Build the full file path for a downloaded video."""
    folder_path = os.path.join(output_dir, folder)
    os.makedirs(folder_path, exist_ok=True)

    if original_name:
        return os.path.join(folder_path, original_name)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return os.path.join(folder_path, f"video_{message_id}_{timestamp}.mp4")


def validate_video_file(filepath: str, expected_size: Optional[int] = None) -> tuple[bool, str]:
    """Validate that a downloaded file is a valid video.

    Uses ffprobe if available, otherwise checks file extension and minimum size.
    Also verifies file size against expected size if provided.

    Args:
        filepath: Path to the file to validate.
        expected_size: Expected file size in bytes (from Telegram metadata).

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is empty string.
    """
    if not os.path.exists(filepath):
        return False, "Archivo no existe"

    actual_size = os.path.getsize(filepath)

    # Check minimum size (1KB)
    if actual_size < 1024:
        return False, f"Archivo demasiado pequeño ({actual_size} bytes)"

    # Check extension
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        return False, f"Extensión no válida: {ext}"

    # Verify size matches expected (tolerance of 1 byte for filesystem differences)
    if expected_size is not None:
        size_diff = abs(actual_size - expected_size)
        if size_diff > 1:
            return False, f"Tamaño incorrecto: esperado {expected_size} bytes, obtenido {actual_size} bytes"

    # Try ffprobe for proper validation
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            result = subprocess.run(
                [ffprobe, "-v", "error", "-show_streams", filepath],
                capture_output=True,
                text=True,
                timeout=30,
            )
            # If ffprobe finds video or audio streams, it's valid
            if "codec_type=video" in result.stdout or "codec_type=audio" in result.stdout:
                return True, ""
            return False, "ffprobe no encontró streams de video/audio"
        except (subprocess.TimeoutExpired, Exception):
            # ffprobe failed, fall back to basic checks
            pass

    # Basic validation passed (extension + size + optional size check)
    return True, ""


def clean_partial_downloads(output_dir: str, history: Optional[object] = None) -> int:
    """Clean up partial/incomplete download files.

    Also detects video files that are likely incomplete (size mismatch with history).

    Args:
        output_dir: Base output directory to scan.
        history: Optional DownloadHistory instance to verify file integrity.

    Returns:
        Number of files cleaned.
    """
    cleaned = 0

    # Clean files with partial download extensions
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            filepath = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in PART_EXTENSIONS:
                try:
                    os.remove(filepath)
                    logger.info("Archivo parcial eliminado: %s", filepath)
                    cleaned += 1
                except OSError as e:
                    logger.warning("No se pudo eliminar %s: %s", filepath, e)

    # Clean zero-byte video files (likely interrupted downloads)
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            filepath = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                try:
                    if os.path.getsize(filepath) == 0:
                        os.remove(filepath)
                        logger.info("Archivo vacío eliminado: %s", filepath)
                        cleaned += 1
                except OSError as e:
                    logger.warning("No se pudo eliminar %s: %s", filepath, e)

    # Verify existing files against history if available
    if history is not None:
        cleaned += _clean_corrupt_files_from_history(output_dir, history)

    return cleaned


def _clean_corrupt_files_from_history(output_dir: str, history: object) -> int:
    """Clean files that are marked as downloaded but are missing or corrupt on disk.

    Args:
        output_dir: Base output directory.
        history: DownloadHistory instance.

    Returns:
        Number of files cleaned/marked for retry.
    """
    cleaned = 0
    try:
        stats = history.conn.execute(
            "SELECT * FROM downloads WHERE status = 'downloaded'"
        ).fetchall()

        for row in stats:
            output_path = row["output_path"]
            message_id = row["message_id"]
            expected_size = row["size_bytes"]

            if not output_path:
                continue

            # Check if file exists
            if not os.path.exists(output_path):
                logger.warning(
                    "Archivo descargado no encontrado en disco: %s (msg#%d)",
                    output_path, message_id,
                )
                history.record_error(message_id, row["channel_id"], "Archivo no encontrado en disco")
                cleaned += 1
                continue

            # Check if file size matches
            actual_size = os.path.getsize(output_path)
            if expected_size and abs(actual_size - expected_size) > 1:
                logger.warning(
                    "Archivo corrupto detectado (tamaño %d != %d): %s (msg#%d)",
                    actual_size, expected_size, output_path, message_id,
                )
                # Move to quarantine
                from src.scanner import SecurityScanner
                scanner = SecurityScanner(output_dir=output_dir)
                scanner.quarantine_file(output_path)
                history.record_error(message_id, row["channel_id"], "Archivo corrupto (tamaño incorrecto)")
                cleaned += 1
    except Exception as e:
        logger.warning("Error verificando historial: %s", e)

    return cleaned


async def download_video(
    client: TelegramClient,
    message: types.Message,
    output_path: str,
    timeout: int = 3600,
    max_retries: int = 3,
    channel_entity=None,
) -> tuple[int, int]:
    """Download a video with progress bar, timeout, retries, and resume support.

    Downloads to a temporary .part file first, then renames on completion
    for atomic operation and to prevent corrupt files on crash.

    Supports resuming interrupted downloads by checking for existing .part files
    and using the offset parameter. Also handles FileReferenceExpiredError by
    re-fetching the message to get a fresh file reference.

    Args:
        client: Authenticated TelegramClient.
        message: The message containing the video.
        output_path: Full path to save the file.
        timeout: Maximum seconds for download (default 1 hour).
        max_retries: Maximum number of retry attempts.
        channel_entity: Channel entity for re-fetching messages on expired references.

    Returns:
        Tuple of (downloaded_size_bytes, retry_count).

    Raises:
        Exception: If download fails after all retries.
    """
    video = message.video
    file_size = video.size
    last_error = None
    retry_count = 0

    # Download to .part file first for atomic operation
    part_path = output_path + ".part"

    for attempt in range(1, max_retries + 1):
        # Check for existing partial download to resume
        offset = 0
        if os.path.exists(part_path):
            existing_size = os.path.getsize(part_path)
            if existing_size > 0 and existing_size < file_size:
                offset = existing_size
                logger.info(
                    "msg#%d: reanudando descarga desde %s (%.1f%%)",
                    message.id,
                    format_size(offset),
                    (offset / file_size) * 100,
                )

        pbar = tqdm(
            total=file_size,
            initial=offset,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=f"  Descargando msg#{message.id} (intento {attempt}/{max_retries})",
            colour="green",
        )

        start = time.time()
        current_message = message

        def progress_callback(current: int, _total: int) -> None:
            pbar.n = offset + current
            pbar.refresh()

        try:
            download_kwargs = {
                "input_location": current_message.video,
                "file": part_path,
                "progress_callback": progress_callback,
            }
            if offset > 0:
                download_kwargs["offset"] = offset

            await asyncio.wait_for(
                client.download_file(**download_kwargs),
                timeout=timeout,
            )
            pbar.close()

            # Atomic rename from .part to final path
            shutil.move(part_path, output_path)

            downloaded_size = os.path.getsize(output_path)
            elapsed = time.time() - start
            speed = downloaded_size / elapsed if elapsed > 0 else 0
            logger.debug(
                "msg#%d: descargado %s en %.0fs (%s/s) | reintentos: %d",
                message.id,
                format_size(downloaded_size),
                elapsed,
                format_size(int(speed)),
                retry_count,
            )
            return downloaded_size, retry_count

        except TypeError as te:
            if "offset" in str(te):
                pbar.close()
                logger.warning("msg#%d: offset no soportado, reintentando sin resume...", message.id)
                if attempt < max_retries:
                    retry_count += 1
                    continue
            raise

        except errors.FileReferenceExpiredError as e:
            pbar.close()
            last_error = e
            logger.debug("msg#%d: referencia de archivo caducada, re-obteniendo...", message.id)

            # Try to re-fetch the message to get a fresh file reference
            if channel_entity is not None:
                try:
                    fresh_messages = await client.get_messages(channel_entity, ids=message.id)
                    if fresh_messages and fresh_messages.video:
                        current_message = fresh_messages
                        video = fresh_messages.video
                        file_size = video.size
                        logger.debug("msg#%d: referencia actualizada correctamente", message.id)
                        # Delete partial file since reference changed
                        if os.path.exists(part_path):
                            os.remove(part_path)
                        offset = 0
                        # Continue to retry with fresh reference
                        if attempt < max_retries:
                            retry_count += 1
                            continue
                    else:
                        logger.debug("msg#%d: no se pudo re-obtener el mensaje", message.id)
                except Exception as fetch_error:
                    logger.debug("msg#%d: error re-obteniendo mensaje: %s", message.id, fetch_error)

            # Clean up partial file
            if os.path.exists(part_path):
                os.remove(part_path)
            if attempt < max_retries:
                retry_count += 1

        except asyncio.TimeoutError:
            pbar.close()
            last_error = TimeoutError(f"Timeout después de {timeout}s")
            logger.warning("msg#%d: timeout en intento %d", message.id, attempt)
            # Keep partial file for resume on next attempt
            if attempt < max_retries:
                retry_count += 1

        except Exception as e:
            pbar.close()
            last_error = e
            logger.warning("msg#%d: error en intento %d: %s", message.id, attempt, e)
            # Keep partial file for resume on next attempt (unless it's a reference error)
            if attempt < max_retries:
                retry_count += 1

        if attempt < max_retries:
            wait = min(2 ** attempt, 60)  # Exponential backoff, max 60s
            logger.debug("msg#%d: reintentando en %ds...", message.id, wait)
            await asyncio.sleep(wait)

    # All retries exhausted - log consolidated failure
    error_type = type(last_error).__name__ if last_error else "Unknown"
    error_msg = str(last_error) if last_error else "no error captured"
    logger.warning("msg#%d: %d/%d reintentos agotados (%s: %s)", message.id, max_retries, max_retries, error_type, error_msg)

    # Clean up any remaining .part file after all retries exhausted
    if os.path.exists(part_path):
        os.remove(part_path)

    raise last_error or Exception("Download failed after all retries")


class DownloadSummary:
    """Tracks download statistics for a session."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.session_id = str(uuid.uuid4())[:8]
        self.total_found = 0
        self.already_downloaded = 0
        self.skipped_short = 0
        self.downloaded = 0
        self.errors = 0
        self.invalid_files = 0
        self.dry_run_count = 0
        self.start_time = time.time()
        self.total_bytes = 0
        self.details: list[str] = []
        self.download_times: list[float] = []
        self.download_speeds: list[float] = []
        self.file_sizes: list[int] = []

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

    def average_speed(self) -> str:
        """Calculate average download speed."""
        elapsed = self.elapsed()
        if elapsed <= 0 or self.total_bytes <= 0:
            return "N/A"
        return f"{format_size(int(self.total_bytes / elapsed))}/s"

    def record_download(self, size_bytes: int, elapsed_seconds: float) -> None:
        """Record statistics for a single download.

        Args:
            size_bytes: Size of the downloaded file.
            elapsed_seconds: Time taken for the download.
        """
        self.download_times.append(elapsed_seconds)
        self.file_sizes.append(size_bytes)
        speed = size_bytes / elapsed_seconds if elapsed_seconds > 0 else 0
        self.download_speeds.append(speed)

    def min_time(self) -> str:
        """Get minimum download time."""
        if not self.download_times:
            return "N/A"
        return f"{min(self.download_times):.1f}s"

    def max_time(self) -> str:
        """Get maximum download time."""
        if not self.download_times:
            return "N/A"
        return f"{max(self.download_times):.1f}s"

    def fastest_speed(self) -> str:
        """Get fastest download speed."""
        if not self.download_speeds:
            return "N/A"
        return f"{format_size(int(max(self.download_speeds)))}/s"

    def slowest_speed(self) -> str:
        """Get slowest download speed."""
        if not self.download_speeds:
            return "N/A"
        return f"{format_size(int(min(self.download_speeds)))}/s"

    def largest_file(self) -> str:
        """Get largest file size."""
        if not self.file_sizes:
            return "N/A"
        return format_size(max(self.file_sizes))

    def smallest_file(self) -> str:
        """Get smallest file size."""
        if not self.file_sizes:
            return "N/A"
        return format_size(min(self.file_sizes))

    def success_rate(self) -> str:
        """Calculate success rate as percentage."""
        total_processed = self.downloaded + self.errors + self.invalid_files
        if total_processed == 0:
            return "N/A"
        rate = (self.downloaded / total_processed) * 100
        return f"{rate:.1f}%"

    def to_dict(self, channel_title: str, daily_remaining: int) -> dict:
        """Serialize summary to dictionary for JSON output.

        Args:
            channel_title: Name of the channel.
            daily_remaining: Remaining daily download slots.

        Returns:
            Dictionary with all summary data.
        """
        return {
            "session_id": self.session_id,
            "channel": channel_title,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "videos_found": self.total_found,
            "already_downloaded": self.already_downloaded,
            "skipped_short": self.skipped_short,
            "downloaded": self.downloaded,
            "invalid_files": self.invalid_files,
            "dry_run_count": self.dry_run_count,
            "errors": self.errors,
            "total_bytes": self.total_bytes,
            "space_used": format_size(self.total_bytes),
            "daily_remaining": daily_remaining,
            "elapsed_seconds": round(self.elapsed(), 1),
            "elapsed_formatted": self.format_elapsed(),
            "average_speed": self.average_speed(),
            "min_time": self.min_time(),
            "max_time": self.max_time(),
            "fastest_speed": self.fastest_speed(),
            "slowest_speed": self.slowest_speed(),
            "largest_file": self.largest_file(),
            "smallest_file": self.smallest_file(),
            "success_rate": self.success_rate(),
            "details": self.details,
        }

    def print_summary(self, channel_title: str, daily_remaining: int) -> None:
        """Print summary to logger and stdout."""
        lines = [
            "=" * 50,
            "  DESCARGA MASIVA COMPLETADA",
            "=" * 50,
            f"  Session ID:              {self.session_id}",
            f"  Canal:                   {channel_title}",
            f"  Vídeos encontrados:      {self.total_found}",
            f"  Ya descargados:          {self.already_downloaded}",
            f"  Saltados (cortos):       {self.skipped_short}",
            f"  Descargados correctamente: {self.downloaded}",
            f"  Archivos inválidos:      {self.invalid_files}",
            f"  Dry-run (simulados):     {self.dry_run_count}",
            f"  Errores:                 {self.errors}",
            f"  Tasa de éxito:           {self.success_rate()}",
            f"  Espacio usado:           {format_size(self.total_bytes)}",
            f"  Límite diario:           {daily_remaining} restantes",
            "-" * 50,
            f"  Tiempo total:            {self.format_elapsed()}",
            f"  Velocidad media:         {self.average_speed()}",
            f"  Tiempo mín/máx:          {self.min_time()} / {self.max_time()}",
            f"  Velocidad mín/máx:       {self.slowest_speed()} / {self.fastest_speed()}",
            f"  Archivo mín/máx:         {self.smallest_file()} / {self.largest_file()}",
            "=" * 50,
        ]
        for line in lines:
            logger.info(line)
            print(line)

    def save_to_log(self, output_dir: str, channel_title: str, daily_remaining: int) -> str:
        """Save summary to log and JSON files.

        Args:
            output_dir: Base output directory.
            channel_title: Name of the channel.
            daily_remaining: Remaining daily download slots.

        Returns:
            Path to the log file.
        """
        log_dir = os.path.join(output_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"summary_{timestamp}.log")
        json_path = os.path.join(log_dir, f"summary_{timestamp}.json")

        # Save human-readable log
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"DESCARGA MASIVA - {channel_title}\n")
            f.write(f"Session ID: {self.session_id}\n")
            f.write(f"Fecha: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"Vídeos encontrados: {self.total_found}\n")
            f.write(f"Ya descargados: {self.already_downloaded}\n")
            f.write(f"Saltados (cortos): {self.skipped_short}\n")
            f.write(f"Descargados: {self.downloaded}\n")
            f.write(f"Archivos inválidos: {self.invalid_files}\n")
            f.write(f"Dry-run: {self.dry_run_count}\n")
            f.write(f"Errores: {self.errors}\n")
            f.write(f"Tasa de éxito: {self.success_rate()}\n")
            f.write(f"Espacio usado: {format_size(self.total_bytes)}\n")
            f.write(f"Límite diario restante: {daily_remaining}\n")
            f.write(f"Tiempo total: {self.format_elapsed()}\n")
            f.write(f"Velocidad media: {self.average_speed()}\n")
            f.write(f"Tiempo mín/máx: {self.min_time()} / {self.max_time()}\n")
            f.write(f"Velocidad mín/máx: {self.slowest_speed()} / {self.fastest_speed()}\n")
            f.write(f"Archivo mín/máx: {self.smallest_file()} / {self.largest_file()}\n")

            if self.details:
                f.write("\nDetalles:\n")
                for detail in self.details:
                    f.write(f"  {detail}\n")

        # Save machine-readable JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(channel_title, daily_remaining), f, indent=2, ensure_ascii=False)

        logger.info("Resumen guardado en: %s y %s", log_path, json_path)
        return log_path


async def retry_failed_downloads(
    client: TelegramClient,
    channel_entity: types.InputChannel,
    channel_id: str,
    channel_title: str,
    config: dict,
    history: DownloadHistory,
    scanner: SecurityScanner,
    notifier: Optional[Notifier] = None,
    dry_run: bool = False,
    channel_index: int = 0,
    max_retries_per_file: int = 2,
    session_download_count: int = 0,
    max_per_run: int = 50,
) -> DownloadSummary:
    """Retry previously failed downloads (error or invalid status).

    Args:
        client: Authenticated TelegramClient.
        channel_entity: The channel entity to search messages in.
        channel_id: The channel identifier.
        channel_title: The channel title for logging.
        config: Configuration dictionary.
        history: DownloadHistory instance.
        scanner: SecurityScanner instance.
        notifier: Optional Notifier instance.
        dry_run: If True, only log what would be done.
        channel_index: Index of the channel for folder mapping.
        max_retries_per_file: Maximum retries per failed file.

    Returns:
        DownloadSummary with retry results.
    """
    summary = DownloadSummary()

    output_dir = config.get("output_dir", "./downloads")
    channel_folders = config.get("channel_folders", {})
    default_folder = config.get("default_folder", "uncategorized")
    delay = config.get("download_delay_seconds", 30)
    download_timeout = config.get("download_timeout_seconds", 3600)
    max_retries = config.get("max_download_retries", 3)
    min_free_space = config.get("min_free_space_mb", 500) * 1024 * 1024

    folder = get_folder_for_channel(channel_index, channel_folders, default_folder)

    # Get failed downloads for this channel
    failed = history.get_failed_downloads(channel_id)
    if not failed:
        logger.info("No hay descargas fallidas para reintentar en %s", channel_title)
        return summary

    # Initial disk space check before retrying
    stat = os.statvfs(output_dir)
    initial_free_space = stat.f_bavail * stat.f_frsize
    if initial_free_space < min_free_space:
        logger.error(
            "Espacio insuficiente para reintentos: %s libre, %s mínimo",
            format_size(initial_free_space),
            format_size(min_free_space),
        )
        return summary

    logger.info("Reintentando %d descargas fallidas en %s", len(failed), channel_title)

    # Build a map of message_id -> message for efficient lookup
    message_map = {}
    async for message in client.iter_messages(
        channel_entity, filter=InputMessagesFilterVideo(), ids=[f["message_id"] for f in failed]
    ):
        if message and message.video:
            message_map[message.id] = message

    for fail_record in failed:
        msg_id = fail_record["message_id"]
        if msg_id not in message_map:
            logger.warning("msg#%d: no se encontró el mensaje para reintentar", msg_id)
            summary.errors += 1
            continue

        message = message_map[msg_id]
        video = message.video
        duration = get_video_duration(video) or 0
        original_name = get_filename(video)
        width, height = get_video_resolution(video)

        output_path = build_output_path(output_dir, folder, msg_id, original_name)

        if dry_run:
            summary.dry_run_count += 1
            logger.info("msg#%d: [DRY-RUN REINTENTO] %s", msg_id, original_name or f"video_{msg_id}")
            continue

        # Check disk space
        stat = os.statvfs(output_dir)
        free_space = stat.f_bavail * stat.f_frsize
        if free_space < min_free_space:
            logger.error("Espacio insuficiente para reintentos")
            break

        try:
            start = time.time()
            dynamic_timeout = max(600, int(video.size / 500000) * 1.5)
            downloaded_size, retries = await download_video(
                client, message, output_path,
                timeout=dynamic_timeout,
                max_retries=max_retries_per_file,
                channel_entity=channel_entity,
            )
            elapsed = time.time() - start
            summary.total_bytes += downloaded_size

            # Validate file integrity
            is_valid, error_msg = validate_video_file(output_path, expected_size=video.size)
            if not is_valid:
                logger.error("msg#%d: reintentó pero sigue inválido: %s", msg_id, error_msg)
                summary.invalid_files += 1
                scanner.quarantine_file(output_path)
                history.record_invalid(
                    message_id=msg_id,
                    channel_id=channel_id,
                    filename=os.path.basename(output_path),
                    original_name=original_name,
                    error_message=f"Reintento fallido: {error_msg}",
                    output_path=output_path,
                )
                continue

            # Security scan
            scan_result = scanner.scan(output_path)
            if scan_result.status == ScanResult.THREAT:
                history.record_error(msg_id, channel_id, "Amenaza detectada en reintento")
                summary.errors += 1
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

            history.increment_daily_count()
            summary.downloaded += 1
            summary.record_download(downloaded_size, elapsed)
            logger.info("msg#%d: reintentado exitosamente (%s en %.0fs)", msg_id, format_size(downloaded_size), elapsed)

            if delay > 0:
                await asyncio.sleep(delay)

        except Exception as e:
            logger.error("msg#%d: error en reintento: %s", msg_id, e)
            history.record_error(msg_id, channel_id, f"Reintento fallido: {e}")
            summary.errors += 1

    run_remaining = max(0, max_per_run - session_download_count)
    summary.print_summary(f"{channel_title} (reintentos)", run_remaining)

    return summary


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
    channel_index: int = 0,
) -> DownloadSummary:
    """Execute bulk download for a channel."""
    summary = DownloadSummary()

    output_dir = config.get("output_dir", "./downloads")
    channel_folders = config.get("channel_folders", {})
    default_folder = config.get("default_folder", "uncategorized")
    min_duration = config.get("min_duration_seconds", 300)
    delay = config.get("download_delay_seconds", 30)
    max_per_run = config.get("max_downloads_per_run", 50)
    download_timeout = config.get("download_timeout_seconds", 3600)
    max_retries = config.get("max_download_retries", 3)
    min_free_space = config.get("min_free_space_mb", 500) * 1024 * 1024

    folder = get_folder_for_channel(channel_index, channel_folders, default_folder)
    logger.info("Carpeta destino para este canal: %s", folder)

    # Clean partial downloads before starting
    cleaned = clean_partial_downloads(output_dir, history)
    if cleaned > 0:
        logger.info("Archivos parciales/corruptos eliminados: %d", cleaned)

    # Initial disk space check before starting session
    stat = os.statvfs(output_dir)
    initial_free_space = stat.f_bavail * stat.f_frsize
    if initial_free_space < min_free_space:
        logger.error(
            "Espacio insuficiente al iniciar sesión: %s libre, %s mínimo",
            format_size(initial_free_space),
            format_size(min_free_space),
        )
        if notifier:
            notifier.notify_error(
                subject="Espacio en disco insuficiente al iniciar",
                message=f"No se puede iniciar la descarga. Espacio libre: {format_size(initial_free_space)}, mínimo: {format_size(min_free_space)}",
                metadata={
                    "channel_id": channel_id,
                    "channel_title": channel_title,
                    "free_space": initial_free_space,
                    "min_required": min_free_space,
                },
            )
        summary.print_summary(channel_title, max_per_run)
        return summary

    logger.info("Espacio libre disponible: %s", format_size(initial_free_space))

    session_download_count = 0
    logger.info("Límite por ejecución: %d", max_per_run)

    total_videos = 0

    async for message in client.iter_messages(
        channel_entity, filter=InputMessagesFilterVideo()
    ):
        total_videos += 1
        msg_id = message.id

        summary.total_found += 1

        video = message.video
        if not video:
            continue

        duration = get_video_duration(video) or 0
        original_name = get_filename(video)
        width, height = get_video_resolution(video)

        if history.is_downloaded(msg_id):
            output_path = history.get_output_path(msg_id)
            if output_path and not os.path.exists(output_path):
                logger.info("msg#%d: marcado como descargado pero archivo no existe, re-descargando", msg_id)
            else:
                summary.already_downloaded += 1
                logger.debug("msg#%d: ya descargado", msg_id)
                continue

        if history.is_skipped_short(msg_id):
            summary.skipped_short += 1
            logger.debug("msg#%d: ya saltado (corto)", msg_id)
            continue

        if history.is_invalid(msg_id):
            summary.invalid_files += 1
            logger.debug("msg#%d: ya marcado como inválido", msg_id)
            continue

        if duration < min_duration:
            history.record_skipped_short(msg_id, channel_id, duration, original_name)
            summary.skipped_short += 1
            logger.info(
                "msg#%d: saltado (%.0fs < %ds)", msg_id, duration, min_duration
            )
            continue

        if session_download_count >= max_per_run:
            logger.info("Límite por ejecución alcanzado (%d/%d)", session_download_count, max_per_run)
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

        # Check disk space before downloading
        stat = os.statvfs(output_dir)
        free_space = stat.f_bavail * stat.f_frsize
        if free_space < min_free_space:
            logger.error(
                "Espacio insuficiente: %s libre, %s mínimo requerido",
                format_size(free_space),
                format_size(min_free_space),
            )
            if notifier:
                notifier.notify_error(
                    subject="Espacio en disco insuficiente",
                    message=f"Espacio libre: {format_size(free_space)}, mínimo: {format_size(min_free_space)}",
                    metadata={"channel_id": channel_id, "channel_title": channel_title},
                )
            break

        if video.size > free_space:
            logger.warning(
                "msg#%d: vídeo demasiado grande (%s) para espacio disponible (%s)",
                msg_id,
                format_size(video.size),
                format_size(free_space),
            )
            history.record_error(msg_id, channel_id, "Espacio insuficiente")
            summary.errors += 1
            summary.details.append(f"msg#{msg_id}: ERROR - espacio insuficiente")
            continue

        output_path = build_output_path(output_dir, folder, msg_id, original_name)

        try:
            start = time.time()
            dynamic_timeout = max(600, int(video.size / 500000) * 1.5)
            downloaded_size, retries = await download_video(
                client, message, output_path,
                timeout=dynamic_timeout,
                max_retries=max_retries,
                channel_entity=channel_entity,
            )
            elapsed = time.time() - start
            summary.total_bytes += downloaded_size

            # Validate file integrity
            is_valid, error_msg = validate_video_file(output_path, expected_size=video.size)
            if not is_valid:
                logger.error("msg#%d: archivo descargado no es un vídeo válido: %s", msg_id, error_msg)
                summary.invalid_files += 1
                scanner.quarantine_file(output_path)
                history.record_invalid(
                    message_id=msg_id,
                    channel_id=channel_id,
                    filename=os.path.basename(output_path),
                    original_name=original_name,
                    error_message=error_msg,
                    output_path=output_path,
                )
                summary.details.append(f"msg#{msg_id}: INVÁLIDO - {original_name}")
                if notifier:
                    notifier.notify_error(
                        subject=f"Archivo inválido descargado #{msg_id}",
                        message=f"El archivo descargado no es un vídeo válido: {error_msg}",
                        metadata={
                            "channel_id": channel_id,
                            "channel_title": channel_title,
                            "video_id": str(msg_id),
                            "file_path": output_path,
                            "error": error_msg,
                        },
                    )
                continue

            # Security scan
            scan_result = scanner.scan(output_path)
            if scan_result.status == ScanResult.THREAT:
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
                            "file_path": output_path,
                        },
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

            history.increment_daily_count()
            session_download_count += 1
            summary.downloaded += 1
            summary.record_download(downloaded_size, elapsed)
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

            if session_download_count < max_per_run:
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
                        "error_message": str(e),
                    },
                )

    run_remaining = max(0, max_per_run - session_download_count)
    summary.print_summary(channel_title, run_remaining)

    # Send session completion notification with full summary as metadata
    if notifier and not dry_run:
        summary_dict = summary.to_dict(channel_title, run_remaining)
        message = (
            f"Descarga masiva completada para {channel_title}\n\n"
            f"Total descargados: {summary.downloaded}\n"
            f"Tiempo total: {summary.format_elapsed()}\n"
            f"Velocidad media: {summary.average_speed()}\n"
            f"Tiempo mín/máx: {summary.min_time()} / {summary.max_time()}\n"
            f"Velocidad mín/máx: {summary.slowest_speed()} / {summary.fastest_speed()}\n"
            f"Archivo mín/máx: {summary.smallest_file()} / {summary.largest_file()}\n"
            f"Tasa de éxito: {summary.success_rate()}"
        )
        notifier.notify_session_complete(
            subject=f"Sesión completada: {channel_title}",
            message=message,
            metadata=summary_dict,
        )

    return summary
