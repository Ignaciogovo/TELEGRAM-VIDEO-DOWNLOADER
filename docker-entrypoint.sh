#!/bin/bash
# Punto de entrada del contenedor Docker
# - Aplica DOWNLOAD_LIMIT si está definido
# - Ejecuta el comando de telegram-downloader

set -e

# Sobrescribe max_downloads_per_run si DOWNLOAD_LIMIT está definido
if [ -n "$DOWNLOAD_LIMIT" ] && [ -f /app/config.yaml ]; then
    if [ -w /app/config.yaml ]; then
        sed -i "s/max_downloads_per_run:.*/max_downloads_per_run: $DOWNLOAD_LIMIT/" /app/config.yaml
        echo "[entrypoint] DOWNLOAD_LIMIT=$DOWNLOAD_LIMIT aplicado"
    else
        echo "[entrypoint] WARN: /app/config.yaml no escribible, DOWNLOAD_LIMIT ignorado"
    fi
fi

# Si no hay sesión, mostrar mensaje
if [ ! -f "/app/session_data/telegram_downloader.session" ]; then
    echo "================================================"
    echo "  Primera ejecución - Autenticación requerida"
    echo "  Ejecuta con -it para introducir el código"
    echo "================================================"
fi

cd /app
exec python src/main.py "$@"
