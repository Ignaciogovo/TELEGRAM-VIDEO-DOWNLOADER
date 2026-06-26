# Telegram Video Downloader

Descarga automática de vídeos de uno o varios canales de Telegram. Compara con un historial SQLite, escanea contra virus con ClamAV/VirusTotal y notifica fallos vía JSON. Pensado para ejecutarse desatendido en cron dentro de un contenedor Docker.

## Estado

Fases 1-4 completadas. Funcionalidad actual: descarga masiva con filtros, historial persistente, escaneo de seguridad, notificaciones JSON, logs rotativos, búsqueda de chats y wrapper de cron con detección de contenedores atascados.

## Requisitos previos

Antes de empezar necesitas:

1. **Una cuenta de Telegram** (tu cuenta personal).
2. **API credentials** — obtén `TELEGRAM_API_ID` y `TELEGRAM_API_HASH` en [my.telegram.org/apps](https://my.telegram.org/apps).
3. **Docker** (recomendado) **o Python 3.12+** con `pip`.

## Instalación

### Opción A — Docker (recomendado)

```bash
git clone <repo> telegram-video-downloader
cd telegram-video-downloader

mkdir -p downloads session_data  # o la ruta que definas en DOWNLOADS_DIR
cp .env.example .env
nano .env   # editar con tus credenciales

docker build -t telegram-downloader .
```

### Opción B — Local con venv

```bash
git clone <repo> telegram-video-downloader
cd telegram-video-downloader

python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env
```

## Configuración

### `.env` — credenciales y canales

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=tu_api_hash_aqui
TELEGRAM_CHANNELS=mi_canal,-1001234567890,@otro
NOTIFICATION_EMAIL=tu@email.com
VT_API_KEY=
DOWNLOADS_DIR=./downloads          # ruta del host para vídeos y logs (crearla antes de ejecutar)
```

`TELEGRAM_CHANNELS` admite:
- **Usernames públicos**: `durov`
- **IDs numéricos de canales privados**: `-1001234567890` (prefijo `-100` obligatorio)
- **Mezcla** separada por comas

### `config.yaml` — comportamiento

> **Nota:** `output_dir` dentro del contenedor es siempre `/app/downloads`. La ruta del **host** se configura via `DOWNLOADS_DIR` en `.env` (o como variable de entorno del wrapper). No es necesario cambiarla aquí.

```yaml
output_dir: "/app/downloads"
log_level: "INFO"
session_name: "session_data/telegram_downloader"

channel_folders:
  0: "peliculas"        # índice 0 = primer canal en TELEGRAM_CHANNELS
default_folder: "uncategorized"

min_duration_seconds: 300       # solo vídeos > 5 min
download_delay_seconds: 30      # pausa entre descargas
max_downloads_per_run: 50       # límite por ejecución
download_timeout_seconds: 3600  # 1 hora
min_free_space_mb: 500          # parar si queda poco espacio

security:
  enabled: true
  engine: "clamav"              # o "virustotal"
  scan_probability: 0.1         # 10% de los vídeos se escanean
```

## Primera ejecución (autenticación)

La primera vez Telegram te pedirá teléfono + código. Esta sesión se guarda en `session_data/` y no se vuelve a pedir.

**Docker:**
```bash
docker run --rm -it --env-file .env \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/session_data:/app/session_data \
  telegram-downloader
```

**Local:**
```bash
source venv/bin/activate
python src/main.py
```

Introduce tu número en formato internacional (`+34612345678`) y el código que te envíe Telegram.

## Uso

### Comandos principales

> **Nota:** `-v ${DOWNLOADS_DIR:-$(pwd)/downloads}:/app/downloads` usa la variable `DOWNLOADS_DIR` del `.env` o el default. Cambia `DOWNLOADS_DIR` para almacenar los vídeos en otra ubicación.

| Acción | Docker | Local |
|--------|--------|-------|
| Descargar todos los nuevos | `docker run --rm --env-file .env -v ${DOWNLOADS_DIR:-$(pwd)/downloads}:/app/downloads -v $(pwd)/session_data:/app/session_data telegram-downloader --all` | `python src/main.py --all` |
| Simular sin descargar (dry-run) | añade `--dry-run` | añade `--dry-run` |
| Descargar el más reciente | igual sin `--all` | `python src/main.py` |
| Descargar uno específico (msg id) | añade `--message-id 123` | `python src/main.py --message-id 123` |
| Solo un canal (varios en `.env`) | añade `--channel mi_canal` | `python src/main.py --all --channel mi_canal` |
| Ver estadísticas del historial | añade `--stats` | `python src/main.py --stats` |

### Listar y buscar chats

```bash
# Listar todos los chats/canales de la cuenta
docker run --rm --env-file .env \
  -v $(pwd)/session_data:/app/session_data \
  telegram-downloader --list-chats
```

# Buscar el ID de un chat por nombre (devuelve solo el ID)
docker run --rm --env-file .env \
  -v $(pwd)/session_data:/app/session_data \
  telegram-downloader --find-chat peliculas
```

Tras obtener un ID numérico, actualiza `TELEGRAM_CHANNELS` en `.env`:
```env
TELEGRAM_CHANNELS=-1001234567890,-100987654321
```

### Limitar descargas por ejecución

Sobrescribe `max_downloads_per_run` con la variable de entorno `DOWNLOAD_LIMIT`:

```bash
# Docker
docker run --rm -e DOWNLOAD_LIMIT=5 --env-file .env \
  -v ${DOWNLOADS_DIR:-$(pwd)/downloads}:/app/downloads \
  -v $(pwd)/session_data:/app/session_data \
  telegram-downloader --all

# Local
DOWNLOAD_LIMIT=5 python src/main.py --all
```

### Ejecución desatendida (cron)

El proyecto incluye `scripts/cron-wrapper.sh` que lanza el contenedor si no está corriendo y, si lleva más de `MAX_CONTAINER_HOURS` activo, lo detiene, notifica y relanza.

```bash
chmod +x scripts/cron-wrapper.sh
```

Variables del wrapper:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DOWNLOADS_DIR` | `$(pwd)/downloads` | Ruta del host para vídeos, logs y notificaciones |
| `MAX_CONTAINER_HOURS` | `12` | Horas antes de generar notificación de "stale container" |
| `CONTAINER_NAME` | `telegram-downloader` | Nombre del contenedor |
| `IMAGE_NAME` | `telegram-downloader` | Imagen Docker a lanzar |

> **Importante:** `DOWNLOADS_DIR` debe crearse antes de la primera ejecución (`mkdir -p /ruta/que/quieras`). El wrapper no la crea automáticamente.

**Instalar en crontab:**

```bash
crontab -e
# Añadir una de estas líneas (elegir según la ubicación deseada):

# Cada hora — ubicación por defecto
0 * * * * cd /workspace/telegram-video-downloader && ./scripts/cron-wrapper.sh >> /var/log/telegram-cron.log 2>&1

# Cada hora — ubicación personalizada (NAS, SSD, etc.)
0 * * * * cd /workspace/telegram-video-downloader && DOWNLOADS_DIR=/mnt/nas/telegram-descargas ./scripts/cron-wrapper.sh >> /var/log/telegram-cron.log 2>&1
```

## Casos de uso

### 1. Backup personal de canales
Mantén una copia local de todos los vídeos de canales donde guardas contenido (películas, documentales, cursos, etc.). El historial SQLite evita re-descargar lo que ya tienes, así que las ejecuciones diarias son rápidas.

### 2. Automatización con cron
Programa descargas diarias a las 2 AM. Cada ejecución solo procesa vídeos nuevos; el resto ya están en el historial. El wrapper de cron detecta contenedores atascados y te avisa.

### 3. Descarga selectiva
Usa `min_duration_seconds` para descartar clips cortos, y `channel_folders` para organizar cada canal en su propia carpeta. Ideal para evitar ruido en canales que mezclan cortos y largos.

### 4. Multi-canal con carpetas
Configura varios canales en `TELEGRAM_CHANNELS` y asigna carpetas distintas en `config.yaml`:
```yaml
channel_folders:
  0: "peliculas"      # primer canal -> downloads/peliculas/
  1: "series"         # segundo canal -> downloads/series/
  2: "documentales"   # tercer canal -> downloads/documentales/
```

### 5. Monitorización de salud
`scripts/cron-wrapper.sh` genera una entrada en `downloads/notifications/notifications.json` si el contenedor lleva más de 12h activo. Integra ese JSON con cualquier servicio de notificaciones externo (email, Telegram bot, webhook, etc.).

### 6. Escaneo de seguridad
El 10% de los vídeos descargados se escanean con ClamAV (incluido en la imagen Docker). Si se detecta amenaza, el fichero se mueve a `downloads/quarantine/` y se genera una notificación `type: "threat_detected"`.

## Docker

### Build

```bash
# Single-arch (rápido)
docker build -t telegram-downloader .

# Multi-arch (linux/amd64, linux/arm64)
docker buildx create --use   # solo la primera vez
docker buildx build --platform linux/amd64,linux/arm64 -t telegram-downloader .
```

### Variables de entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `TELEGRAM_API_ID` | API ID de Telegram | requerido |
| `TELEGRAM_API_HASH` | API hash de Telegram | requerido |
| `TELEGRAM_CHANNELS` | Canales a descargar | requerido |
| `NOTIFICATION_EMAIL` | Email destino notificaciones | `admin@example.com` |
| `DOWNLOAD_LIMIT` | Sobrescribe `max_downloads_per_run` | sin límite |
| `VT_API_KEY` | API key de VirusTotal (si `engine: virustotal`) | vacío |
| `LOG_LEVEL` | Nivel de log (DEBUG/INFO/WARNING/ERROR) | `INFO` |

### Volúmenes

| Path host | Path contenedor | Propósito |
|-----------|-----------------|-----------|
| `./downloads` | `/app/downloads` | Vídeos descargados (persistente) |
| `./session_data` | `/app/session_data` | Sesión Telegram (persistente) |

### Notas técnicas

- El contenedor ejecuta como usuario no-root (`appuser` UID/GID 1000)
- `tini` se usa como PID 1 para manejo correcto de señales
- `freshclam` actualiza firmas de ClamAV durante el build (no requiere red en runtime)
- ClamAV está preinstalado en la imagen; no requiere configuración adicional

## Estructura de directorios

```
telegram-video-downloader/
├── src/                    # código fuente
│   ├── main.py             # entry point
│   ├── downloader.py       # lógica de descarga bulk
│   ├── scanner.py          # escaneo de seguridad
│   ├── notifier.py         # generación de notificaciones JSON
│   ├── history.py          # historial SQLite
│   ├── list_chats.py       # utilidad listar/buscar chats
│   └── ...
├── downloads/              # volumen (vídeos + logs + notificaciones)
│   ├── peliculas/          # vídeos del canal índice 0
│   ├── logs/               # logs rotativos
│   ├── notifications/      # JSON de notificaciones
│   └── history.db          # historial SQLite
├── session_data/           # volumen (sesión Telegram)
├── scripts/
│   └── cron-wrapper.sh     # wrapper para cron
├── config.yaml             # configuración del comportamiento
├── .env                    # credenciales (NO commitear)
├── Dockerfile              # imagen Docker
```

## Seguridad

- El 10% de los vídeos se escanean con ClamAV (o VirusTotal si `engine: "virustotal"`)
- Las amenazas detectadas se mueven a `downloads/quarantine/` y se notifican vía `notifications.json`
- El contenedor Docker ejecuta como usuario no-root
- La sesión de Telegram se almacena en un volumen persistente (no dentro de la imagen)
- No subas `.env` a git — está en `.gitignore`

## FAQ

### ¿Cómo obtengo `TELEGRAM_API_ID` y `TELEGRAM_API_HASH`?
Ve a [my.telegram.org/apps](https://my.telegram.org/apps), inicia sesión con tu número, crea una app y copia los valores. Son públicos (no son secretos como un token de bot).

### ¿Cómo encuentro el ID de un canal privado?
Ejecuta `telegram-downloader --list-chats` y busca el nombre del canal. Los IDs privados empiezan por `-100` (ej. `-1001234567890`).

### ¿Puedo ejecutarlo sin Docker?
Sí. Usa `python src/main.py --all` con el venv activado. La única diferencia es que ClamAV no estará preinstalado; necesitas instalarlo manualmente (`apt install clamav`) o cambiar `engine: "virustotal"` en `config.yaml`.

### ¿Es seguro descargar vídeos de canales arbitrarios?
Riesgo bajo. Cada vídeo se escanea con probabilidad 10% por ClamAV antes de quedar disponible. Las amenazas se mueven a `quarantine/`. No es una garantía absoluta — un 0% de malware se te puede colar — pero reduce drásticamente la superficie.

### El contenedor se queda colgado / tarda mucho
Por defecto `download_timeout_seconds: 3600` (1 hora por vídeo). Si un vídeo está atascado, el script lo salta tras N reintentos (`max_download_retries: 3`). `scripts/cron-wrapper.sh` detecta contenedores que llevan más de 12h activos y genera una notificación.

### ¿Cómo actualizo la imagen?
```bash
docker build --pull -t telegram-downloader .
# O con multi-arch:
docker buildx build --pull --platform linux/amd64,linux/arm64 -t telegram-downloader .
```

### ¿Cómo paro un cron que ya está corriendo?
```bash
docker ps | grep telegram-downloader
docker stop <container_id>
```

### ¿Y si pierdo la sesión?
Borra `session_data/telegram_downloader.session` y vuelve a ejecutar con `-it` para re-autenticarte. El historial de descargas (`downloads/history.db`) se mantiene intacto.

## Licencia

MIT.
