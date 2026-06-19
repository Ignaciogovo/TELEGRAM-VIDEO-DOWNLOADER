"""Full channel verification scan.

Scans ALL videos in a channel from the beginning,
compares with download history, and downloads any missing ones.
Updates the checkpoint after completion.

Usage:
    python src/verify_all.py                    # Full scan, download missing
    python src/verify_all.py --dry-run          # Show what would be downloaded
    python src/verify_all.py --channel -100xxx  # Specific channel
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path for src module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from dotenv import load_dotenv
from telethon import TelegramClient, errors

from src.downloader import run_bulk_download
from src.history import DownloadHistory
from src.scanner import SecurityScanner
from src.notifier import Notifier
from src.logger import setup_logging

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config.yaml.

    Returns:
        Configuration dictionary.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Verificación completa: escanea TODOS los vídeos del canal desde el principio."
    )
    parser.add_argument(
        "--channel",
        type=str,
        default=None,
        help="Canal a verificar (username o ID). Debe estar en TELEGRAM_CHANNELS.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular sin descargar nada.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Ruta al archivo de configuración.",
    )
    return parser.parse_args()


async def main() -> None:
    """Main entry point for full verification."""
    args = parse_args()
    load_dotenv()
    config = load_config(args.config)
    
    output_dir = config.get("output_dir", "./downloads")
    log_dir = "/app/logs" if os.path.exists("/app/logs") else os.path.join(output_dir, "logs")
    setup_logging(config.get("log_level", "INFO"), log_dir)

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    channels_str = os.environ.get("TELEGRAM_CHANNELS", "")
    channels = [ch.strip() for ch in channels_str.split(",") if ch.strip()]

    if not channels:
        logger.error("TELEGRAM_CHANNELS no definida en .env")
        sys.exit(1)

    if args.channel:
        if args.channel not in channels:
            logger.error(
                "El canal '%s' no está en TELEGRAM_CHANNELS. Disponibles: %s",
                args.channel,
                ", ".join(channels),
            )
            sys.exit(1)
        target_channels = [args.channel]
    else:
        target_channels = channels

    db_path = os.path.join(output_dir, "history.db")
    history = DownloadHistory(db_path)

    security_config = config.get("security", {})
    scanner = SecurityScanner(
        enabled=security_config.get("enabled", True),
        engine=security_config.get("engine", "clamav"),
        scan_probability=security_config.get("scan_probability", 0.1),
        output_dir=output_dir,
    )

    notifications_dir = "/app/notifications" if os.path.exists("/app/notifications") else os.path.join(output_dir, "notifications")
    notifier = Notifier(
        notifications_dir=notifications_dir,
        notification_email=os.getenv("NOTIFICATION_EMAIL")
    )

    session_name = config.get("session_name", "telegram_downloader")
    client = TelegramClient(session_name, api_id, api_hash)

    try:
        await client.start()
        logger.info("Conectado a Telegram como %s", await client.get_me())
    except EOFError:
        logger.error("Sesión no autenticada y stdin no interactivo.")
        logger.error("Ejecuta 'python src/main.py' para autenticarte primero.")
        history.close()
        sys.exit(2)
    except errors.AuthKeyUnregisteredError:
        logger.error("Sesión no válida. Elimina el .session y vuelve a autenticar.")
        history.close()
        sys.exit(2)
    except Exception as e:
        logger.error("Error de conexión: %s", e)
        history.close()
        sys.exit(2)

    try:
        for channel_index, channel_username in enumerate(target_channels):
            logger.info("=" * 50)
            logger.info("Verificando canal: %s (índice: %d)", channel_username, channel_index)
            logger.info("=" * 50)

            try:
                entity = await client.get_entity(channel_username)
                channel_id = str(entity.id)
                channel_title = getattr(entity, "title", channel_username)

                logger.info("Canal: %s (ID: %s)", channel_title, channel_id)

                await run_bulk_download(
                    client=client,
                    channel_entity=entity,
                    channel_id=channel_id,
                    channel_title=channel_title,
                    config=config,
                    history=history,
                    scanner=scanner,
                    notifier=notifier,
                    dry_run=args.dry_run,
                    from_start=True,
                    channel_index=channel_index,
                )

            except errors.UsernameNotOccupiedError:
                logger.error("Canal '%s' no encontrado", channel_username)
            except errors.ChannelPrivateError:
                logger.error("No tienes acceso al canal '%s'", channel_username)
            except Exception as e:
                logger.error("Error procesando canal '%s': %s", channel_username, e)
                
                if notifier:
                    notifier.notify_error(
                        subject=f"Error procesando canal {channel_username}",
                        message=f"Error al procesar el canal {channel_username}",
                        metadata={
                            "channel_username": channel_username,
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
    finally:
        history.close()
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
