#!/bin/bash

# Script de pruebas automático para Telegram Video Downloader - Fase 2
# Verifica: Docker build, Python env, config, logging, notifications, volumes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
RESULTS_FILE="$SCRIPT_DIR/test_results.json"

VOLUME_PREFIX="$(basename "$SCRIPT_DIR")_"
IMAGE_NAME="${VOLUME_PREFIX}telegram-downloader"
VOL_LOGS="${VOLUME_PREFIX}telegram_logs"
VOL_NOTIF="${VOLUME_PREFIX}telegram_notifications"
VOL_DOWNLOADS="${VOLUME_PREFIX}telegram_downloads"
VOL_SESSION="${VOLUME_PREFIX}telegram_session"

cd "$PROJECT_DIR"

TIMESTAMP=$(date -Iseconds)
TESTS=()
PASSED=0
FAILED=0
SKIPPED=0

add_result() {
    local name="$1" status="$2" message="$3" details="$4"
    TESTS+=("{\"name\":\"$name\",\"status\":\"$status\",\"message\":\"$message\",\"details\":\"$details\"}")
    if [ "$status" = "pass" ]; then PASSED=$((PASSED + 1))
    elif [ "$status" = "fail" ]; then FAILED=$((FAILED + 1))
    else SKIPPED=$((SKIPPED + 1)); fi
}

echo "=========================================="
echo "  Telegram Video Downloader - Fase 2 Tests"
echo "=========================================="
echo ""

# Test 1: Build
echo "[Test 1] Construcción de imagen Docker..."
BUILD_START=$(date +%s)
if docker compose -f "$COMPOSE_FILE" build 2>&1 | tail -3; then
    BUILD_TIME=$(( $(date +%s) - BUILD_START ))
    add_result "docker_build" "pass" "Imagen construida" "Tiempo: ${BUILD_TIME}s"
    echo "  ✓ PASADO (${BUILD_TIME}s)"
else
    add_result "docker_build" "fail" "Error al construir" ""
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 2: Python env
echo "[Test 2] Entorno Python..."
OUT=$(docker run --rm --entrypoint "" "$IMAGE_NAME" python -c "
import telethon, yaml, dotenv, logging.handlers
print('telethon:', telethon.__version__)
print('All imports OK')
" 2>&1)
if echo "$OUT" | grep -q "All imports OK"; then
    add_result "python_env" "pass" "Imports OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "python_env" "fail" "Error imports" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 3: Config
echo "[Test 3] Carga de configuración..."
OUT=$(docker run --rm --entrypoint "" -v "$(pwd)/config.yaml:/app/config.yaml:ro" -w /app "$IMAGE_NAME" python -c "
import yaml
with open('config.yaml') as f: config = yaml.safe_load(f)
print('session:', config.get('session_name'))
print('output_dir:', config.get('output_dir'))
print('security:', config.get('security', {}).get('enabled'))
print('Config OK')
" 2>&1)
if echo "$OUT" | grep -q "Config OK"; then
    add_result "config" "pass" "Config OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "config" "fail" "Error config" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 4: Logging
echo "[Test 4] Logging..."
docker run --rm --entrypoint "" -v "${VOL_LOGS}:/app/logs" -w /app "$IMAGE_NAME" python -c "
import sys; sys.path.insert(0, '/app')
from src.logger import setup_logging
setup_logging('INFO', '/app/logs')
import logging; logging.getLogger('test').info('Test log')
print('Logging OK')
" 2>&1
LOG_FILE=$(docker run --rm -v "${VOL_LOGS}:/app/logs" alpine ls /app/logs/telegram-downloader.log 2>/dev/null || echo "")
if [ -n "$LOG_FILE" ]; then
    LINES=$(docker run --rm -v "${VOL_LOGS}:/app/logs" alpine wc -l /app/logs/telegram-downloader.log | awk '{print $1}')
    add_result "logging" "pass" "Log creado" "$LINES líneas"
    echo "  ✓ PASADO ($LINES líneas)"
else
    add_result "logging" "fail" "No se creó log" ""
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 5: Notificaciones
echo "[Test 5] Notificaciones..."
docker run --rm -v "${VOL_NOTIF}:/app/notifications" alpine sh -c "rm -f /app/notifications/notifications.json && chmod 777 /app/notifications" 2>/dev/null || true
OUT=$(docker run --rm --entrypoint "" -v "${VOL_NOTIF}:/app/notifications" -e NOTIFICATION_EMAIL=test@example.com -w /app "$IMAGE_NAME" python src/test_notifications.py 2>&1)
if echo "$OUT" | grep -q "Notificaciones generadas"; then
    COUNT=$(docker run --rm -v "${VOL_NOTIF}:/app/notifications" alpine cat /app/notifications/notifications.json 2>&1 | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    add_result "notifications" "pass" "Notificaciones creadas" "$COUNT notificaciones"
    echo "  ✓ PASADO ($COUNT notificaciones)"
else
    add_result "notifications" "fail" "Error notificaciones" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 6: Estructura notificaciones
echo "[Test 6] Estructura JSON notificaciones..."
OUT=$(docker run --rm -v "${VOL_NOTIF}:/app/notifications" alpine cat /app/notifications/notifications.json 2>&1 | python3 -c "
import sys,json
data=json.load(sys.stdin)
n=data[0]
keys=['id','timestamp','type','from','to','subject','message','sent','metadata']
missing=[k for k in keys if k not in n]
if missing: print(f'Faltan: {missing}'); sys.exit(1)
print(f'Tipos: {set(x[\"type\"] for x in data)}')
print(f'Total: {len(data)}')
" 2>&1)
if [ $? -eq 0 ]; then
    add_result "notif_structure" "pass" "Estructura OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "notif_structure" "fail" "Estructura incorrecta" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 7: Volúmenes
echo "[Test 7] Volúmenes..."
VOLS=$(docker volume ls --format '{{.Name}}' | grep "${VOLUME_PREFIX}telegram")
FOUND=0
for v in telegram_downloads telegram_logs telegram_notifications telegram_session; do
    echo "$VOLS" | grep -q "$v" && FOUND=$((FOUND + 1))
done
if [ "$FOUND" -eq 4 ]; then
    add_result "volumes" "pass" "4/4 volúmenes" ""
    echo "  ✓ PASADO (4/4)"
else
    add_result "volumes" "fail" "Faltan volúmenes" "$FOUND/4"
    echo "  ✗ FALLIDO ($FOUND/4)"
fi
echo ""

# Test 8: Imagen
echo "[Test 8] Imagen Docker..."
SIZE=$(docker images "$IMAGE_NAME" --format '{{.Size}}' 2>/dev/null || echo "N/A")
if [ "$SIZE" != "N/A" ]; then
    add_result "image" "pass" "Imagen existe" "Tamaño: $SIZE"
    echo "  ✓ PASADO ($SIZE)"
else
    add_result "image" "fail" "Imagen no encontrada" "$IMAGE_NAME"
    echo "  ✗ FALLIDO"
fi
echo ""

# Resumen
TOTAL=$((PASSED + FAILED + SKIPPED))
cat > "$RESULTS_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "tests": [$(IFS=,; echo "${TESTS[*]}")],
  "summary": {"total": $TOTAL, "passed": $PASSED, "failed": $FAILED, "skipped": $SKIPPED}
}
EOF

echo "=========================================="
echo "  Resumen: $TOTAL total | $PASSED ✓ | $FAILED ✗ | $SKIPPED ⊗"
echo "=========================================="
echo ""
echo "Ver notificaciones: bash docker/view_notifications.sh"
