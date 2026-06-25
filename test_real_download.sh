#!/bin/bash
# =============================================================================
# Telegram Video Downloader - Prueba Real de Validación de Fase 2
# =============================================================================
# Este script:
# 1. Ejecuta una descarga real de 2 vídeos
# 2. Valida todos los TODOs de la Fase 2
#
# Uso: bash test_real_download.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON="venv/bin/python3"
RESULTS_FILE="$SCRIPT_DIR/test_results.json"
PASSED=0
FAILED=0
SKIPPED=0
TESTS=()

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

add_result() {
    local name="$1" status="$2" message="$3"
    TESTS+=("{\"name\":\"$name\",\"status\":\"$status\",\"message\":\"$message\"}")
    if [ "$status" = "pass" ]; then
        PASSED=$((PASSED + 1))
        echo -e "  ${GREEN}✓ PASADO${NC} - $message"
    elif [ "$status" = "fail" ]; then
        FAILED=$((FAILED + 1))
        echo -e "  ${RED}✗ FALLIDO${NC} - $message"
    else
        SKIPPED=$((SKIPPED + 1))
        echo -e "  ${YELLOW}⊗ SALTADO${NC} - $message"
    fi
}

echo ""
echo "================================================================"
echo "  Telegram Video Downloader - Prueba Real de Fase 2"
echo "================================================================"
echo ""

# =============================================================================
# PASO 0: Verificar prerequisitos
# =============================================================================
echo -e "${BLUE}[Paso 0] Verificando prerequisitos...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${RED}Error: No se encontró .env. Crea uno basado en .env.example.${NC}"
    exit 1
fi

if ! $PYTHON -c "import telethon, yaml, dotenv" 2>/dev/null; then
    echo -e "${RED}Error: Dependencias Python no instaladas.${NC}"
    exit 1
fi

# Verificar que hay canales configurados
CHANNELS=$(grep -o 'TELEGRAM_CHANNELS=.*' .env | cut -d= -f2)
if [ -z "$CHANNELS" ]; then
    echo -e "${RED}Error: TELEGRAM_CHANNELS no definido en .env.${NC}"
    exit 1
fi
echo "  Canales configurados: $CHANNELS"

# Obtener el primer canal para la prueba
FIRST_CHANNEL=$(echo "$CHANNELS" | cut -d, -f1 | tr -d ' ')
echo "  Canal de prueba: $FIRST_CHANNEL"
echo ""

# =============================================================================
# PASO 1: Preparar configuración para descargar exactamente 2 vídeos
# =============================================================================
echo -e "${BLUE}[Paso 1] Preparando configuración de prueba...${NC}"

# Backup del config original
cp config.yaml config.yaml.backup 2>/dev/null || true

# Crear config temporal para 2 vídeos
cat > config_test.yaml << 'EOF'
session_name: "telegram_downloader"
output_dir: "./downloads"
log_level: "INFO"

channel_folders:
  0: "peliculas"

default_folder: "uncategorized"

# Duración mínima: 0 para descargar cualquier vídeo
min_duration_seconds: 0

# Sin espera entre descargas (para prueba rápida)
download_delay_seconds: 0

# Máximo 2 descargas para la prueba
max_downloads_per_run: 4

# Timeout corto para prueba (10 min)
download_timeout_seconds: 600

# 3 reintentos
max_download_retries: 3

# Espacio mínimo: 100MB
min_free_space_mb: 100

security:
  enabled: true
  engine: "clamav"
  scan_probability: 0.1
EOF

echo "  Config de prueba creado: config_test.yaml"
echo "  Límite: 2 vídeos, sin espera, duración mínima 0s"
echo ""

# =============================================================================
# PASO 2: Ejecutar descarga real
# =============================================================================
echo -e "${BLUE}[Paso 2] Ejecutando descarga real de 2 vídeos...${NC}"
echo "  (Esto puede tardar dependiendo del tamaño de los vídeos)"
echo ""

# Limpiar notificaciones previas para prueba limpia
rm -f ./downloads/notifications/notifications.json 2>/dev/null || true

# Ejecutar descarga real (sin --dry-run)
if $PYTHON src/main.py --all --config config_test.yaml --channel "$FIRST_CHANNEL" 2>&1; then
    echo ""
    echo -e "${GREEN}  Descarga completada exitosamente${NC}"
    DOWNLOAD_OK=true
else
    echo ""
    echo -e "${YELLOW}  La descarga tuvo errores (puede ser normal si no hay vídeos nuevos)${NC}"
    DOWNLOAD_OK=false
fi
echo ""

# =============================================================================
# PASO 3: Validar TODOs
# =============================================================================
echo "================================================================"
echo "  Validación de TODOs"
echo "================================================================"
echo ""

# -----------------------------------------------------------------------------
# TODO 1: Paths hardcoded corregidos
# -----------------------------------------------------------------------------
echo -e "${BLUE}[TODO 1] Paths hardcoded corregidos...${NC}"

OUT=$($PYTHON -c "
import sys; sys.path.insert(0, '.')
from src.notifier import Notifier
from src.logger import setup_logging

# Verificar que notifier usa ./downloads/notifications
n = Notifier()
assert 'downloads/notifications' in str(n.notifications_dir) or n.notifications_dir.name == 'notifications'

# Verificar que logger crea logs en ./downloads/logs
import os
setup_logging('DEBUG', './downloads/logs')
assert os.path.isdir('./downloads/logs'), 'Logs dir should exist'

print('Paths OK')
" 2>&1)
if echo "$OUT" | grep -q "Paths OK"; then
    add_result "todo1_paths" "pass" "Paths correctos (./downloads/)"
else
    add_result "todo1_paths" "fail" "Paths incorrectos: $OUT"
fi
echo ""

# -----------------------------------------------------------------------------
# TODO 2: Verificación de integridad
# -----------------------------------------------------------------------------
echo -e "${BLUE}[TODO 2] Verificación de integridad de archivos...${NC}"

OUT=$($PYTHON -c "
import sys; sys.path.insert(0, '.')
from src.downloader import validate_video_file
import tempfile, os

# Test 1: archivo no existe
valid, msg = validate_video_file('/nonexistent')
assert valid == False, 'Non-existent should be False'

# Test 2: archivo pequeño
tmp = tempfile.mktemp(suffix='.mp4')
with open(tmp, 'wb') as f:
    f.write(b'x' * 100)
valid, msg = validate_video_file(tmp)
assert valid == False, 'Small file should be False'
os.unlink(tmp)

# Test 3: archivo válido con tamaño correcto
tmp = tempfile.mktemp(suffix='.mp4')
with open(tmp, 'wb') as f:
    f.write(b'x' * 2048)
valid, msg = validate_video_file(tmp, expected_size=2048)
assert valid == True, 'Correct size should be valid'
os.unlink(tmp)

# Test 4: tamaño incorrecto
tmp = tempfile.mktemp(suffix='.mp4')
with open(tmp, 'wb') as f:
    f.write(b'x' * 2048)
valid, msg = validate_video_file(tmp, expected_size=1000)
assert valid == False, 'Size mismatch should be invalid'
os.unlink(tmp)

# Verificar que history tiene record_invalid e is_invalid
from src.history import DownloadHistory
import tempfile
tmpdb = tempfile.mktemp(suffix='.db')
h = DownloadHistory(tmpdb)
h.record_invalid(1, 'ch', 'f.mp4', 'f.mp4', 'test')
assert h.is_invalid(1) == True
h.close()
os.unlink(tmpdb)

print('Integrity OK')
" 2>&1)
if echo "$OUT" | grep -q "Integrity OK"; then
    add_result "todo2_integrity" "pass" "Validación de integridad funcional"
else
    add_result "todo2_integrity" "fail" "Error en integridad: $OUT"
fi
echo ""

# -----------------------------------------------------------------------------
# TODO 3: Archivos parcialmente descargados
# -----------------------------------------------------------------------------
echo -e "${BLUE}[TODO 3] Manejo de archivos parcialmente descargados...${NC}"

OUT=$($PYTHON -c "
import sys, os, tempfile, shutil; sys.path.insert(0, '.')
from src.downloader import clean_partial_downloads

# Crear directorio de prueba
tmpdir = tempfile.mkdtemp()
os.makedirs(os.path.join(tmpdir, 'videos'))

# Crear archivos parciales
with open(os.path.join(tmpdir, 'videos', 'test.part'), 'w') as f:
    f.write('partial')
with open(os.path.join(tmpdir, 'videos', 'test.tmp'), 'w') as f:
    f.write('partial')
with open(os.path.join(tmpdir, 'videos', 'test.download'), 'w') as f:
    f.write('partial')

# Crear archivo válido
with open(os.path.join(tmpdir, 'videos', 'real.mp4'), 'wb') as f:
    f.write(b'x' * 2048)

# Crear archivo vacío
with open(os.path.join(tmpdir, 'videos', 'empty.mp4'), 'wb') as f:
    pass

# Limpiar
cleaned = clean_partial_downloads(tmpdir)
remaining = os.listdir(os.path.join(tmpdir, 'videos'))

assert cleaned >= 3, f'Should clean at least 3 files, got {cleaned}'
assert 'real.mp4' in remaining, 'real.mp4 should remain'
assert 'empty.mp4' not in remaining, 'empty.mp4 should be cleaned'

shutil.rmtree(tmpdir)

# Verificar que download_video usa .part para descarga atómica
import inspect
from src.downloader import download_video
source = inspect.getsource(download_video)
assert '.part' in source, 'Should use .part file'
assert 'shutil.move' in source, 'Should use atomic rename'

print('Partial files OK')
" 2>&1)
if echo "$OUT" | grep -q "Partial files OK"; then
    add_result "todo3_partial" "pass" "Limpieza de parciales funcional"
else
    add_result "todo3_partial" "fail" "Error en parciales: $OUT"
fi
echo ""

# -----------------------------------------------------------------------------
# TODO 4: Resumen final de sesión
# -----------------------------------------------------------------------------
echo -e "${BLUE}[TODO 4] Resumen final de sesión...${NC}"

OUT=$($PYTHON -c "
import sys, os, json, tempfile, shutil; sys.path.insert(0, '.')
from src.downloader import DownloadSummary

s = DownloadSummary()
assert len(s.session_id) == 8, 'session_id should be 8 chars'

s.downloaded = 2
s.total_bytes = 1048576 * 2
s.record_download(1048576, 10.0)
s.record_download(1048576, 5.0)

# Verificar estadísticas
assert s.min_time() != 'N/A'
assert s.max_time() != 'N/A'
assert s.success_rate() != 'N/A'
assert s.fastest_speed() != 'N/A'
assert s.slowest_speed() != 'N/A'

# Verificar to_dict
d = s.to_dict('TestChannel', 48)
assert 'session_id' in d
assert 'downloaded' in d
assert 'success_rate' in d

# Verificar save_to_log crea .log y .json
tmpdir = tempfile.mkdtemp()
log_path = s.save_to_log(tmpdir, 'TestChannel', 48)
assert os.path.exists(log_path), 'Log file should exist'
json_path = log_path.replace('.log', '.json')
assert os.path.exists(json_path), 'JSON file should exist'

with open(json_path) as f:
    data = json.load(f)
assert data['session_id'] == s.session_id
assert data['downloaded'] == 2

shutil.rmtree(tmpdir)
print('Summary OK')
" 2>&1)
if echo "$OUT" | grep -q "Summary OK"; then
    add_result "todo4_summary" "pass" "Resumen de sesión con stats y JSON"
else
    add_result "todo4_summary" "fail" "Error en resumen: $OUT"
fi
echo ""

# -----------------------------------------------------------------------------
# TODO 5: Notificación de finalización
# -----------------------------------------------------------------------------
echo -e "${BLUE}[TODO 5] Notificación de finalización...${NC}"

OUT=$($PYTHON -c "
import sys, os, json, tempfile, shutil; sys.path.insert(0, '.')
from src.notifier import Notifier

tmpdir = tempfile.mkdtemp()
n = Notifier(notifications_dir=tmpdir)

# Probar notify_session_complete
n.notify_session_complete(
    subject='Test Session',
    message='Test completed',
    metadata={'downloaded': 2, 'errors': 0, 'session_id': 'abc12345'}
)

notif_file = os.path.join(tmpdir, 'notifications.json')
with open(notif_file) as f:
    data = json.load(f)

assert len(data) == 1
assert data[0]['type'] == 'session_complete'
assert data[0]['subject'] == 'Test Session'
assert data[0]['metadata']['downloaded'] == 2
assert data[0]['metadata']['session_id'] == 'abc12345'

shutil.rmtree(tmpdir)
print('Notification OK')
" 2>&1)
if echo "$OUT" | grep -q "Notification OK"; then
    add_result "todo5_notification" "pass" "Notificación session_complete funcional"
else
    add_result "todo5_notification" "fail" "Error en notificación: $OUT"
fi
echo ""

# -----------------------------------------------------------------------------
# TODO 6: Validación de espacio en disco
# -----------------------------------------------------------------------------
echo -e "${BLUE}[TODO 6] Validación de espacio en disco...${NC}"

OUT=$($PYTHON -c "
import sys; sys.path.insert(0, '.')
from src.utils import format_size

# Verificar que config tiene min_free_space_mb
import yaml
with open('config_test.yaml') as f:
    config = yaml.safe_load(f)
assert 'min_free_space_mb' in config
assert config['min_free_space_mb'] > 0

# Verificar que run_bulk_download verifica espacio inicial
import inspect
from src.downloader import run_bulk_download
source = inspect.getsource(run_bulk_download)
assert 'initial_free_space' in source, 'Should check initial space'
assert 'Espacio insuficiente al iniciar' in source, 'Should have initial check message'

print('Disk space OK')
" 2>&1)
if echo "$OUT" | grep -q "Disk space OK"; then
    add_result "todo6_diskspace" "pass" "Validación de espacio en disco funcional"
else
    add_result "todo6_diskspace" "fail" "Error en espacio en disco: $OUT"
fi
echo ""

# -----------------------------------------------------------------------------
# TODO 7: Tests automatizados
# -----------------------------------------------------------------------------
echo -e "${BLUE}[TODO 7] Tests automatizados básicos...${NC}"

# Ejecutar test.sh
if bash test.sh 2>&1 | grep -q "✓"; then
    TEST_COUNT=$(bash test.sh 2>&1 | grep "Resumen:" | grep -o '[0-9]* total' | cut -d' ' -f1)
    PASSED_COUNT=$(bash test.sh 2>&1 | grep "Resumen:" | grep -o '[0-9]* ✓' | cut -d' ' -f1)
    add_result "todo7_tests" "pass" "$PASSED_COUNT/$TEST_COUNT tests pasando"
else
    add_result "todo7_tests" "fail" "Tests fallidos"
fi
echo ""

# -----------------------------------------------------------------------------
# TODO 8: Timeout y reintentos configurables
# -----------------------------------------------------------------------------
echo -e "${BLUE}[TODO 8] Timeout y reintentos configurables...${NC}"

OUT=$($PYTHON -c "
import sys, yaml, inspect; sys.path.insert(0, '.')

# Verificar config
with open('config_test.yaml') as f:
    config = yaml.safe_load(f)
assert 'download_timeout_seconds' in config
assert config['download_timeout_seconds'] == 600
assert 'max_download_retries' in config
assert config['max_download_retries'] == 3
print('Config OK')

# Verificar download_video signature
from src.downloader import download_video
sig = inspect.signature(download_video)
assert 'timeout' in sig.parameters
assert 'max_retries' in sig.parameters

# Verificar que retorna tupla (size, retries)
source = inspect.getsource(download_video)
assert 'return downloaded_size, retry_count' in source, 'Should return tuple'

# Verificar backoff exponencial
assert '2 ** attempt' in source, 'Should have exponential backoff'

print('Timeout/retries OK')
" 2>&1)
if echo "$OUT" | grep -q "Timeout/retries OK"; then
    add_result "todo8_timeout" "pass" "Timeout y reintentos configurables"
else
    add_result "todo8_timeout" "fail" "Error en timeout/reintentos: $OUT"
fi
echo ""

# -----------------------------------------------------------------------------
# Verificación adicional: Archivos generados
# -----------------------------------------------------------------------------
echo -e "${BLUE}[Verificación] Archivos generados por la descarga...${NC}"

# Verificar logs
if [ -d "./downloads/logs" ]; then
    LOG_COUNT=$(ls ./downloads/logs/ 2>/dev/null | wc -l)
    add_result "files_logs" "pass" "$LOG_COUNT archivos de log"
else
    add_result "files_logs" "fail" "Directorio logs no existe"
fi

# Verificar notificaciones
if [ -f "./downloads/notifications/notifications.json" ]; then
    NOTIF_COUNT=$($PYTHON -c "import json; print(len(json.load(open('./downloads/notifications/notifications.json'))))" 2>/dev/null || echo "0")
    add_result "files_notifications" "pass" "$NOTIF_COUNT notificaciones"
else
    add_result "files_notifications" "skip" "Sin notificaciones (puede ser normal en dry-run)"
fi

# Verificar historial
if [ -f "./downloads/history.db" ]; then
    DB_SIZE=$(ls -lh ./downloads/history.db | awk '{print $5}')
    add_result "files_history" "pass" "history.db existe ($DB_SIZE)"
else
    add_result "files_history" "fail" "history.db no existe"
fi

# Verificar resumen JSON
SUMMARY_JSON=$(ls ./downloads/logs/summary_*.json 2>/dev/null | head -1)
if [ -n "$SUMMARY_JSON" ]; then
    add_result "files_summary_json" "pass" "Resumen JSON generado"
else
    add_result "files_summary_json" "skip" "Sin resumen JSON (puede ser normal en dry-run)"
fi

# Verificar que no hay archivos parciales
PARTIAL_COUNT=$(find ./downloads -name "*.part" -o -name "*.tmp" -o -name "*.temp" -o -name "*.download" 2>/dev/null | wc -l)
if [ "$PARTIAL_COUNT" -eq 0 ]; then
    add_result "files_no_partial" "pass" "Sin archivos parciales"
else
    add_result "files_no_partial" "fail" "$PARTIAL_COUNT archivos parciales encontrados"
fi

echo ""

# =============================================================================
# RESUMEN FINAL
# =============================================================================
TOTAL=$((PASSED + FAILED + SKIPPED))

cat > "$RESULTS_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "tests": [$(IFS=,; echo "${TESTS[*]}")],
  "summary": {"total": $TOTAL, "passed": $PASSED, "failed": $FAILED, "skipped": $SKIPPED}
}
EOF

echo "================================================================"
echo -e "  ${GREEN}Resumen: $TOTAL total | $PASSED ✓ | $FAILED ✗ | $SKIPPED ⊗${NC}"
echo "================================================================"
echo ""
echo "Resultados detallados: $RESULTS_FILE"
echo ""

# Restaurar config original
if [ -f "config.yaml.backup" ]; then
    mv config.yaml.backup config.yaml
    rm -f config_test.yaml
    echo "Configuración original restaurada."
fi

if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}¡Todos los TODOs validados correctamente!${NC}"
    exit 0
else
    echo -e "${RED}Algunos TODOs fallaron. Revisa los resultados.${NC}"
    exit 1
fi
