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

### Fase 2: Descarga Masiva 🔄 EN PROGRESO
- Historial SQLite con checkpoint
- Filtros (duración, límite diario)
- Mapeo canales → carpetas
- Escaneo de seguridad
- Notificaciones JSON
- Logs rotativos
- Dry-run mode
- Verificación completa

### Fase 3: Daemon + Cron ⏸️ PAUSADA
- Script de ejecución automática
- Configuración de cron
- Monitoreo de salud
- (Definir cuando se reanude)

### Fases Futuras
- Posibles nuevas funcionalidades
- Se definirán según necesidades

## 10. Estado Actual

**Rama activa:** `feature/fase-2-bulk-download`
**Fase:** 2 (Descarga Masiva)
**Estado:** En progreso, 1/8 todos completados
**Próximo paso:** TODO 2 (Verificación de integridad de archivos)

## 11. To-dos Pendientes Fase 2

### TODO 1: Corregir paths hardcoded
- `notifier.py`: cambiar default de `/app/notifications` a `./downloads/notifications`
- `logger.py`: cambiar default de `/app/logs` a `./downloads/logs`
- Ambos deben respetar `output_dir` de `config.yaml`

### TODO 2: Verificación de integridad de archivos descargados
- Validar que el archivo descargado es un vídeo válido
- Si no es válido, mover a cuarentena y notificar
- Registrar en historial como "invalid"

### TODO 3: Manejo de archivos parcialmente descargados
- Detectar archivos temporales o incompletos
- Limpiar archivos incompletos al iniciar sesión
- Opción de reintentar descargas fallidas

### TODO 4: Resumen final de sesión
- Mostrar resumen detallado al finalizar sesión
- Incluir: vídeos encontrados, descargados, saltados, errores
- Tiempo total, velocidad promedio, espacio usado
- Guardar resumen en log

### TODO 5: Notificación de finalización
- Generar notificación JSON cuando se completa una sesión
- Incluir resumen de la sesión

### TODO 6: Validación de espacio en disco
- Antes de descargar, verificar espacio disponible
- Si no hay espacio suficiente, notificar y detener

### TODO 7: Tests automatizados básicos
- Crear script de tests sin Docker
- Tests de: configuración, historial, notificaciones, escáner

### TODO 8: Timeout y reintentos configurables
- Timeout configurable para descargas
- Límite de reintentos por vídeo
- Logging de velocidad de descarga

## 12. Progreso de To-dos

| # | Todo | Estado |
|---|------|--------|
| 1 | Corregir paths hardcoded | ✅ Completado |
| 2 | Verificación de integridad | ⏳ Pendiente |
| 3 | Archivos parcialmente descargados | ⏳ Pendiente |
| 4 | Resumen final de sesión | ⏳ Pendiente |
| 5 | Notificación de finalización | ⏳ Pendiente |
| 6 | Validación de espacio en disco | ⏳ Pendiente |
| 7 | Tests automatizados | ⏳ Pendiente |
| 8 | Timeout y reintentos | ⏳ Pendiente |

## 13. Checklist de Validación de Fase

Antes de considerar una fase completa:
- [ ] Todos los todos completados
- [ ] Tests funcionales pasando
- [ ] Código revisado y limpio
- [ ] Documentación actualizada
- [ ] Validación manual del usuario
- [ ] Merge a `develop` aprobado
