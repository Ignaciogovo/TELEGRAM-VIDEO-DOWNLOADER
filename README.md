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
max_downloads_per_run: 50    # límite por ejecución del script
channel_folders:              # índice 0 = primer canal en TELEGRAM_CHANNELS
  0: "peliculas"
default_folder: "uncategorized"
security:
  enabled: true
  engine: "clamav"            # o "virustotal"
  scan_probability: 0.1       # 10% se escanean
```

## Uso

### 1. Setup inicial (primera vez)

1. Crear entorno virtual e instalar dependencias:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Crear archivo de configuración:
   ```bash
   cp .env.example .env
   ```

3. Editar `.env` con tus credenciales:
   ```env
   TELEGRAM_API_ID=tu_id
   TELEGRAM_API_HASH=tu_hash
   TELEGRAM_CHANNELS=-1002523901612
   ```

4. (Opcional) Editar `config.yaml` para ajustar filtros y carpetas.

5. **Primera ejecución**: el script pedirá teléfono + código de verificación.

### 2. Ejecución manual

Activar el entorno antes de cada sesión:
```bash
source venv/bin/activate
```

| Acción | Comando |
|--------|---------|
| Simular sin descargar (dry-run) | `python src/main.py --all --dry-run` |
| Descargar todos los vídeos nuevos | `python src/main.py --all` |
| Descargar el más reciente | `python src/main.py` |
| Descargar uno específico | `python src/main.py --message-id 123` |
| Solo un canal (de varios en .env) | `python src/main.py --all --channel -1002523901612` |
| Ver estadísticas del historial | `python src/main.py --stats` |

### 3. Tests

| Test | Comando |
|------|---------|
| Unit tests | `bash test.sh` |
| Test de integración (descarga real) | `bash test_real_download.sh` |

### 4. Herramientas auxiliares

| Herramienta | Comando |
|-------------|---------|
| Listar canales disponibles | `python src/list_chats.py` |
| Ver últimos 20 vídeos sin descargar | `python src/extract_metadata.py 20` |
| Generar notificaciones de prueba | `python src/test_notifications.py` |

## Docker

### Build

**Single-arch (más rápido):**
```bash
docker build -t telegram-downloader .
```

**Multi-arch (linux/amd64, linux/arm64):**
```bash
docker buildx create --use  # Solo la primera vez
docker buildx build --platform linux/amd64,linux/arm64 -t telegram-downloader .
```

### Primera ejecución (autenticación interactiva)

```bash
mkdir -p downloads session_data

docker run --rm -it --env-file .env \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/session_data:/app/session_data \
  telegram-downloader
```

Introduce el código de Telegram cuando se pida. La sesión se guarda en `session_data/telegram_downloader.session`.

### Ejecuciones siguientes (cron, sin -it)

```bash
docker run --rm --env-file .env \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/session_data:/app/session_data \
  telegram-downloader
```

### Variables de entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DOWNLOAD_LIMIT` | Sobrescribe `max_downloads_per_run` | - |
| `TELEGRAM_API_ID` | Telegram API ID (en .env) | requerido |
| `TELEGRAM_API_HASH` | Telegram API hash (en .env) | requerido |
| `TELEGRAM_CHANNELS` | Canales a descargar (en .env) | requerido |
| `NOTIFICATION_EMAIL` | Email destino notificaciones | admin@example.com |
| `VT_API_KEY` | API key de VirusTotal | vacío |

### Volúmenes

| Path contenedor | Propósito |
|------------------|-----------|
| `/app/downloads` | Vídeos descargados (persistente) |
| `/app/session_data` | Sesión Telegram (persistente) |

### Cron ejemplo (diario a las 2:00 AM)

```bash
0 2 * * * cd /path/to/project && docker run --rm --env-file .env \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/session_data:/app/session_data \
  telegram-downloader >> /var/log/telegram-downloader.log 2>&1
```

### Notas

- El contenedor ejecuta como usuario no-root (`appuser` UID/GID 1000)
- `tini` se usa como PID 1 para manejo correcto de señales
- `freshclam` actualiza firmas de ClamAV durante el build (no requiere red en runtime)

## Seguridad

Cada vídeo tiene un 10% de probabilidad de ser escaneado por ClamAV o VirusTotal. Si se detecta amenaza, se mueve a `downloads/quarantine/`.
