#!/bin/bash
# Punto de entrada del contenedor Docker
# Ejecuta el comando de telegram-downloader

set -e

# Si no hay sesión, mostrar mensaje
if [ ! -f "/app/session_data/telegram_downloader.session" ]; then
    echo "================================================"
    echo "  Primera ejecución - Autenticación requerida"
    echo "  Ejecuta con -it para introducir el código"
    echo "================================================"
fi

cd /app
exec python src/main.py "$@"
