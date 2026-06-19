## Git Workflow

### Estructura de ramas
- `master` → Producción (solo merges desde develop)
- `develop` → Integración (rama principal de desarrollo)
- `feature/<descripcion>` → Cambios específicos (desde develop, merge a develop)

### Flujo de trabajo
1. Partir siempre de `develop` actualizada
2. Crear rama feature: `git checkout -b feature/<descripcion-cambio>`
3. Realizar cambios y commit en la rama feature
4. Merge a `develop` para revisión
5. Una vez validado, merge de `develop` a `master`

### Convenciones de commits
- `feat:` nueva funcionalidad
- `fix:` corrección de bug
- `docs:` documentación
- `refactor:` refactorización sin cambio funcional
- `chore:` tareas de mantenimiento

### Fases del proyecto
- Cada fase se desarrolla en su propia rama feature
- No mergear a develop hasta que el usuario valide la fase
- No iniciar la siguiente fase sin confirmación explícita del usuario

### Seguridad
La seguridad es una **PRIORIDAD** del proyecto. Los vídeos descargados de fuentes
no verificadas pueden contener malware embebido.

- TODO vídeo descargado tiene una probabilidad configurable de ser escaneado
- Motor por defecto: ClamAV (local, offline)
- Motor alternativo: VirusTotal API (cloud, multi-engine)
- Si un fichero se detecta como amenaza, se mueve a `downloads/quarantine/` y se registra
- Si el motor de escaneo no está disponible, se registra un WARNING pero la descarga continúa
- NUNCA desactivar el escaneo en producción sin justificación documentada
- Las credenciales API y claves de sesión NUNCA deben commitearse al repositorio
- `.env` y `*.session` están en `.gitignore` y no deben excluirse
