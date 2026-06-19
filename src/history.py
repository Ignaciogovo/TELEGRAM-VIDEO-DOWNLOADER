"""SQLite backend for download history, channel state, and daily stats."""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS downloads (
    message_id INTEGER PRIMARY KEY,
    channel_id TEXT NOT NULL,
    filename TEXT,
    original_name TEXT,
    size_bytes INTEGER,
    duration_seconds REAL,
    width INTEGER,
    height INTEGER,
    mime_type TEXT,
    status TEXT,
    output_path TEXT,
    category TEXT,
    scan_result TEXT,
    error_message TEXT,
    downloaded_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS channel_state (
    channel_id TEXT PRIMARY KEY,
    last_processed_message_id INTEGER DEFAULT 0,
    total_videos_found INTEGER DEFAULT 0,
    last_scan_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,
    download_count INTEGER DEFAULT 0
);
"""


class DownloadHistory:
    """Manages download history using SQLite."""

    def __init__(self, db_path: str) -> None:
        """Initialize the download history database.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        logger.info("Base de datos de historial: %s", db_path)

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def is_downloaded(self, message_id: int) -> bool:
        """Check if a message has already been downloaded.

        Args:
            message_id: The Telegram message ID.

        Returns:
            True if the message is already downloaded.
        """
        row = self.conn.execute(
            "SELECT status FROM downloads WHERE message_id = ?",
            (message_id,),
        ).fetchone()
        return row is not None and row["status"] == "downloaded"

    def is_skipped_short(self, message_id: int) -> bool:
        """Check if a message was skipped for being too short.

        Args:
            message_id: The Telegram message ID.

        Returns:
            True if the message was skipped as too short.
        """
        row = self.conn.execute(
            "SELECT status FROM downloads WHERE message_id = ?",
            (message_id,),
        ).fetchone()
        return row is not None and row["status"] == "skipped_short"

    def record_downloaded(
        self,
        message_id: int,
        channel_id: str,
        filename: str,
        original_name: Optional[str],
        size_bytes: int,
        duration_seconds: float,
        width: int,
        height: int,
        mime_type: str,
        output_path: str,
        category: str,
        scan_result: Optional[str],
    ) -> None:
        """Record a successfully downloaded video.

        Args:
            message_id: The Telegram message ID.
            channel_id: The channel identifier.
            filename: The saved filename.
            original_name: Original filename from Telegram.
            size_bytes: File size in bytes.
            duration_seconds: Video duration.
            width: Video width in pixels.
            height: Video height in pixels.
            mime_type: MIME type of the file.
            output_path: Full path where the file was saved.
            category: Assigned category from rules.
            scan_result: Security scan result.
        """
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO downloads
               (message_id, channel_id, filename, original_name,
                size_bytes, duration_seconds, width, height, mime_type,
                status, output_path, category, scan_result, downloaded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                message_id, channel_id, filename, original_name,
                size_bytes, duration_seconds, width, height, mime_type,
                "downloaded", output_path, category, scan_result, now,
            ),
        )
        self.conn.commit()

    def record_skipped_short(
        self,
        message_id: int,
        channel_id: str,
        duration_seconds: float,
        filename: Optional[str],
    ) -> None:
        """Record a video skipped for being too short.

        Args:
            message_id: The Telegram message ID.
            channel_id: The channel identifier.
            duration_seconds: Video duration.
            filename: Original filename if available.
        """
        self.conn.execute(
            """INSERT OR REPLACE INTO downloads
               (message_id, channel_id, filename, duration_seconds, status)
               VALUES (?, ?, ?, ?, 'skipped_short')""",
            (message_id, channel_id, filename, duration_seconds),
        )
        self.conn.commit()

    def record_error(
        self,
        message_id: int,
        channel_id: str,
        error_message: str,
        retry_count: int = 0,
    ) -> None:
        """Record a failed download attempt.

        Args:
            message_id: The Telegram message ID.
            channel_id: The channel identifier.
            error_message: Description of the error.
            retry_count: Number of retry attempts.
        """
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO downloads
               (message_id, channel_id, status, error_message,
                retry_count, downloaded_at)
               VALUES (?, ?, 'error', ?, ?, ?)""",
            (message_id, channel_id, error_message, retry_count, now),
        )
        self.conn.commit()

    def update_scan_result(
        self, message_id: int, scan_result: str
    ) -> None:
        """Update the scan result for a downloaded video.

        Args:
            message_id: The Telegram message ID.
            scan_result: The scan result ('clean', 'threat', 'skipped').
        """
        self.conn.execute(
            "UPDATE downloads SET scan_result = ? WHERE message_id = ?",
            (scan_result, message_id),
        )
        self.conn.commit()

    def get_channel_state(self, channel_id: str) -> dict:
        """Get the processing state for a channel.

        Args:
            channel_id: The channel identifier.

        Returns:
            Dictionary with last_processed_message_id and total_videos_found.
        """
        row = self.conn.execute(
            "SELECT * FROM channel_state WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
        if row:
            return dict(row)
        return {
            "channel_id": channel_id,
            "last_processed_message_id": 0,
            "total_videos_found": 0,
            "last_scan_at": None,
        }

    def update_channel_state(
        self,
        channel_id: str,
        last_processed_message_id: int,
        total_videos_found: int,
    ) -> None:
        """Update the processing state for a channel.

        Args:
            channel_id: The channel identifier.
            last_processed_message_id: The last message ID processed.
            total_videos_found: Total videos found in the channel.
        """
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO channel_state
               (channel_id, last_processed_message_id,
                total_videos_found, last_scan_at)
               VALUES (?, ?, ?, ?)""",
            (channel_id, last_processed_message_id, total_videos_found, now),
        )
        self.conn.commit()

    def get_daily_count(self, date_str: Optional[str] = None) -> int:
        """Get the number of downloads for a specific date.

        Args:
            date_str: Date in YYYY-MM-DD format. Defaults to today.

        Returns:
            Number of downloads on that date.
        """
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self.conn.execute(
            "SELECT download_count FROM daily_stats WHERE date = ?",
            (date_str,),
        ).fetchone()
        return row["download_count"] if row else 0

    def increment_daily_count(self, date_str: Optional[str] = None) -> int:
        """Increment the daily download counter.

        Args:
            date_str: Date in YYYY-MM-DD format. Defaults to today.

        Returns:
            The new count after incrementing.
        """
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.conn.execute(
            """INSERT INTO daily_stats (date, download_count)
               VALUES (?, 0)
               ON CONFLICT(date) DO NOTHING""",
            (date_str,),
        )
        self.conn.execute(
            "UPDATE daily_stats SET download_count = download_count + 1 WHERE date = ?",
            (date_str,),
        )
        self.conn.commit()
        return self.get_daily_count(date_str)

    def get_stats(self) -> dict:
        """Get overall download statistics.

        Returns:
            Dictionary with counts by status.
        """
        stats = {}
        for row in self.conn.execute(
            "SELECT status, COUNT(*) as count FROM downloads GROUP BY status"
        ):
            stats[row["status"]] = row["count"]

        total = self.conn.execute("SELECT COUNT(*) as c FROM downloads").fetchone()
        stats["total"] = total["c"]

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats["today_downloads"] = self.get_daily_count(today)

        return stats
