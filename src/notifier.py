"""Módulo de notificaciones para errores y amenazas."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class Notifier:
    """Gestiona notificaciones JSON para el servicio de envío externo."""

    def __init__(
        self,
        notifications_dir: str = "./downloads/notifications",
        notification_email: Optional[str] = None
    ) -> None:
        """Inicializar notificador.

        Args:
            notifications_dir: Directorio donde se guardan las notificaciones.
            notification_email: Email destino de las notificaciones.
        """
        self.notifications_dir = Path(notifications_dir)
        self.notifications_dir.mkdir(parents=True, exist_ok=True)
        self.notifications_file = self.notifications_dir / "notifications.json"
        
        self.notification_email = notification_email or os.getenv(
            "NOTIFICATION_EMAIL", "admin@example.com"
        )

    def _load_notifications(self) -> list[dict]:
        """Cargar notificaciones existentes.

        Returns:
            Lista de notificaciones.
        """
        if not self.notifications_file.exists():
            return []
        
        with open(self.notifications_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_notifications(self, notifications: list[dict]) -> None:
        """Guardar notificaciones.

        Args:
            notifications: Lista de notificaciones.
        """
        with open(self.notifications_file, "w", encoding="utf-8") as f:
            json.dump(notifications, f, indent=2, ensure_ascii=False)

    def notify_error(
        self,
        subject: str,
        message: str,
        metadata: Optional[dict] = None
    ) -> None:
        """Crear notificación de error.

        Args:
            subject: Asunto de la notificación.
            message: Mensaje de error.
            metadata: Metadatos adicionales.
        """
        self._add_notification(
            notification_type="error",
            subject=subject,
            message=message,
            metadata=metadata or {}
        )

    def notify_threat(
        self,
        subject: str,
        message: str,
        metadata: Optional[dict] = None
    ) -> None:
        """Crear notificación de amenaza detectada.

        Args:
            subject: Asunto de la notificación.
            message: Mensaje de amenaza.
            metadata: Metadatos adicionales.
        """
        self._add_notification(
            notification_type="threat_detected",
            subject=subject,
            message=message,
            metadata=metadata or {}
        )

    def _add_notification(
        self,
        notification_type: str,
        subject: str,
        message: str,
        metadata: dict
    ) -> None:
        """Agregar notificación al archivo.

        Args:
            notification_type: Tipo de notificación.
            subject: Asunto.
            message: Mensaje.
            metadata: Metadatos.
        """
        notifications = self._load_notifications()

        full_message = f"{message}\n\nMetadata:\n{json.dumps(metadata, indent=2, ensure_ascii=False)}"

        notification = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": notification_type,
            "from": "telegram-downloader@local",
            "to": self.notification_email,
            "subject": subject,
            "message": full_message,
            "sent": 0,
            "metadata": metadata
        }

        notifications.append(notification)
        self._save_notifications(notifications)
