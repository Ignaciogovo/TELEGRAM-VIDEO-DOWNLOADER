"""Extract metadata from the last N videos in a channel without downloading."""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import InputMessagesFilterVideo

load_dotenv()

from src.utils import format_size, get_video_duration, get_video_resolution, get_filename


async def main() -> None:
    """Connect to Telegram and print metadata for the last N videos."""
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    channel_arg = sys.argv[2] if len(sys.argv) > 2 else None

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    channels_str = os.environ.get("TELEGRAM_CHANNELS", "")
    channels = [ch.strip() for ch in channels_str.split(",") if ch.strip()]

    if not channels:
        print("Error: TELEGRAM_CHANNELS no definida en .env")
        sys.exit(1)

    if channel_arg:
        if channel_arg not in channels:
            print(f"Error: canal '{channel_arg}' no está en TELEGRAM_CHANNELS. Disponibles: {', '.join(channels)}")
            sys.exit(1)
        target_channel = channel_arg
    else:
        target_channel = channels[0]

    # Convert numeric channel ID from string to int for Telethon
    try:
        target_channel = int(target_channel)
    except ValueError:
        pass

    client = TelegramClient("telegram_downloader", api_id, api_hash)
    await client.start()

    channel = await client.get_entity(target_channel)
    print(f"\nCanal: {channel.title}")
    print(f"Obteniendo metadatos de los últimos {count} vídeos...\n")

    header = (
        f"{'ID':<8} {'Duración':<10} {'Tamaño':<10} "
        f"{'Resolución':<12} {'Nombre':<40} {'Fecha':<12}"
    )
    print(header)
    print("-" * len(header))

    found = 0
    async for message in client.iter_messages(channel, filter=InputMessagesFilterVideo(), limit=200):
        if found >= count:
            break

        video = message.video
        if not video:
            continue

        duration = get_video_duration(video)
        width, height = get_video_resolution(video)
        filename = get_filename(video)
        date = message.date

        dur_str = f"{duration:.0f}s" if duration else "?"
        res_str = f"{width}x{height}" if width and height else "?"
        name_str = (filename or f"video_{message.id}")[:38]
        date_str = date.strftime("%Y-%m-%d") if date else "?"

        print(
            f"{message.id:<8} {dur_str:<10} {format_size(video.size):<10} "
            f"{res_str:<12} {name_str:<40} {date_str:<12}"
        )
        found += 1

    print(f"\nTotal vídeos encontrados: {found}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
