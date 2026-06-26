# Debug: session_data no se monta correctamente

Ejecuta estos comandos en orden y pega la salida:

## 1. Verificar que el directorio existe en el host

```bash
ls -la /data/docker/docker_compose/TELEGRAM-VIDEO-DOWNLOADER/
```

## 2. Verificar que la imagen tiene los directorios correctos

```bash
docker run --rm telegram-downloader ls -la /app/
```

## 3. Verificar permissions del volumen dentro del contenedor

```bash
docker run --rm \
  -v /data/docker/docker_compose/TELEGRAM-VIDEO-DOWNLOADER/session_data:/app/session_data \
  telegram-downloader \
  ls -la /app/session_data/
```

## 4. Debug: ver qué valores lee config.yaml dentro del contenedor

```bash
docker run --rm \
  --env-file .env \
  -v /home/pollito/media/telegram_download_film/downloads:/app/downloads \
  -v /data/docker/docker_compose/TELEGRAM-VIDEO-DOWNLOADER/session_data:/app/session_data \
  telegram-downloader \
  python -c "
import yaml
with open('/app/config.yaml') as f:
    c = yaml.safe_load(f)
print('session_name:', c.get('session_name'))
print('output_dir:', c.get('output_dir'))
"
```

## 5. Crear el directorio si no existe

```bash
mkdir -p /data/docker/docker_compose/TELEGRAM-VIDEO-DOWNLOADER/session_data
ls -la /data/docker/docker_compose/TELEGRAM-VIDEO-DOWNLOADER/
```

## 6. Verificar si hay un archivo .session en algún lado

```bash
find /data/docker/docker_compose/TELEGRAM-VIDEO-DOWNLOADER/ -name "*.session"
find /home/pollito/media/telegram_download_film/ -name "*.session"
```

## 7. Verificar que el volume mount funciona

```bash
docker run --rm \
  -v /data/docker/docker_compose/TELEGRAM-VIDEO-DOWNLOADER/session_data:/app/test_mount \
  telegram-downloader \
  bash -c "echo 'test' > /app/test_mount/test.txt && cat /app/test_mount/test.txt"
```

Después de ejecutar, muestra la salida de cada comando.
