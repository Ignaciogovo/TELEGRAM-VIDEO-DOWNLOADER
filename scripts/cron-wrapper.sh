#!/bin/bash
# Wrapper para cron: lanza el contenedor telegram-downloader si no está corriendo.
# Si lleva mas de MAX_CONTAINER_HOURS activo: para, notifica y relanza.
#
# Variables de entorno:
#   DOWNLOADS_DIR        - ruta del host para downloads (default: $(pwd)/downloads)
#   MAX_CONTAINER_HOURS   - umbral en horas (default: 12)
#   CONTAINER_NAME       - nombre del contenedor (default: telegram-downloader)
#   IMAGE_NAME           - imagen docker a lanzar (default: telegram-downloader)
#
# Ejemplo crontab (ubicación personalizada):
#   DOWNLOADS_DIR=/mnt/nas/telegram-descargas
#   0 * * * * cd /workspace/telegram-video-downloader && DOWNLOADS_DIR=/mnt/nas/telegram-descargas ./scripts/cron-wrapper.sh >> /var/log/telegram-cron.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

DOWNLOADS_DIR="${DOWNLOADS_DIR:-$(pwd)/downloads}"
CONTAINER_NAME="${CONTAINER_NAME:-telegram-downloader}"
IMAGE_NAME="${IMAGE_NAME:-telegram-downloader}"
MAX_HOURS="${MAX_CONTAINER_HOURS:-12}"
SESSION_DIR="$(pwd)/session_data"
NOTIFICATIONS_DIR="${DOWNLOADS_DIR}/notifications"

if [ ! -f .env ]; then
    echo "[$(date -Iseconds)] ERROR: no existe .env en $PROJECT_DIR" >&2
    exit 1
fi

mkdir -p "${DOWNLOADS_DIR}" "${SESSION_DIR}" "${NOTIFICATIONS_DIR}"

# Busca el contenedor por nombre exacto (^...$ para evitar matches parciales)
container_id=$(docker ps -q --filter "name=^${CONTAINER_NAME}$" || true)

if [ -z "$container_id" ]; then
    echo "[$(date -Iseconds)] Contenedor '${CONTAINER_NAME}' no esta corriendo. Lanzando..."
    docker run --rm \
        --name "${CONTAINER_NAME}" \
        --env-file .env \
        -v "${DOWNLOADS_DIR}:/app/downloads" \
        -v "${SESSION_DIR}:/app/session_data" \
        "${IMAGE_NAME}" --all
    echo "[$(date -Iseconds)] Contenedor lanzado y finalizado."
    exit 0
fi

# Contenedor en ejecución: comprobar duración
started=$(docker inspect --format '{{.Created}}' "$CONTAINER_NAME")
started_epoch=$(date -d "$started" +%s 2>/dev/null || echo 0)
now_epoch=$(date +%s)
hours_running=$(( (now_epoch - started_epoch) / 3600 ))

echo "[$(date -Iseconds)] Contenedor '${CONTAINER_NAME}' corriendo desde ${started} (${hours_running}h)."

if [ "$hours_running" -ge "$MAX_HOURS" ]; then
    echo "[$(date -Iseconds)] Supera umbral de ${MAX_HOURS}h. Deteniendo..."

    # 1. Parar contenedor stale
    docker stop "$CONTAINER_NAME" || true

    # 2. Notificar (datos capturados antes del stop)
    echo "[$(date -Iseconds)] Generando notificacion..."
    docker run --rm \
        --env-file .env \
        -v "${DOWNLOADS_DIR}:/app/downloads" \
        -v "${SESSION_DIR}:/app/session_data" \
        "${IMAGE_NAME}" \
        --notify-stale \
        --stale-hours "$hours_running" \
        --stale-threshold "$MAX_HOURS" \
        --stale-started "$started"

    # 3. Relanzar ejecución fresca
    echo "[$(date -Iseconds)] Lanzando nueva ejecucion..."
    docker run --rm \
        --name "${CONTAINER_NAME}" \
        --env-file .env \
        -v "${DOWNLOADS_DIR}:/app/downloads" \
        -v "${SESSION_DIR}:/app/session_data" \
        "${IMAGE_NAME}" --all
    echo "[$(date -Iseconds)] Ejecucion completada."
    exit 0
fi

echo "[$(date -Iseconds)] Contenedor dentro del umbral (${hours_running}h < ${MAX_HOURS}h). OK."
