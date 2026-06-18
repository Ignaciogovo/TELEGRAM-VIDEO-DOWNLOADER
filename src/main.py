"""Telegram Video Downloader - Phase 1.

Descarga un único vídeo de un canal de Telegram.
"""

import argparse
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from telethon import TelegramClient, errors, types
from tqdm import tqdm

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from a YAML file.

    Args:
        config_path: Path to the config.yaml file.

    Returns:
        Dictionary with configuration values.

    Raises:
        FileNotFoundError: If config file does not exist.
        yaml.YAMLError: If config file is not valid YAML.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def setup_logging(log_level: str) -> None:
    """Configure logging with the specified level.

    Args:
        log_level: Logging level as a string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_client(
    api_id: int, api_hash: str, session_name: str
) -> TelegramClient:
    """Create and return a Telethon TelegramClient.

    Args:
        api_id: Telegram API ID.
        api_hash: Telegram API hash.
        session_name: Base name for the session file.

    Returns:
        Configured TelegramClient instance.
    """
    return TelegramClient(session_name, api_id, api_hash)


async def get_entity(
    client: TelegramClient, channel_username: str
) -> types.InputChannel:
    """Resolve a channel username to a Telegram entity.

    Args:
        client: Authenticated TelegramClient.
        channel_username: Username of the channel (with or without @).

    Returns:
        InputChannel entity for the specified channel.

    Raises:
        ValueError: If the channel cannot be found.
    """
    try:
        entity = await client.get_entity(channel_username)
        logger.info("Canal encontrado: %s", entity.title)
        return entity
    except errors.FloodWaitError as e:
        logger.error("Rate limit. Esperar %d segundos.", e.seconds)
        raise
    except errors.UsernameNotOccupiedError:
        logger.error("Canal '%s' no encontrado.", channel_username)
        raise ValueError(f"Canal '{channel_username}' no encontrado.")
    except errors.UsernameInvalidError:
        logger.error("Username '%s' no válido.", channel_username)
        raise ValueError(f"Username '{channel_username}' no válido.")


async def find_latest_video_message(
    client: TelegramClient, channel_entity: types.InputChannel
) -> Optional[types.Message]:
    """Find the most recent message containing a video in the channel.

    Args:
        client: Authenticated TelegramClient.
        channel_entity: The channel entity to search.

    Returns:
        The most recent Message with a video, or None if no video found.
    """
    async for message in client.iter_messages(channel_entity, limit=50):
        if message.video:
            logger.info(
                "Último vídeo encontrado: message_id=%d", message.id
            )
            return message
    return None


async def get_message_by_id(
    client: TelegramClient, channel_entity: types.InputChannel, message_id: int
) -> Optional[types.Message]:
    """Fetch a specific message by its ID from the channel.

    Args:
        client: Authenticated TelegramClient.
        channel_entity: The channel entity to search.
        message_id: The ID of the message to fetch.

    Returns:
        The Message if found, or None.

    Raises:
        ValueError: If the message does not exist or has no video.
    """
    try:
        messages = await client.get_messages(
            channel_entity, ids=message_id
        )
        if messages is None:
            raise ValueError(f"Mensaje con id={message_id} no encontrado.")
        if not messages.video:
            raise ValueError(
                f"El mensaje con id={message_id} no contiene un vídeo."
            )
        return messages
    except errors.MessageIdInvalidError:
        raise ValueError(f"Mensaje con id={message_id} no válido.")


def build_output_path(
    output_dir: str, message: types.Message
) -> str:
    """Build the full file path for the downloaded video.

    Uses the original filename if available, otherwise falls back to
    message_id with a timestamp.

    Args:
        output_dir: Directory where the video will be saved.
        message: The Telegram message containing the video.

    Returns:
        Full path where the video will be saved.
    """
    os.makedirs(output_dir, exist_ok=True)

    original_name = None
    if message.video and message.video.document:
        for attr in message.video.document.attributes:
            if isinstance(attr, types.DocumentAttributeFilename):
                original_name = attr.file_name
                break

    if original_name:
        return os.path.join(output_dir, original_name)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return os.path.join(output_dir, f"video_{message.id}_{timestamp}.mp4")


async def download_video(
    client: TelegramClient, message: types.Message, output_path: str
) -> int:
    """Download a video from a Telegram message with progress bar.

    Args:
        client: Authenticated TelegramClient.
        message: The Telegram message containing the video.
        output_path: Full path where the video will be saved.

    Returns:
        Size of the downloaded file in bytes.
    """
    video = message.video
    file_size = video.size

    pbar = tqdm(
        total=file_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=f"Descargando message_id={message.id}",
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


def format_size(size_bytes: int) -> str:
    """Format a file size in bytes to a human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable size string (e.g., '15.3 MB').
    """
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Descarga un vídeo de un canal de Telegram."
    )
    parser.add_argument(
        "--message-id",
        type=int,
        default=None,
        help="ID del mensaje a descargar. Si no se especifica, descarga el más reciente.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Ruta al archivo de configuración (default: config.yaml).",
    )
    return parser.parse_args()


async def main() -> None:
    """Main entry point for the video downloader."""
    args = parse_args()
    config = load_config(args.config)

    setup_logging(config.get("log_level", "INFO"))

    api_id = config["api_id"]
    api_hash = config["api_hash"]
    session_name = config["session_name"]
    channel_username = config["channel_username"]
    output_dir = config["output_dir"]

    logger.info("Iniciando Telegram Video Downloader (Fase 1)")
    logger.info("Canal: %s", channel_username)

    client = create_client(api_id, api_hash, session_name)

    try:
        await client.start()
        logger.info("Conectado a Telegram como %s", await client.get_me())

        channel_entity = await get_entity(client, channel_username)

        if args.message_id is not None:
            message = await get_message_by_id(
                client, channel_entity, args.message_id
            )
        else:
            message = await find_latest_video_message(client, channel_entity)
            if message is None:
                logger.error("No se encontró ningún vídeo en el canal.")
                return

        output_path = build_output_path(output_dir, message)
        logger.info("Guardando en: %s", output_path)

        start_time = time.time()
        downloaded_size = await download_video(client, message, output_path)
        elapsed = time.time() - start_time

        logger.info("=" * 50)
        logger.info("Descarga completada")
        logger.info("Archivo: %s", output_path)
        logger.info("Tamaño: %s", format_size(downloaded_size))
        logger.info("Tiempo: %.1f segundos", elapsed)
        speed = downloaded_size / elapsed if elapsed > 0 else 0
        logger.info("Velocidad media: %s/s", format_size(int(speed)))
        logger.info("=" * 50)

    except ValueError as e:
        logger.error("Error: %s", e)
    except errors.PhoneNumberInvalidError:
        logger.error(
            "Credenciales incorrectas. Verifica api_id y api_hash en config.yaml."
        )
    except errors.AuthKeyUnregisteredError:
        logger.error(
            "Sesión no válida. Elimina el archivo .session y vuelve a intentar."
        )
    except ConnectionError as e:
        logger.error("Error de conexión: %s", e)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
