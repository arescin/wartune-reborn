FROM python:3.12-slim

# Dependências de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv via pip (garantido e compatível com uv_build)
RUN pip install --no-cache-dir "uv>=0.12.3"

WORKDIR /app

# Copiar arquivos de configuração e código necessários para o build
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY proto/ ./proto/
COPY data/ ./data/
COPY bundled_cdn/ ./bundled_cdn/

# Sincronizar dependências e instalar o pacote wartune-server
RUN uv sync --no-dev

# Criar pastas para dados e logs
RUN mkdir -p /app/data/templates /app/logs

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    WARTUNE_BIND_HOST="0.0.0.0" \
    WARTUNE_PUBLIC_HOST="0.0.0.0" \
    WARTUNE_HTTP_PORT=8080 \
    WARTUNE_SOCKET_PORT=5000 \
    WARTUNE_WEBSOCKET_PORT=5001 \
    WARTUNE_POLICY_PORT=843 \
    WARTUNE_DATABASE_URL="sqlite+aiosqlite:////app/data/wartune.db" \
    WARTUNE_TEMPLATES_FILE="/app/data/templates/tempinfos.xml" \
    WARTUNE_RSA_KEY_FILE="/app/data/rsa_private.pem" \
    WARTUNE_EVENTS_FILE="/app/data/events.json" \
    WARTUNE_LOG_DIR="/app/logs" \
    WARTUNE_LOG_LEVEL="INFO"

EXPOSE 8080 5000 5001 843

CMD ["sh", "-c", "mkdir -p /app/data/cdn && cp -rf /app/bundled_cdn/* /app/data/cdn/ 2>/dev/null || true; uv run wartune-server db init && exec uv run wartune-server run"]
