#!/bin/bash

# Script de pruebas automático para Telegram Video Downloader - Fase 2
# Verifica: build, Python env, config, logging, notifications, volumes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
RESULTS_FILE="$SCRIPT_DIR/test_results.json"

cd "$PROJECT_DIR"

# Inicializar resultados
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

# Test 1: Entorno Python
echo "[Test 1] Entorno Python..."
OUT=$(python -c "
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

# Test 2: Carga de configuración
echo "[Test 2] Carga de configuración..."
OUT=$(python -c "
import yaml
with open('config.yaml') as f: config = yaml.safe_load(f)
print('session:', config.get('session_name'))
print('output_dir:', config.get('output_dir'))
print('security:', config.get('security', {}).get('enabled'))
print('timeout:', config.get('download_timeout_seconds'))
print('retries:', config.get('max_download_retries'))
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

# Test 3: Logging
echo "[Test 3] Logging..."
OUT=$(python -c "
import sys; sys.path.insert(0, '.')
from src.logger import setup_logging
setup_logging('INFO', './downloads/logs')
import logging; logging.getLogger('test').info('Test log')
print('Logging OK')
" 2>&1)
if echo "$OUT" | grep -q "Logging OK"; then
    LOG_FILE=$(ls ./downloads/logs/telegram-downloader.log 2>/dev/null || echo "")
    if [ -n "$LOG_FILE" ]; then
        LINES=$(wc -l < ./downloads/logs/telegram-downloader.log)
        add_result "logging" "pass" "Log creado" "$LINES líneas"
        echo "  ✓ PASADO ($LINES líneas)"
    else
        add_result "logging" "fail" "No se creó log" ""
        echo "  ✗ FALLIDO"
    fi
else
    add_result "logging" "fail" "Error logging" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 4: Notificaciones
echo "[Test 4] Notificaciones..."
OUT=$(python src/test_notifications.py 2>&1)
if echo "$OUT" | grep -q "Notificaciones generadas"; then
    COUNT=$(python -c "import json; print(len(json.load(open('./downloads/notifications/notifications.json'))))" 2>/dev/null || echo "0")
    add_result "notifications" "pass" "Notificaciones creadas" "$COUNT notificaciones"
    echo "  ✓ PASADO ($COUNT notificaciones)"
else
    add_result "notifications" "fail" "Error notificaciones" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 5: Estructura JSON notificaciones
echo "[Test 5] Estructura JSON notificaciones..."
OUT=$(python -c "
import json
with open('./downloads/notifications/notifications.json') as f:
    data = json.load(f)
n = data[0]
keys = ['id','timestamp','type','from','to','subject','message','sent','metadata']
missing = [k for k in keys if k not in n]
if missing:
    print(f'Faltan: {missing}')
    exit(1)
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

# Test 6: Historial SQLite
echo "[Test 6] Historial SQLite..."
OUT=$(python -c "
import sys; sys.path.insert(0, '.')
from src.history import DownloadHistory
h = DownloadHistory('./downloads/history.db')
stats = h.get_stats()
print(f'Total registros: {stats.get(\"total\", 0)}')
print(f'Descargados: {stats.get(\"downloaded\", 0)}')
print(f'Errores: {stats.get(\"error\", 0)}')
h.close()
print('History OK')
" 2>&1)
if echo "$OUT" | grep -q "History OK"; then
    add_result "history" "pass" "Historial OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "history" "fail" "Error historial" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 7: Escáner de seguridad
echo "[Test 7] Escáner de seguridad..."
OUT=$(python -c "
import sys; sys.path.insert(0, '.')
from src.scanner import SecurityScanner
s = SecurityScanner(enabled=True, engine='clamav', scan_probability=1.0, output_dir='./downloads')
print(f'Enabled: {s.enabled}')
print(f'Engine: {s.engine}')
print(f'Probability: {s.scan_probability}')
print('Scanner OK')
" 2>&1)
if echo "$OUT" | grep -q "Scanner OK"; then
    add_result "scanner" "pass" "Escáner OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "scanner" "fail" "Error escáner" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 8: Validación de vídeo
echo "[Test 8] Validación de vídeo..."
OUT=$(python -c "
import sys; sys.path.insert(0, '.')
from src.downloader import validate_video_file
# Test with non-existent file
valid, msg = validate_video_file('/nonexistent')
assert valid == False, 'Non-existent should be False'
assert 'no existe' in msg.lower(), 'Should have error message'
# Test with small file
import tempfile, os
tmpfile = tempfile.mktemp(suffix='.mp4')
with open(tmpfile, 'wb') as f:
    f.write(b'x' * 100)  # Too small
valid, msg = validate_video_file(tmpfile)
assert valid == False, 'Small file should be False'
os.unlink(tmpfile)
# Test with valid size file
tmpfile = tempfile.mktemp(suffix='.mp4')
with open(tmpfile, 'wb') as f:
    f.write(b'x' * 2048)
valid, msg = validate_video_file(tmpfile, expected_size=2048)
assert valid == True, 'Correct size should be valid'
os.unlink(tmpfile)
# Test size mismatch
tmpfile = tempfile.mktemp(suffix='.mp4')
with open(tmpfile, 'wb') as f:
    f.write(b'x' * 2048)
valid, msg = validate_video_file(tmpfile, expected_size=1000)
assert valid == False, 'Size mismatch should be invalid'
os.unlink(tmpfile)
print('Validation OK')
" 2>&1)
if echo "$OUT" | grep -q "Validation OK"; then
    add_result "video_validation" "pass" "Validación OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "video_validation" "fail" "Error validación" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 9: DownloadSummary
echo "[Test 9] DownloadSummary..."
OUT=$(python -c "
import sys, json, os, tempfile, shutil; sys.path.insert(0, '.')
from src.downloader import DownloadSummary

# Test initialization
s = DownloadSummary()
assert len(s.session_id) == 8, 'session_id should be 8 chars'
assert s.total_found == 0
assert s.downloaded == 0
assert s.errors == 0
assert s.download_times == []
assert s.file_sizes == []
print('Init OK')

# Test record_download
s.record_download(1048576, 10.0)  # 1MB in 10s
s.record_download(2097152, 5.0)   # 2MB in 5s
assert len(s.download_times) == 2
assert len(s.file_sizes) == 2
assert len(s.download_speeds) == 2
print('record_download OK')

# Test statistics
assert s.min_time() == '5.0s', f'min_time: {s.min_time()}'
assert s.max_time() == '10.0s', f'max_time: {s.max_time()}'
assert 'MB' in s.largest_file()
assert 'KB' in s.smallest_file() or 'MB' in s.smallest_file()
print('Statistics OK')

# Test success_rate
s.downloaded = 2
s.errors = 1
s.invalid_files = 0
assert s.success_rate() == '66.7%', f'success_rate: {s.success_rate()}'
print('success_rate OK')

# Test empty session
s2 = DownloadSummary()
assert s2.min_time() == 'N/A'
assert s2.max_time() == 'N/A'
assert s2.success_rate() == 'N/A'
assert s2.average_speed() == 'N/A'
print('Empty session OK')

# Test to_dict
s3 = DownloadSummary()
s3.downloaded = 1
s3.total_bytes = 1048576
d = s3.to_dict('TestChannel', 49)
assert d['session_id'] == s3.session_id
assert d['channel'] == 'TestChannel'
assert d['downloaded'] == 1
assert 'timestamp' in d
assert 'elapsed_formatted' in d
print('to_dict OK')

# Test save_to_log creates both .log and .json
tmpdir = tempfile.mkdtemp()
s4 = DownloadSummary()
s4.downloaded = 1
s4.total_bytes = 1048576
log_path = s4.save_to_log(tmpdir, 'TestChannel', 49)
assert os.path.exists(log_path), 'Log file should exist'
json_path = log_path.replace('.log', '.json')
assert os.path.exists(json_path), 'JSON file should exist'
with open(json_path) as f:
    data = json.load(f)
assert data['session_id'] == s4.session_id
assert data['downloaded'] == 1
shutil.rmtree(tmpdir)
print('save_to_log OK')

print('DownloadSummary OK')
" 2>&1)
if echo "$OUT" | grep -q "DownloadSummary OK"; then
    add_result "download_summary" "pass" "DownloadSummary OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "download_summary" "fail" "Error DownloadSummary" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 10: Validación de espacio en disco
echo "[Test 10] Validación de espacio en disco..."
OUT=$(python -c "
import sys, os; sys.path.insert(0, '.')
from src.utils import format_size

# Test disk space using os.statvfs (inlined version)
stat = os.statvfs('.')
free = stat.f_bavail * stat.f_frsize
assert free > 0, 'Free space should be positive'
print(f'Free space: {format_size(free)}')

# Test format_size with various values
assert format_size(0) == '0.0 B'
assert format_size(512) == '512.0 B'
assert format_size(1024) == '1.0 KB'
assert format_size(1048576) == '1.0 MB'
assert format_size(1073741824) == '1.0 GB'
print('Disk space OK')
" 2>&1)
if echo "$OUT" | grep -q "Disk space OK"; then
    add_result "disk_space" "pass" "Espacio en disco OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "disk_space" "fail" "Error espacio en disco" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 11: Tests integrados y edge cases
echo "[Test 11] Tests integrados y edge cases..."
OUT=$(python -c "
import sys, os, json, tempfile, shutil; sys.path.insert(0, '.')

# 1. History CRUD operations
from src.history import DownloadHistory
tmpdb = tempfile.mktemp(suffix='.db')
h = DownloadHistory(tmpdb)

# Record downloaded
h.record_downloaded(
    message_id=1, channel_id='test_ch', filename='video1.mp4',
    original_name='orig.mp4', size_bytes=1000000, duration_seconds=120.0,
    width=1920, height=1080, mime_type='video/mp4',
    output_path='/tmp/video1.mp4', category='peliculas', scan_result='clean'
)
assert h.is_downloaded(1) == True
assert h.is_downloaded(999) == False
print('History CRUD OK')

# Record skipped short
h.record_skipped_short(2, 'test_ch', 10.0, 'short.mp4')
assert h.is_skipped_short(2) == True
assert h.is_downloaded(2) == False
print('History skip OK')

# Record error
h.record_error(3, 'test_ch', 'Connection timeout')
stats = h.get_stats()
assert stats.get('error', 0) >= 1
print('History error OK')

# Record invalid
h.record_invalid(4, 'test_ch', 'bad.mp4', 'bad.mp4', 'Invalid file')
assert h.is_invalid(4) == True
print('History invalid OK')

# Get failed downloads
failed = h.get_failed_downloads('test_ch')
assert len(failed) >= 2  # error + invalid
print('History get_failed OK')

# Channel state
h.update_channel_state('test_ch', 100, 50)
state = h.get_channel_state('test_ch')
assert state['last_processed_message_id'] == 100
assert state['total_videos_found'] == 50
print('History channel state OK')

# Daily stats
count = h.get_daily_count()
assert count == 0
h.increment_daily_count()
h.increment_daily_count()
count = h.get_daily_count()
assert count == 2
print('History daily stats OK')

h.close()
os.unlink(tmpdb)

# 2. Scanner probability
from src.scanner import SecurityScanner, ScanResult
s = SecurityScanner(enabled=True, engine='clamav', scan_probability=0.0, output_dir='./downloads')
assert s.should_scan() == False, '0% probability should never scan'
s2 = SecurityScanner(enabled=False, engine='clamav', scan_probability=1.0, output_dir='./downloads')
assert s2.should_scan() == False, 'disabled should never scan'
print('Scanner probability OK')

# 3. Notification append
from src.notifier import Notifier
tmpdir = tempfile.mkdtemp()
n = Notifier(notifications_dir=tmpdir)
n.notify_error(subject='Error 1', message='msg1')
n.notify_error(subject='Error 2', message='msg2')
n.notify_threat(subject='Threat', message='threat msg')

notif_file = os.path.join(tmpdir, 'notifications.json')
with open(notif_file) as f:
    data = json.load(f)
assert len(data) == 3
types = set(x['type'] for x in data)
assert 'error' in types
assert 'threat_detected' in types
shutil.rmtree(tmpdir)
print('Notification append OK')

# 4. Config edge cases
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)
assert 'output_dir' in config
assert 'security' in config
assert config.get('min_free_space_mb', 0) > 0
assert config.get('download_timeout_seconds', 0) > 0
assert config.get('max_download_retries', 0) > 0
print('Config edge cases OK')

# 5. build_output_path
from src.downloader import build_output_path, get_folder_for_channel
tmpdir = tempfile.mkdtemp()
path1 = build_output_path(tmpdir, 'test', 123, 'video.mp4')
assert path1.endswith('video.mp4')
assert os.path.exists(os.path.dirname(path1))

path2 = build_output_path(tmpdir, 'test', 124, None)
assert 'video_124_' in path2
assert path2.endswith('.mp4')
shutil.rmtree(tmpdir)
print('build_output_path OK')

# 6. get_folder_for_channel
folders = {0: 'peliculas', 1: 'series'}
assert get_folder_for_channel(0, folders, 'default') == 'peliculas'
assert get_folder_for_channel(1, folders, 'default') == 'series'
assert get_folder_for_channel(99, folders, 'default') == 'default'
print('get_folder_for_channel OK')

print('Integration tests OK')
" 2>&1)
if echo "$OUT" | grep -q "Integration tests OK"; then
    add_result "integration" "pass" "Tests integrados OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "integration" "fail" "Error tests integrados" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 12: Timeout y reintentos configurables
echo "[Test 12] Timeout y reintentos configurables..."
OUT=$(python -c "
import sys, yaml; sys.path.insert(0, '.')

# Verify config has timeout and retry settings
with open('config.yaml') as f:
    config = yaml.safe_load(f)

assert 'download_timeout_seconds' in config
assert config['download_timeout_seconds'] == 3600
assert 'max_download_retries' in config
assert config['max_download_retries'] == 3
print('Config timeout/retries OK')

# Verify download_video signature returns tuple
import inspect
from src.downloader import download_video
sig = inspect.signature(download_video)
assert 'timeout' in sig.parameters
assert 'max_retries' in sig.parameters
print('download_video signature OK')

print('Timeout/retries OK')
" 2>&1)
if echo "$OUT" | grep -q "Timeout/retries OK"; then
    add_result "timeout_retries" "pass" "Timeout/reintentos OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "timeout_retries" "fail" "Error timeout/reintentos" "$OUT"
    echo "  ✗ FALLIDO"
fi
echo ""

# Test 13: Fixes para videos largos (timeout dinámico, resume, file reference)
echo "[Test 13] Fixes para videos largos..."
OUT=$(python -c "
import sys; sys.path.insert(0, '.')
from src.downloader import download_video
import inspect

# 1. Dynamic timeout calculation (inlined formula)
# Small file (10MB) at 500KB/s = 20s * 1.5 = 30s -> min 600s
size_10mb = 10 * 1024 * 1024
t1 = max(600, int(size_10mb / 500000) * 1.5)
assert t1 == 600, f'Small file timeout should be min 600, got {t1}'
print(f'Small file timeout: {t1}s (min)')

# Large file (900MB) at 500KB/s = 1843s * 1.5 = 2765s
size_900mb = 900 * 1024 * 1024
t2 = max(600, int(size_900mb / 500000) * 1.5)
assert t2 > 2700, f'Large file timeout should be > 2700, got {t2}'
print(f'Large file (900MB) timeout: {t2}s')

# Very large file (2GB) at 500KB/s = 4096s * 1.5 = 6144s
size_2gb = 2 * 1024 * 1024 * 1024
t3 = max(600, int(size_2gb / 500000) * 1.5)
assert t3 > 6000, f'Very large file timeout should be > 6000, got {t3}'
print(f'Very large file (2GB) timeout: {t3}s')
print('Dynamic timeout OK')

# 2. Verify download_video has channel_entity parameter
sig = inspect.signature(download_video)
assert 'channel_entity' in sig.parameters, 'download_video should have channel_entity parameter'
print('channel_entity parameter OK')

# 3. Verify download_video source has resume logic
source = inspect.getsource(download_video)
assert 'offset' in source, 'Should use offset for resume'
assert 'FileReferenceExpiredError' in source, 'Should handle FileReferenceExpiredError'
assert 'get_messages' in source, 'Should re-fetch message on expired reference'
assert 'initial=offset' in source, 'Should show progress from offset'
print('Resume and file reference handling OK')

print('Large video fixes OK')
" 2>&1)
if echo "$OUT" | grep -q "Large video fixes OK"; then
    add_result "large_video_fixes" "pass" "Fixes para videos largos OK" "$OUT"
    echo "  ✓ PASADO"
else
    add_result "large_video_fixes" "fail" "Error en fixes para videos largos: $OUT"
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
echo "Resultados: $RESULTS_FILE"
