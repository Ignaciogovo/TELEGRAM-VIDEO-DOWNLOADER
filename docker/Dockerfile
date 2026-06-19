FROM python:3.11-slim

# Instalar ClamAV y dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    clamav \
    clamav-daemon \
    procps \
    time && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Actualizar base de datos de ClamAV (puede fallar en build, no crítico)
RUN freshclam || echo "WARNING: freshclam failed, will update at runtime"

# Crear usuario no-root
RUN groupadd -r downloader && \
    useradd -r -g downloader -d /app -s /sbin/nologin downloader

# Directorio de trabajo
WORKDIR /app

# Copiar dependencias primero (para caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY src/ ./src/
COPY config.yaml .

# Crear directorios necesarios
RUN mkdir -p /app/downloads /app/logs /app/notifications /app/session && \
    chown -R downloader:downloader /app

# Entry point (debe ser antes de cambiar a usuario no-root)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Cambiar a usuario no-root
USER downloader

# Volúmenes
VOLUME ["/app/downloads", "/app/logs", "/app/notifications", "/app/session"]

ENTRYPOINT ["/entrypoint.sh"]
