"""Telegram Video Downloader.

Bulk download with filtering, security scanning, resume support, and cron automation.
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

# Add project root to path for src module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from dotenv import load_dotenv
from telethon import TelegramClient, errors, types
from telethon.tl.types import InputMessagesFilterVideo
from tqdm import tqdm

from src.downloader import run_bulk_download
from src.history import DownloadHistory
from src.scanner import SecurityScanner
from src.logger import setup_logging
from src.utils import format_size

logger = logging.getLogger(__name__)


def load_env_credentials() -> tuple[int, str, list[str]]:
    """Load Telegram API credentials and channel list from environment variables.

    Reads TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_CHANNELS from environment.
    Supports .env files via python-dotenv.

    Returns:
        Tuple of (api_id, api_hash, channels_list).

    Raises:
        ValueError: If required environment variables are missing.
    """
    load_dotenv()

    api_id_str = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    channels_str = os.getenv("TELEGRAM_CHANNELS")

    if not api_id_str:
        raise ValueError(
            "TELEGRAM_API_ID no definida. Crea un archivo .env basado en .env.example."
        )
    if not api_hash:
        raise ValueError(
            "TELEGRAM_API_HASH no definida. Crea un archivo .env basado en .env.example."
        )
    if not channels_str:
        raise ValueError(
            "TELEGRAM_CHANNELS no definida. Crea un archivo .env basado en .env.example."
        )

    try:
        api_id = int(api_id_str)
    except ValueError:
        raise ValueError("TELEGRAM_API_ID debe ser un número entero.")

    channels = [ch.strip() for ch in channels_str.split(",") if ch.strip()]
    if not channels:
        raise ValueError(
            "TELEGRAM_CHANNELS debe contener al menos un canal."
        )

    return api_id, api_hash, channels


def load_config(config_path: str) -> dict:
    """Load configuration from a YAML file.

    Args:
        config_path: Path to the config.yaml file.

    Returns:
        Dictionary with configuration values.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


async def get_entity(
    client: TelegramClient, channel_username: str
) -> types.InputChannel:
    """Resolve a channel username or ID to a Telegram entity.

    Args:
        client: Authenticated TelegramClient.
        channel_username: Username or numeric channel ID.

    Returns:
        InputChannel entity.

    Raises:
        ValueError: If the channel cannot be found.
    """
    try:
        try:
            channel_id = int(channel_username)
            entity = await client.get_entity(channel_id)
            logger.info("Canal encontrado por ID: %s", entity.title)
            return entity
        except ValueError:
            pass

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
    except errors.ChannelPrivateError:
        logger.error("Canal '%s' es privado o no tienes acceso.", channel_username)
        raise ValueError(f"No tienes acceso al canal '{channel_username}'.")


async def find_latest_video_message(
    client: TelegramClient, channel_entity: types.InputChannel
) -> Optional[types.Message]:
    """Find the most recent message containing a video.

    Args:
        client: Authenticated TelegramClient.
        channel_entity: The channel entity.

    Returns:
        The most recent Message with a video, or None.
    """
    async for message in client.iter_messages(channel_entity, filter=InputMessagesFilterVideo(), limit=1):
        return message
    return None


def build_output_path(
    output_dir: str, message: types.Message
) -> str:
    """Build the full file path for a downloaded video.

    Args:
        output_dir: Directory where the video will be saved.
        message: The Telegram message containing the video.

    Returns:
        Full path where the video will be saved.
    """
    os.makedirs(output_dir, exist_ok=True)

    original_name = None
    video = message.video
    if video:
        for attr in video.attributes:
            if isinstance(attr, types.DocumentAttributeFilename):
                original_name = attr.file_name
                break

    if original_name:
        return os.path.join(output_dir, original_name)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return os.path.join(output_dir, f"video_{message.id}_{timestamp}.mp4")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Telegram Video Downloader - Fase 1 y 2"
    )
    parser.add_argument(
        "--message-id",
        type=int,
        default=None,
        help="ID del mensaje a descargar. Si no se especifica, descarga el más reciente.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Descargar todos los vídeos nuevos del canal (resume desde checkpoint).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular descarga sin descargar nada.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Mostrar estadísticas del historial de descargas.",
    )
    parser.add_argument(
        "--channel",
        type=str,
        default=None,
        help="Canal a usar (username o ID). Debe estar en TELEGRAM_CHANNELS.",
    )
    parser.add_argument(
        "--list-chats",
        action="store_true",
        help="Listar todos los chats de la cuenta y salir.",
    )
    parser.add_argument(
        "--find-chat",
        type=str,
        default=None,
        help="Buscar un chat por nombre e imprimir su ID. Coincidencia parcial.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Ruta al archivo de configuración (default: config.yaml).",
    )
    parser.add_argument(
        "--notify-stale",
        action="store_true",
        help="Generar notificación de contenedor stale y salir.",
    )
    parser.add_argument(
        "--stale-hours",
        type=int,
        default=None,
        help="Horas que lleva el contenedor corriendo (para --notify-stale).",
    )
    parser.add_argument(
        "--stale-threshold",
        type=int,
        default=None,
        help="Umbral de horas superado (para --notify-stale).",
    )
    parser.add_argument(
        "--stale-started",
        type=str,
        default=None,
        help="Timestamp de cuándo se arrancó el contenedor (para --notify-stale).",
    )
    return parser.parse_args()


async def run_single_download(
    client: TelegramClient,
    channel_entity: types.InputChannel,
    channel_username: str,
    config: dict,
    message_id: Optional[int] = None,
) -> None:
    """Run a single video download (Phase 1 mode).

    Args:
        client: Authenticated TelegramClient.
        channel_entity: The channel entity.
        channel_username: Channel identifier string.
        config: Configuration dictionary.
        message_id: Specific message ID, or None for latest.
    """
    output_dir = config.get("output_dir", "./downloads")

    if message_id is not None:
        message = (await client.get_messages(channel_entity, ids=message_id))[0]
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


async def run_stats(output_dir: str) -> None:
    """Print download statistics.

    Args:
        output_dir: Base output directory (for history.db path).
    """
    db_path = os.path.join(output_dir, "history.db")
    if not os.path.exists(db_path):
        logger.info("No hay historial de descargas aún.")
        return

    history = DownloadHistory(db_path)
    stats = history.get_stats()

    logger.info("=" * 50)
    logger.info("  ESTADÍSTICAS DE DESCARGAS")
    logger.info("=" * 50)
    logger.info("  Total registros:       %d", stats.get("total", 0))
    logger.info("  Descargados:           %d", stats.get("downloaded", 0))
    logger.info("  Saltados (cortos):     %d", stats.get("skipped_short", 0))
    logger.info("  Errores:               %d", stats.get("error", 0))
    logger.info("  Descargas hoy:         %d", stats.get("today_downloads", 0))
    logger.info("=" * 50)

    history.close()


async def main() -> None:
    """Main entry point."""
    args = parse_args()
    config = load_config(args.config)
    log_dir = "./downloads/logs"
    setup_logging(config.get("log_level", "INFO"), log_dir)

    if args.stats:
        output_dir = config.get("output_dir", "./downloads")
        await run_stats(output_dir)
        return

    if args.notify_stale:
        from src.notifier import Notifier
        output_dir = config.get("output_dir", "./downloads")
        notifier = Notifier(
            notifications_dir=f"{output_dir}/notifications",
            notification_email=os.getenv("NOTIFICATION_EMAIL"),
        )
        notifier.notify_error(
            subject=(
                f"Contenedor telegram-downloader lleva "
                f"mas de {args.stale_threshold}h en ejecucion"
            ),
            message=(
                f"El contenedor lleva {args.stale_hours}h activo "
                f"(umbral: {args.stale_threshold}h). "
                f"Puede estar stuck."
            ),
            metadata={
                "container_name": "telegram-downloader",
                "running_hours": args.stale_hours,
                "threshold_hours": args.stale_threshold,
                "started_at": args.stale_started,
                "source": "cron-wrapper",
            },
        )
        return

    api_id, api_hash, channels = load_env_credentials()
    session_name = config.get("session_name", "telegram_downloader")
    output_dir = config.get("output_dir", "./downloads")

    if os.getenv("DOWNLOAD_LIMIT"):
        config["max_downloads_per_run"] = int(os.getenv("DOWNLOAD_LIMIT"))

    if args.list_chats or args.find_chat is not None:
        from src.list_chats import list_chats_main
        rc = await list_chats_main(args.find_chat, session_name)
        sys.exit(rc)

    if args.channel is not None:
        if args.channel not in channels:
            logger.error(
                "El canal '%s' no está en TELEGRAM_CHANNELS. Disponibles: %s",
                args.channel,
                ", ".join(channels),
            )
            return
        target_channels = [args.channel]
    else:
        target_channels = channels

    client = TelegramClient(session_name, api_id, api_hash)

    try:
        await client.start()
        logger.info("Conectado a Telegram como %s", await client.get_me())

        if args.all:
            db_path = os.path.join(output_dir, "history.db")
            history = DownloadHistory(db_path)

            security_config = config.get("security", {})
            scanner = SecurityScanner(
                enabled=security_config.get("enabled", True),
                engine=security_config.get("engine", "clamav"),
                scan_probability=security_config.get("scan_probability", 0.1),
                output_dir=output_dir,
            )

            for channel_index, channel_username in enumerate(target_channels):
                logger.info("=" * 50)
                logger.info("Canal: %s (índice: %d)", channel_username, channel_index)
                logger.info("=" * 50)

                try:
                    entity = await get_entity(client, channel_username)
                    channel_id = str(entity.id)
                    channel_title = getattr(entity, "title", channel_username)

                    await run_bulk_download(
                        client=client,
                        channel_entity=entity,
                        channel_id=channel_id,
                        channel_title=channel_title,
                        config=config,
                        history=history,
                        scanner=scanner,
                        dry_run=args.dry_run,
                        from_start=False,
                        channel_index=channel_index,
                    )

                except ValueError as e:
                    logger.error("Error: %s", e)
                except Exception as e:
                    logger.error("Error procesando canal '%s': %s", channel_username, e)

            history.close()

        else:
            channel_username = target_channels[0]
            entity = await get_entity(client, channel_username)

            await run_single_download(
                client=client,
                channel_entity=entity,
                channel_username=channel_username,
                config=config,
                message_id=args.message_id,
            )

    except ValueError as e:
        logger.error("Error: %s", e)
    except errors.PhoneNumberInvalidError:
        logger.error("Credenciales incorrectas. Verifica TELEGRAM_API_ID y TELEGRAM_API_HASH.")
    except errors.AuthKeyUnregisteredError:
        logger.error("Sesión no válida. Elimina el archivo .session y vuelve a intentar.")
    except ConnectionError as e:
        logger.error("Error de conexión: %s", e)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
