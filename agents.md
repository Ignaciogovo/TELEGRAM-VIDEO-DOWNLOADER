## Git Workflow

- `master` → producción
- `develop` → integración
- `feature/<nombre>` → cambios (desde develop, merge a develop)

No mergear a develop hasta validación del usuario. No iniciar siguiente fase sin confirmación.

### Commits

`feat:` nueva funcionalidad | `fix:` bug | `docs:` documentación | `refactor:` sin cambio funcional | `chore:` mantenimiento

## Seguridad

- Escaneo aleatorio configurable (ClamAV/VirusTotal)
- Amenazas → `downloads/quarantine/`
- NUNCA commitear `.env` ni `*.session` (están en `.gitignore`)
