# Dockerfile para o Servidor de Jogo Wartune Reborn (Python / asyncio)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Instalar dependências de sistema mínimas (compiladores se necessário e curl para healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de dependências
COPY pyproject.toml uv.lock ./

# Instalar dependências Python via pip
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

# Copiar código-fonte, dados e ferramentas
COPY src/ ./src/
COPY data/ ./data/
COPY data/templates/ ./image-data/templates/
COPY tools/ ./tools/
COPY proto/ ./proto/
COPY docker/server/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

# Portas:
# 8080 = HTTP (REQUEST_PATH)
# 5000 = Game TCP Socket
# 5001 = WebSocket (Ruffle proxy)
# 843 = Flash Policy Server
EXPOSE 8080 5000 5001 843

VOLUME ["/app/data", "/app/logs"]

ENTRYPOINT ["/entrypoint.sh"]
CMD ["run"]
