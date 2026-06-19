# Guía de pruebas - Telegram Video Downloader

## Prerrequisitos

- Docker instalado y funcionando
- Docker Compose instalado
- Permisos para ejecutar comandos Docker (usuario en grupo `docker` o sudo)
- Proyecto clonado en tu máquina

## Ejecutar pruebas automáticas

```bash
# Navegar al directorio del proyecto
cd /ruta/al/telegram-video-downloader

# Dar permisos de ejecución al script
chmod +x docker/test.sh

# Ejecutar pruebas
bash docker/test.sh
```

El script ejecutará 8 tests automáticamente:

1. **Construcción de imagen Docker** - Verifica que la imagen se construye sin errores
2. **Ejecución del contenedor** - Verifica que el contenedor se ejecuta y termina correctamente
3. **Verificación de volúmenes** - Verifica que se crean los 4 volúmenes esperados
4. **Verificación de logs** - Verifica que se genera el archivo de log
5. **Verificación de notificaciones** - Verifica que existe el archivo de notificaciones
6. **Notificaciones forzadas** - Genera 3 notificaciones de prueba y verifica que se crean
7. **Test de rendimiento** - Mide tiempo de ejecución, uso de memoria y tamaño de imagen
8. **Script de ejecución** - Verifica que run.sh funciona correctamente

## Verificar resultados

Los resultados se guardan en `docker/test_results.json`:

```bash
cat docker/test_results.json | python3 -m json.tool
```

Ejemplo de resultado:

```json
{
  "timestamp": "2026-06-19T03:00:00+02:00",
  "tests": [
    {"name": "docker_build", "status": "pass", "message": "...", "details": "..."},
    ...
  ],
  "summary": {
    "total": 8,
    "passed": 7,
    "failed": 1,
    "skipped": 0
  }
}
```

## Limpieza manual

```bash
# Eliminar contenedor
docker rm -f telegram-downloader

# Eliminar volúmenes
docker volume rm telegram-downloader_telegram_downloads
docker volume rm telegram-downloader_telegram_logs
docker volume rm telegram-downloader_telegram_notifications
docker volume rm telegram-downloader_telegram_session

# Eliminar imagen
docker rmi telegram-downloader_telegram-downloader

# Eliminar resultados de pruebas
rm docker/test_results.json
```

## Comandos útiles para debugging

```bash
# Ver logs del contenedor
docker logs telegram-downloader

# Ver logs persistentes
docker run --rm -v telegram-downloader_telegram_logs:/logs alpine cat /logs/telegram-downloader.log

# Ver notificaciones
docker run --rm -v telegram-downloader_telegram_notifications:/notifications alpine cat /notifications/notifications.json

# Ver volúmenes
docker volume ls | grep telegram

# Ver contenedores
docker ps -a | grep telegram

# Ejecutar contenedor manualmente
docker-compose -f docker/docker-compose.yml run --rm telegram-downloader

# Ejecutar con dry-run
docker-compose -f docker/docker-compose.yml run --rm telegram-downloader python src/verify_all.py --dry-run
```

## Configuración de cron

Editar crontab:

```bash
crontab -e
```

Agregar línea para ejecutar diariamente a las 03:00:

```cron
0 3 * * * /ruta/al/telegram-video-downloader/docker/run.sh >> /var/log/telegram-downloader-cron.log 2>&1
```

**Nota**: Reemplaza `/ruta/al/telegram-video-downloader` con la ruta real donde está el proyecto en tu sistema.
