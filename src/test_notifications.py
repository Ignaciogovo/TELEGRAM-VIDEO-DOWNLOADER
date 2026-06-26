"""Script para generar notificaciones de prueba."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.notifier import Notifier


def main() -> None:
    """Generar notificaciones de prueba."""
    notifications_dir = "/app/notifications" if os.path.exists("/app/notifications") else "./downloads/notifications"
    
    notifier = Notifier(
        notifications_dir=notifications_dir,
        notification_email=os.getenv("NOTIFICATION_EMAIL", "admin@example.com")
    )

    print("Generando notificaciones de prueba...")

    notifier.notify_error(
        subject="Error de prueba: Fallo de red",
        message="Se produjo un error de red al descargar un vídeo",
        metadata={
            "channel_id": "-1002523901612",
            "channel_title": "PeIis Variadas 🇪🇸",
            "video_id": "999",
            "error_type": "ConnectionError",
            "error_message": "Connection timed out"
        }
    )

    notifier.notify_threat(
        subject="Amenaza detectada: Malware en vídeo",
        message="ClamAV detectó una amenaza en un vídeo descargado",
        metadata={
            "channel_id": "-1002523901612",
            "channel_title": "PeIis Variadas 🇪🇸",
            "video_id": "998",
            "scan_result": "threat",
            "scan_details": "ClamAV: Win.Test.Malware_1234 FOUND",
            "file_path": "/app/downloads/peliculas/suspicious_video.mp4"
        }
    )

    notifier.notify_error(
        subject="Error de prueba: Límite de API",
        message="Se alcanzó el límite de la API de Telegram",
        metadata={
            "channel_id": "-1002523901612",
            "channel_title": "PeIis Variadas 🇪🇸",
            "video_id": "997",
            "error_type": "FloodWaitError",
            "error_message": "FloodWaitError: A wait of 30 seconds is required"
        }
    )

    notifications_file = os.path.join(notifications_dir, "notifications.json")
    with open(notifications_file, "r", encoding="utf-8") as f:
        notifications = json.load(f)

    print(f"Notificaciones generadas: {len(notifications)}")
    print(f"Archivo: {notifications_file}")
    print("\nÚltima notificación:")
    print(json.dumps(notifications[-1], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
