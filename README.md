# Telegram Video Downloader

Descarga todos los vídeos de uno o varios canales de Telegram. Compara con el historial y descarga automáticamente los que falten.

## Estado

**Fase 2 completada** — Descarga masiva con filtros, historial SQLite, escaneo de seguridad (ClamAV/VirusTotal), notificaciones JSON y logs rotativos.

## Instalación

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Configuración

### `.env`
```env
TELEGRAM_API_ID=tu_id
TELEGRAM_API_HASH=tu_hash
TELEGRAM_CHANNELS=-1002523901612
```

### `config.yaml`
```yaml
output_dir: "./downloads"
min_duration_seconds: 300     # solo vídeos > 5 min
max_daily_downloads: 50       # límite diario
channel_folders:              # índice 0 = primer canal en TELEGRAM_CHANNELS
  0: "peliculas"
default_folder: "uncategorized"
security:
  enabled: true
  engine: "clamav"            # o "virustotal"
  scan_probability: 0.1       # 10% se escanean
```

## Uso

La primera vez pedirá teléfono + código de verificación.

```bash
# Un vídeo (el más reciente)
python src/main.py

# Un vídeo específico
python src/main.py --message-id 123

# Todos los nuevos (resume desde checkpoint)
python src/main.py --all

# Simular sin descargar
python src/main.py --all --dry-run

# Verificación completa desde el principio
python src/verify_all.py

# Estadísticas
python src/main.py --stats
```

### Herramientas
```bash
python src/list_chats.py              # Encontrar IDs de canales
python src/extract_metadata.py 20     # Ver últimos 20 vídeos sin descargar
python src/test_notifications.py      # Generar notificaciones de prueba
```

## Seguridad

Cada vídeo tiene un 10% de probabilidad de ser escaneado por ClamAV o VirusTotal. Si se detecta amenaza, se mueve a `downloads/quarantine/`.
