#!/bin/bash
set -e

echo "[$(date -Iseconds)] Iniciando Telegram Video Downloader..."

# Asegurar permisos de escritura en volúmenes montados
for dir in /app/downloads /app/logs /app/notifications /app/session; do
    if [ -d "$dir" ]; then
        chmod -R 777 "$dir" 2>/dev/null || true
    fi
done

# Ejecutar verificación completa (load_dotenv() carga .env dentro de Python)
python src/verify_all.py "$@"

echo "[$(date -Iseconds)] Verificación completada."
