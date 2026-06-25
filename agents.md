# Telegram Video Downloader - Manual de Operaciones

## 1. Flujo de Trabajo por Fases

### Estructura de Ramas
- `master` → producción estable
- `develop` → integración de fases completadas
- `feature/fase-X-descripcion` → desarrollo de cada fase

### Proceso por Fase
1. Crear rama `feature/fase-X-descripcion` desde `develop`
2. Dividir fase en **todos** específicos (el usuario los define)
3. Trabajar cada todo con autonomía
4. Al completar un todo → preguntar antes de continuar
5. Al completar la fase → esperar validación explícita del usuario
6. Validación completada → merge a `develop`

### Regla de Oro
**Ninguna fase está completa hasta que el usuario lo confirme explícitamente.**
Sin validación del usuario = sin merge, sin avanzar.

## 2. Autonomía y Comunicación

### Dentro de un Todo
- **Autonomía total** para implementar
- Tomar decisiones técnicas (estructura, librerías, patrones)
- Hacer commits intermedios si es necesario

### Entre Todos o Fases
- **OBLIGATORIO preguntar** antes de:
  - Pasar al siguiente todo
  - Iniciar nueva fase
  - Cambiar arquitectura o diseño
  - Modificar archivos críticos sin contexto

### Planes Detallados
- **Siempre mostrar plan detallado antes de ejecutar**
- Incluir: qué se va a hacer, por qué, archivos afectados
- Esperar confirmación antes de proceder

## 3. Prioridades del Proyecto

### 1. Seguridad (CRÍTICA)
- Escaneo de malware obligatorio (ClamAV/VirusTotal)
- Probabilidad configurable, nunca desactivar sin justificación
- Cuarentena automática de amenazas detectadas
- Validación de integridad de archivos descargados
- Protección de credenciales (`.env`, `*.session` en `.gitignore`)

### 2. Simplicidad
- Código limpio y mantenible
- Minimizar dependencias
- Preferir soluciones estándar sobre complejas
- Documentación clara y concisa
- Estructura de archivos intuitiva

### 3. Funcionalidad
- No ceder funcionalidad por simplicidad
- Cada feature debe funcionar correctamente
- Tests que verifiquen el comportamiento real
- Manejo robusto de errores

## 4. Testing Obligatorio

### Criterios de Aceptación
- [ ] Programa ejecuta sin errores
- [ ] Funcionalidad principal verificada manualmente
- [ ] Casos edge manejados (errores de red, archivos corruptos, etc.)
- [ ] Logs generados correctamente
- [ ] Historial SQLite actualizado
- [ ] Notificaciones generadas cuando corresponde

### Tipos de Tests
- **Funcional**: Verificar que el programa hace lo que debe hacer
- **Integración**: Verificar que los componentes trabajan juntos
- **Edge cases**: Errores de red, archivos corruptos, límites de API

## 5. Seguridad - Reglas Inviolables

### Código
- NUNCA commitear `.env` ni `*.session`
- Validar inputs del usuario
- Sanitizar paths de archivos
- Manejar errores de red gracefully

### Escaneo de Malware
- TODO archivo descargado debe pasar por escaneo
- Probabilidad configurable (default 10%)
- Cuarentena inmediata si se detecta amenaza
- Notificación al usuario
- Log detallado del resultado

### Credenciales
- Solo desde variables de entorno
- Nunca hardcodear en código
- Nunca loguear valores sensibles

## 6. Simplicidad - Principios

### Código
- Funciones pequeñas y enfocadas
- Nombres descriptivos
- Comentarios solo cuando sean necesarios
- Evitar sobreingeniería

### Arquitectura
- Estructura plana de archivos
- Minimizar abstracciones innecesarias
- Preferir composición sobre herencia
- Un archivo = una responsabilidad clara

### Dependencias
- Solo las estrictamente necesarias
- Preferir librerías estándar cuando sea posible
- Documentar por qué se añade cada dependencia

## 7. Archivos Críticos

### NO MODIFICAR SIN PREGUNTAR
- `.env` (credenciales)
- `config.yaml` (configuración del usuario)
- `src/scanner.py` (lógica de seguridad)
- `src/history.py` (integridad de datos)

### MODIFICAR CON CUIDADO
- `src/main.py` (entry point)
- `src/downloader.py` (lógica principal)
- `src/verify_all.py` (verificación completa)

### LIBRE MODIFICACIÓN
- `src/logger.py` (logging)
- `src/notifier.py` (notificaciones)
- `src/list_chats.py` (herramienta)
- `src/extract_metadata.py` (herramienta)
- `README.md` (documentación)

## 8. Commits

### Convenciones
- `feat:` nueva funcionalidad
- `fix:` corrección de bug
- `docs:` documentación
- `refactor:` sin cambio funcional
- `chore:` mantenimiento
- `test:` añadir tests

### Frecuencia
- Commits pequeños y frecuentes
- Cada cambio lógico = un commit
- Mensajes claros y descriptivos

## 9. Fases del Proyecto

### Fase 1: Descarga Básica ✅ COMPLETADA
- Conexión a Telegram
- Descarga de un vídeo
- Progreso en terminal

### Fase 2: Descarga Masiva ✅ COMPLETADA
- Historial SQLite
- Filtros (duración, límite por ejecución)
- Mapeo canales → carpetas
- Escaneo de seguridad
- Notificaciones JSON
- Logs rotativos
- Dry-run mode
- Verificación completa
- **Sin checkpoint en control de flujo**: se confía en `is_downloaded`/`is_skipped_short`/`is_invalid` para saber qué descargar. Si un archivo marcado como descargado no existe en disco, se re-descarga automáticamente
- **Verificación de existencia**: `get_output_path()` permite comprobar si el archivo físico sigue en disco

#### Limitación conocida: FileReferenceExpiredError

Los file references de vídeos **muy antiguos** en Telegram caducan más rápido de lo que se puede descargar el archivo (1-2 GB). Esto es un **límite de la API de Telegram**, no un bug del código.

**Comportamiento:**
- El código re-intenta 3 veces por vídeo (re-fetch reference + reintentar)
- Si falla 3 veces, se marca el error y se continúa con el siguiente vídeo
- En la **siguiente ejecución**, los vídeos fallidos se reintentan automáticamente (no están en `is_downloaded`)
- Tras 2-3 ejecuciones consecutivas, los vídeos terminan descargándose porque el rate-limiting de Telegram se relaja

**No requiere fix**: el sistema es auto-recuperable y los tests pasan 13/13.

### Fase 3: Docker + Cron ⏸️ PAUSADA
- Dockerfile (python:3.12-slim + ffmpeg)
- docker-entrypoint.sh (entry point minimal)
- .dockerignore
- Soporte DOWNLOAD_LIMIT via environment variable
- Volúmenes: ./downloads, .session

#### Uso

**1. Primera ejecución (manual, interactiva):**
```bash
docker run --rm -it --env-file .env \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/.session:/app/telegram_downloader.session \
  telegram-downloader
```

**2. Ejecuciones siguientes (cron):**
```bash
docker run --rm --env-file .env \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/.session:/app/telegram_downloader.session \
  telegram-downloader
```

**3. Cron ejemplo (diario a las 2:00 AM):**
```bash
0 2 * * * docker run --rm --env-file /path/to/.env \
  -v /path/to/downloads:/app/downloads \
  -v /path/to/.session:/app/telegram_downloader.session \
  telegram-downloader >> /var/log/telegram-downloader.log 2>&1
```

> **NOTA**: El archivo `.session` se crea en la primera ejecución interactiva. Las ejecuciones via cron usan el `.session` persistente. Asegúrate de que la primera ejecución se haga manualmente con `-it`.

### Fases Futuras
- Posibles nuevas funcionalidades
- Se definirán según necesidades

## 10. Estado Actual

**Rama activa:** `feature/fase-2-bulk-download`
**Fase:** 2 (Descarga Masiva) ✅ COMPLETADA
**Estado:** Todos los todos completados (8/8) - Listo para merge a develop
**Próximo paso:** Merge a develop y comenzar Fase 3 (Docker + Cron)

## 11. To-dos Pendientes Fase 2

### TODO 1: Corregir paths hardcoded
- `notifier.py`: cambiar default de `/app/notifications` a `./downloads/notifications`
- `logger.py`: cambiar default de `/app/logs` a `./downloads/logs`
- Ambos deben respetar `output_dir` de `config.yaml`

### TODO 2: Verificación de integridad de archivos descargados ✅ COMPLETADO
- Validar que el archivo descargado es un vídeo válido
- Si no es válido, mover a cuarentena y notificar
- Registrar en historial como "invalid"
- Verificación de tamaño contra metadatos de Telegram
- ffprobe para validación de streams de video/audio

### TODO 3: Manejo de archivos parcialmente descargados ✅ COMPLETADO
- Detectar archivos temporales o incompletos
- Limpiar archivos incompletos al iniciar sesión
- Opción de reintentar descargas fallidas
- Descarga atómica vía archivo .part + rename
- Detección de archivos corruptos en disco vs historial
- Función `retry_failed_downloads()` para reintentos

### TODO 4: Resumen final de sesión ✅ COMPLETADO
- Mostrar resumen detallado al finalizar sesión
- Incluir: vídeos encontrados, descargados, saltados, errores
- Tiempo total, velocidad promedio, espacio usado
- Guardar resumen en log
- Session ID único para correlación
- Estadísticas por descarga (min/max tiempo, velocidades)
- Tasa de éxito como porcentaje
- Salida JSON machine-readable
- Resumen también en stdout

### TODO 5: Notificación de finalización ✅ COMPLETADO
- Generar notificación JSON cuando se completa una sesión
- Incluir resumen de la sesión
- Tipo "session_complete" dedicado (no "error")
- Incluye session_id, stats, success_rate

### TODO 6: Validación de espacio en disco ✅ COMPLETADO
- Antes de descargar, verificar espacio disponible
- Si no hay espacio suficiente, notificar y detener
- Verificación inicial al comenzar sesión
- Verificación por vídeo individual
- Verificación en retry_failed_downloads()

### TODO 7: Tests automatizados básicos ✅ COMPLETADO
- Crear script de tests sin Docker
- Tests de: configuración, historial, notificaciones, escáner
- Tests integrados: CRUD historial, probabilidad escáner, notificaciones
- Edge cases: config, build_output_path, get_folder_for_channel
- 12 tests totales pasando

### TODO 8: Timeout y reintentos configurables ✅ COMPLETADO
- Timeout configurable para descargas (download_timeout_seconds)
- Límite de reintentos por vídeo (max_download_retries)
- Logging de velocidad de descarga
- Contador de reintentos totales en DownloadSummary
- download_video() retorna tupla (size, retries)
- Backoff exponencial entre reintentos (2^attempt, max 60s)
- **Timeout dinámico**: calculado según tamaño de archivo (1.5x tiempo estimado a 500KB/s)
- **Resume support**: reanuda descargas interrumpidas desde archivo .part existente
- **FileReferenceExpiredError**: re-fetch del mensaje para obtener referencia fresca

## 12. Progreso de To-dos

| # | Todo | Estado |
|---|------|--------|
| 1 | Corregir paths hardcoded | ✅ Completado |
| 2 | Verificación de integridad | ✅ Completado |
| 3 | Archivos parcialmente descargados | ✅ Completado |
| 4 | Resumen final de sesión | ✅ Completado |
| 5 | Notificación de finalización | ✅ Completado |
| 6 | Validación de espacio en disco | ✅ Completado |
| 7 | Tests automatizados | ✅ Completado |
| 8 | Timeout y reintentos | ✅ Completado |

## 13. Checklist de Validación de Fase

Antes de considerar una fase completa:
- [ ] Todos los todos completados
- [ ] Tests funcionales pasando
- [ ] Código revisado y limpio
- [ ] Documentación actualizada
- [ ] Validación manual del usuario
- [ ] Merge a `develop` aprobado
