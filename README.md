# Telegram Video Downloader

## Visión general

Demonio (daemon) que se ejecuta en un contenedor Docker de forma continua. Su misión: descargar TODOS los vídeos de un canal de Telegram y cada día verificar cuáles faltan para descargarlos automáticamente.

## Estado actual

**Fase 3 de 3** — Daemon + Docker completo.

- [x] Conexión autenticada a Telegram con Telethon
- [x] Descarga de un único vídeo (el más reciente o por message_id)
- [x] Progreso en terminal
- [x] Guardado en directorio configurable
- [x] Descarga masiva con filtro por duración (> 5 min)
- [x] Historial de descargas en SQLite (resume desde checkpoint)
- [x] Escaneo de seguridad aleatorio (ClamAV / VirusTotal)
- [x] Mapeo de canales a carpetas
- [x] Límite diario de descargas configurable
- [x] Delay entre descargas configurable
- [x] Dry-run mode
- [x] Verificación completa desde el principio
- [x] Daemon completo + contenedor Docker
- [x] Notificaciones JSON para servicio externo
- [x] Logs con rotación (30 días)
- [x] Script de pruebas automático

## Requisitos previos

### Obtener credenciales de Telegram API

1. Ve a [https://my.telegram.org/apps](https://my.telegram.org/apps)
2. Inicia sesión con tu número de teléfono
3. Ve a **API development tools**
4. Crea una nueva aplicación
5. Copia el **App api_id** y **App api_hash**

### Requisitos del sistema

- Python 3.11+
- pip
- ClamAV (opcional, para escaneo de seguridad): `sudo apt install clamav`

## Instalación

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

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

# Mapeo de canales a carpetas
channel_folders:
  "-1002523901612": "peliculas"
  "-1001234567890": "peliculas"
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

### Encontrar el ID de un canal privado

```bash
python src/list_chats.py
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

### Primera ejecución

La primera vez, Telethon pedirá:
1. Tu número de teléfono (+34600123456)
2. Código de verificación
3. Contraseña 2FA (si aplica)

La sesión se guarda en `.session`.

## Estructura del proyecto

```
telegram-video-downloader/
├── .env.example         # Plantilla de variables de entorno
├── .env                 # Tus credenciales (NO commitear)
├── .gitignore
├── agents.md            # Git workflow + seguridad
├── config.yaml          # Configuración general
├── requirements.txt
├── README.md
├── TESTING.md           # Instrucciones de pruebas
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── entrypoint.sh
│   ├── run.sh
│   ├── test.sh
│   ├── test_notifications.py
│   └── test_results.json
└── src/
    ├── __init__.py
    ├── main.py          # Entry point (Fase 1 + Fase 2)
    ├── verify_all.py    # Verificación completa desde el principio
    ├── list_chats.py    # Listar chats/canales
    ├── downloader.py    # Lógica de descarga masiva
    ├── history.py       # SQLite: historial + checkpoint
    ├── scanner.py       # Escaneo seguridad (ClamAV/VT)
    ├── notifier.py      # Notificaciones JSON
    ├── logger.py        # Logging con rotación
    └── extract_metadata.py  # Extraer metadatos sin descargar
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

- **ClamAV** (default): Escaneo local offline. Incluido en la imagen Docker.
- **VirusTotal**: Escaneo cloud multi-engine. Requiere `VT_API_KEY` en `.env`

Si se detecta una amenaza, el fichero se mueve a `downloads/quarantine/`.

## Instalación con Docker

### 1. Construir la imagen

```bash
docker-compose -f docker/docker-compose.yml build
```

### 2. Configurar variables de entorno

Editar `.env` con tus credenciales:

```env
TELEGRAM_API_ID=tu_api_id
TELEGRAM_API_HASH=tu_api_hash
TELEGRAM_CHANNELS=-1002523901612
NOTIFICATION_EMAIL=tu@email.com
```

### 3. Configurar cron

```bash
# Editar crontab
crontab -e

# Agregar línea (ajustar ruta según tu sistema)
0 3 * * * /ruta/al/telegram-video-downloader/docker/run.sh >> /var/log/telegram-downloader-cron.log 2>&1
```

**Nota**: Reemplaza `/ruta/al/telegram-video-downloader` con la ruta real donde está el proyecto.

### 4. Primera ejecución manual

```bash
# Ejecutar manualmente para autenticar
docker-compose -f docker/docker-compose.yml run --rm telegram-downloader

# Seguir las instrucciones de autenticación de Telegram
```

### 5. Verificar logs

```bash
# Ver logs del contenedor
docker logs telegram-downloader

# Ver logs persistentes
docker run --rm -v telegram-downloader_telegram_logs:/logs alpine cat /logs/telegram-downloader.log
```

### 6. Ejecutar pruebas

Ver [TESTING.md](TESTING.md) para instrucciones detalladas.

```bash
chmod +x docker/test.sh
bash docker/test.sh
```

## Estructura de Docker

```
docker/
├── Dockerfile              # Imagen con Python 3.11 + ClamAV
├── docker-compose.yml      # Configuración del contenedor
├── entrypoint.sh           # Script de entrada
├── run.sh                  # Script para cron (verifica si está corriendo)
├── test.sh                 # Script de pruebas automático
├── test_notifications.py   # Genera notificaciones de prueba
└── test_results.json       # Resultados de pruebas (generado)
```

### Volúmenes

| Volumen | Ruta en contenedor | Propósito |
|---|---|---|
| `telegram_downloads` | `/app/downloads` | Vídeos descargados |
| `telegram_logs` | `/app/logs` | Logs con rotación 30 días |
| `telegram_notifications` | `/app/notifications` | Notificaciones JSON compartidas |
| `telegram_session` | `/app/session` | Sesión de Telegram persistente |

### Seguridad

- Usuario no-root (`downloader`)
- Read-only filesystem (excepto volúmenes)
- ClamAV incluido en la imagen
- Límites de recursos: 2GB RAM, 2 CPUs

## Configuración de cron

El contenedor está diseñado para ser ejecutado por un cron externo. Ver [TESTING.md](TESTING.md) para instrucciones detalladas de configuración.

```cron
0 3 * * * /ruta/al/telegram-video-downloader/docker/run.sh >> /var/log/telegram-downloader-cron.log 2>&1
```
