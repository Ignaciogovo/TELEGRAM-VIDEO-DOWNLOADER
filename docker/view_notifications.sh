#!/bin/bash

# Script para ver las notificaciones generadas por el Telegram Video Downloader

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VOLUME_PREFIX="$(basename "$SCRIPT_DIR")_"
VOL_NOTIF="${VOLUME_PREFIX}telegram_notifications"

echo "=========================================="
echo "  Notificaciones del Telegram Video Downloader"
echo "=========================================="
echo ""

# Verificar si existe el archivo de notificaciones
EXISTS=$(docker run --rm -v "${VOL_NOTIF}:/app/notifications" alpine test -f /app/notifications/notifications.json && echo "yes" || echo "no")

if [ "$EXISTS" = "no" ]; then
    echo "No se encontró el archivo de notificaciones."
    echo "Ejecuta los tests primero: bash docker/test.sh"
    exit 1
fi

# Mostrar resumen
echo "Resumen de notificaciones:"
docker run --rm -v "${VOL_NOTIF}:/app/notifications" alpine cat /app/notifications/notifications.json 2>&1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'  Total: {len(data)} notificaciones')
print()
types = {}
for n in data:
    t = n.get('type', 'unknown')
    types[t] = types.get(t, 0) + 1
for t, c in types.items():
    print(f'  - {t}: {c}')
"
echo ""
echo "=========================================="
echo "  Detalle de notificaciones:"
echo "=========================================="
echo ""

# Mostrar cada notificación
docker run --rm -v "${VOL_NOTIF}:/app/notifications" alpine cat /app/notifications/notifications.json 2>&1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
for i, notif in enumerate(data, 1):
    print(f'--- Notificación {i} ---')
    print(f'  ID:        {notif[\"id\"]}')
    print(f'  Timestamp: {notif[\"timestamp\"]}')
    print(f'  Tipo:      {notif[\"type\"]}')
    print(f'  De:        {notif[\"from\"]}')
    print(f'  A:         {notif[\"to\"]}')
    print(f'  Asunto:    {notif[\"subject\"]}')
    print(f'  Enviado:   {\"Sí\" if notif[\"sent\"] else \"No\"}')
    print()
    if notif.get('metadata'):
        print(f'  Metadata:')
        for k, v in notif['metadata'].items():
            print(f'    {k}: {v}')
    print()
"

echo "=========================================="
echo "  Ver JSON completo:"
echo "=========================================="
echo "  docker run --rm -v ${VOL_NOTIF}:/app/notifications alpine cat /app/notifications/notifications.json | python3 -m json.tool"
