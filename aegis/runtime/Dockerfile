# Aegis runtime — Phase 0-1 image.
# Build context is the REPO ROOT (see docker-compose.yml) so the whole kernel is available.
FROM python:3.11-slim

WORKDIR /app

# deps first (layer cache)
COPY runtime/requirements.txt /app/runtime/requirements.txt
RUN pip install --no-cache-dir -r /app/runtime/requirements.txt

# the kernel + runtime code
COPY . /app

# the runtime package is under /app/runtime; the kernel is /app
ENV PYTHONPATH=/app/runtime \
    AEGIS_KERNEL=/app \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "aegis_runtime.cli"]
CMD ["premarket", "--date", "2026-07-21"]
