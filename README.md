# Telegram Video Downloader

## Visión general

Script en Python que descarga TODOS los vídeos de uno o varios canales de Telegram. Escanea el canal completo, compara con el historial de descargas y descarga automáticamente los que falten.

## Estado actual

**Fase 2 de 3** — Descarga masiva con filtros, seguridad y notificaciones.

- [x] Conexión autenticada a Telegram con Telethon
- [x] Descarga de un único vídeo (el más reciente o por message_id)
- [x] Progreso en terminal
- [x] Guardado en directorio configurable
- [x] Descarga masiva con filtro por duración (> 5 min)
- [x] Historial de descargas en SQLite (resume desde checkpoint)
- [x] Escaneo de seguridad aleatorio (ClamAV / VirusTotal)
- [x] Mapeo de canales a carpetas (por índice en TELEGRAM_CHANNELS)
- [x] Límite diario de descargas configurable
- [x] Delay entre descargas configurable
- [x] Dry-run mode
- [x] Verificación completa desde el principio
- [x] Notificaciones JSON para servicio externo
- [x] Logs con rotación (30 días)
- [ ] Daemon + cron (Fase 3)

## Requisitos

- Python 3.11+
- pip
- ClamAV (opcional, para escaneo): `sudo apt install clamav`

## Instalación

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

### 1. Variables de entorno

```bash
cp .env.example .env
```

Edita `.env`:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=tu_api_hash_aqui
TELEGRAM_CHANNELS=-1002523901612,-1001234567890
VT_API_KEY=  # Opcional, solo si usas VirusTotal
```

> **Importante:** `.env` contiene datos sensibles y está en `.gitignore`.

### 2. Configuración general

Edita `config.yaml`:

```yaml
session_name: "telegram_downloader"
output_dir: "./downloads"
log_level: "INFO"

# Mapeo de canales a carpetas (por índice en TELEGRAM_CHANNELS)
# Índice 0 = primer canal, 1 = segundo, etc.
channel_folders:
  0: "peliculas"
  1: "series"
default_folder: "uncategorized"

# Filtros
min_duration_seconds: 300       # solo vídeos > 5 min
download_delay_seconds: 30      # espera entre descargas
max_daily_downloads: 50         # máximo por día

# Escaneo de seguridad
security:
  enabled: true
  engine: "clamav"              # o "virustotal"
  scan_probability: 0.1         # 10% se escanean
```

> **Nota:** Los canales se definen en `.env` (`TELEGRAM_CHANNELS`). El índice en `channel_folders` corresponde al orden en esa lista.

### 3. Autenticación

La primera vez que ejecutes cualquier comando, Telethon pedirá:
1. Tu número de teléfono (+34600123456)
2. Código de verificación
3. Contraseña 2FA (si aplica)

La sesión se guarda en `telegram_downloader.session`.

### Herramientas útiles

**Encontrar el ID de un canal:**
```bash
python src/list_chats.py
```

**Ver metadatos de vídeos sin descargar:**
```bash
# Últimos 20 vídeos del primer canal
python src/extract_metadata.py

# Últimos 50 vídeos
python src/extract_metadata.py 50

# Canal específico
python src/extract_metadata.py 20 -1001234567890
```

## Uso

### Fase 1: Descargar un único vídeo

```bash
# Último vídeo del primer canal
python src/main.py

# Vídeo específico
python src/main.py --message-id 123

# Canal específico
python src/main.py --channel -1001234567890 --message-id 123
```

### Fase 2: Descarga masiva

```bash
# Descargar vídeos nuevos (resume desde checkpoint)
python src/main.py --all

# Simular sin descargar
python src/main.py --all --dry-run

# Canal específico
python src/main.py --all --channel -1001234567890

# Verificación completa desde el principio
python src/verify_all.py

# Verificación completa dry-run
python src/verify_all.py --dry-run

# Estadísticas
python src/main.py --stats
```

## Estructura del proyecto

```
telegram-video-downloader/
├── .env.example         # Plantilla de variables de entorno
├── .env                 # Tus credenciales (NO commitear)
├── .gitignore
├── agents.md            # Configuración opencode
├── config.yaml          # Configuración general
├── requirements.txt
├── README.md
└── src/
    ├── __init__.py
    ├── main.py          # Entry point (Fase 1 + Fase 2)
    ├── verify_all.py    # Verificación completa desde el principio
    ├── list_chats.py    # Listar chats/canales
    ├── extract_metadata.py  # Extraer metadatos sin descargar
    ├── downloader.py    # Lógica de descarga masiva
    ├── history.py       # SQLite: historial + checkpoint
    ├── scanner.py       # Escaneo seguridad (ClamAV/VT)
    ├── notifier.py      # Notificaciones JSON
    ├── logger.py        # Logging con rotación
    └── test_notifications.py  # Generar notificaciones de prueba
```

## Estructura de descargas

```
downloads/
├── peliculas/           # Canal 1 + Canal 2
│   ├── DEADPOOL (2016).mp4
│   └── ...
├── series/              # Canal 3
│   └── ...
├── uncategorized/       # Canales sin mapeo
├── quarantine/          # Ficheros detectados como amenaza
├── history.db           # SQLite con historial
└── logs/                # Resúmenes de cada sesión
    └── summary_20260618_230000.log
```

## Escaneo de seguridad

Cada vídeo descargado tiene una probabilidad configurable (10% por defecto) de ser escaneado:

- **ClamAV** (default): Escaneo local offline. Instala con `sudo apt install clamav`.
- **VirusTotal**: Escaneo cloud multi-engine. Requiere `VT_API_KEY` en `.env`.

Si se detecta una amenaza, el fichero se mueve a `downloads/quarantine/`.

## Notificaciones

El sistema genera notificaciones JSON en `downloads/notifications/notifications.json` para:
- Errores de descarga
- Amenazas detectadas por el escáner

Para generar notificaciones de prueba:
```bash
python src/test_notifications.py
```
