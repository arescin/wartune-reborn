# Dockerfile raiz para Wartune Reborn
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY wartune-reborne-emulator/pyproject.toml wartune-reborne-emulator/uv.lock ./

RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir \
    aiohttp>=3.14.3 \
    aiosqlite>=0.22.1 \
    alembic>=1.20.0 \
    asyncmy>=0.2.16 \
    asyncpg>=0.32.0 \
    cryptography>=50.0.1 \
    protobuf>=7.36.1 \
    pydantic-settings>=2.15.0 \
    "sqlalchemy[asyncio]>=2.0.30" \
    structlog>=26.1.0 \
    tzdata>=2025.2

COPY wartune-reborne-emulator/src/ ./src/
COPY wartune-reborne-emulator/data/ ./data/
COPY wartune-reborne-emulator/tools/ ./tools/
COPY wartune-reborne-emulator/proto/ ./proto/
COPY wartune-reborne-emulator/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 8080 5000 5001 843

ENTRYPOINT ["/entrypoint.sh"]
CMD ["run"]
