#!/bin/bash

# Script para ejecutar Telegram Video Downloader desde cron
# Comprueba si el contenedor está corriendo y lo inicia si es necesario

CONTAINER_NAME="telegram-downloader"
COMPOSE_FILE="docker/docker-compose.yml"

# Navegar al directorio del proyecto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "[$(date -Iseconds)] Verificando contenedor ${CONTAINER_NAME}..."

# Comprobar si el contenedor está corriendo
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[$(date -Iseconds)] Contenedor ${CONTAINER_NAME} ya está corriendo. Saltando ejecución."
    exit 0
fi

# Comprobar si el contenedor existe pero está detenido
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[$(date -Iseconds)] Contenedor ${CONTAINER_NAME} existe pero está detenido. Eliminándolo..."
    docker rm -f ${CONTAINER_NAME}
fi

# Ejecutar el contenedor
echo "[$(date -Iseconds)] Iniciando ${CONTAINER_NAME}..."
docker compose -f "$COMPOSE_FILE" up --abort-on-container-exit
EXIT_CODE=$?

echo "[$(date -Iseconds)] Ejecución completada con código de salida: ${EXIT_CODE}"
exit $EXIT_CODE
