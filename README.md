# Telegram Video Downloader

## Visión general

Demonio (daemon) que se ejecuta en un contenedor Docker de forma continua. Su misión: descargar TODOS los vídeos de un canal de Telegram y cada día verificar cuáles faltan para descargarlos automáticamente. Los vídeos descargados se clasifican en directorios según reglas basadas en metadatos (sin IA).

## Estado actual

**Fase 1 de 3** — Descarga de un único vídeo del canal de Telegram.

- [x] Conexión autenticada a Telegram con Telethon
- [x] Descarga de un único vídeo (el más reciente o por message_id)
- [x] Progreso en terminal
- [x] Guardado en directorio configurable
- [x] Script ejecutable con comando simple
- [ ] Descarga de múltiples vídeos y categorización por reglas YAML (Fase 2)
- [ ] Daemon completo + contenedor Docker (Fase 3)

## Requisitos previos

### Obtener credenciales de Telegram API

1. Ve a [https://my.telegram.org/apps](https://my.telegram.org/apps)
2. Inicia sesión con tu número de teléfono
3. Ve a **API development tools**
4. Crea una nueva aplicación (puede ser cualquier nombre y descripción)
5. Copia el **App api_id** y **App api_hash**

### Requisitos del sistema

- Python 3.11+
- pip

## Instalación

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración

Edita el archivo `config.yaml` con tus credenciales y preferencias:

```yaml
# Obtén api_id y api_hash en https://my.telegram.org/apps
api_id: 12345678
api_hash: "tu_api_hash_aqui"

# Nombre de la sesión (archivo .session donde se guarda la autenticación)
session_name: "telegram_downloader"

# Username del canal de Telegram (con @ o sin @)
channel_username: "tu_canal_aqui"

# Directorio donde se guardarán los vídeos descargados
output_dir: "./downloads"

# Nivel de log: DEBUG, INFO, WARNING, ERROR, CRITICAL
log_level: "INFO"
```

## Uso (Fase 1)

### Descargar el vídeo más reciente del canal

```bash
python src/main.py
```

### Descargar un vídeo específico por su message_id

```bash
python src/main.py --message-id 123
```

### Usar un archivo de configuración personalizado

```bash
python src/main.py --config mi_config.yaml
```

### Primera ejecución

La primera vez que ejecutes el script, Telethon te pedirá:

1. Tu número de teléfono (con código de país, ej: +34600123456)
2. El código de verificación que recibirás en Telegram
3. Si tienes verificación en dos pasos, tu contraseña

La sesión se guarda automáticamente en un archivo `.session` para no tener que autenticarse de nuevo.

## Próximas fases

### Fase 2 — Descarga masiva y categorización (NO implementada)

- Descarga de todos los vídeos de un canal
- Verificación diaria de vídeos nuevos
- Categorización automática por reglas YAML (fecha, duración, tamaño, etc.)
- Historial de descargas para evitar duplicados

### Fase 3 — Daemon + Docker (NO implementada)

- Daemon que se ejecuta continuamente
- Contenedor Docker para despliegue
- Scheduler para verificaciones diarias automáticas
- Logs persistentes y rotación
- Health checks y monitoring
