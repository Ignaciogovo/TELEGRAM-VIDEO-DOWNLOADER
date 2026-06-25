# Imagen base multi-arch
FROM --platform=$TARGETPLATFORM python:3.12-slim

LABEL maintainer="telegram-downloader"
LABEL description="Telegram video downloader with security scanning (non-root)"

# Dependencias del sistema (clamav, ffmpeg, tini)
# freshclam actualiza las firmas durante el build
RUN apt-get update && apt-get install -y --no-install-recommends \
    clamav \
    clamav-freshclam \
    ffmpeg \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && freshclam

# Crear usuario y grupo no-root (UID/GID 1000 estándar)
ARG UID=1000
ARG GID=1000
RUN groupadd --gid ${GID} appuser \
    && useradd --uid ${UID} --gid ${GID} --create-home --shell /bin/bash appuser

# Directorio de trabajo
WORKDIR /app

# Dependencias Python (como root, luego ajustar ownership)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && chown -R appuser:appuser /usr/local/lib/python3.12/site-packages

# Código fuente con ownership correcto desde el inicio
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser config.yaml .
COPY --chown=appuser:appuser docker-entrypoint.sh /usr/local/bin/
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh

# Crear directorios para volúmenes con ownership correcto
RUN mkdir -p /app/downloads /app/session_data \
    && chown -R appuser:appuser /app/downloads /app/session_data

# Cambiar a usuario no-root
USER appuser

# Volúmenes para persistencia
VOLUME ["/app/downloads", "/app/session_data"]

# tini como PID 1 para manejo correcto de señales
ENTRYPOINT ["/usr/bin/tini", "--", "docker-entrypoint.sh"]
CMD ["--all"]
