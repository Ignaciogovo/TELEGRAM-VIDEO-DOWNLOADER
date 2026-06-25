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

## Seguridad

Cada vídeo tiene un 10% de probabilidad de ser escaneado por ClamAV o VirusTotal. Si se detecta amenaza, se mueve a `downloads/quarantine/`.
