#!/usr/bin/env bash
set -e

echo "[Wartune-Server] Iniciando inicialização do servidor de jogo..."

# Garantir diretórios necessários sem perder templates incluídos na imagem
mkdir -p /app/data/templates /app/logs
if [ ! -f /app/data/templates/tempinfos.xml ] && [ -f /app/image-data/templates/tempinfos.xml ]; then
    cp /app/image-data/templates/tempinfos.xml /app/data/templates/tempinfos.xml
fi

# Se o banco configurado for PostgreSQL ou MySQL, aguardar a porta estar disponível
if [[ "${WARTUNE_DATABASE_URL}" == *"postgresql"* ]] || [[ "${WARTUNE_DATABASE_URL}" == *"postgres"* ]]; then
    DB_HOST=$(echo "${WARTUNE_DATABASE_URL}" | sed -E 's/.*@([^:/]+).*/\1/')
    DB_PORT=$(echo "${WARTUNE_DATABASE_URL}" | sed -E 's/.*:([0-9]+)\/.*/\1/')
    DB_PORT=${DB_PORT:-5432}
    echo "[Wartune-Server] Aguardando banco PostgreSQL em ${DB_HOST}:${DB_PORT}..."
    while ! nc -z "${DB_HOST}" "${DB_PORT}"; do
        sleep 1
    done
    echo "[Wartune-Server] PostgreSQL pronto!"
elif [[ "${WARTUNE_DATABASE_URL}" == *"mysql"* ]]; then
    DB_HOST=$(echo "${WARTUNE_DATABASE_URL}" | sed -E 's/.*@([^:/]+).*/\1/')
    DB_PORT=$(echo "${WARTUNE_DATABASE_URL}" | sed -E 's/.*:([0-9]+)\/.*/\1/')
    DB_PORT=${DB_PORT:-3306}
    echo "[Wartune-Server] Aguardando banco MySQL em ${DB_HOST}:${DB_PORT}..."
    while ! nc -z "${DB_HOST}" "${DB_PORT}"; do
        sleep 1
    done
    echo "[Wartune-Server] MySQL pronto!"
fi

# Inicializar schema do banco e templates caso necessário
echo "[Wartune-Server] Executando migrações Alembic e checagem de templates..."
python -c "
import asyncio
from wartune_server.config import Settings
from wartune_server.cli import _db_init

settings = Settings()
asyncio.run(_db_init(settings))
"

if [ "$1" = "run" ]; then
    echo "[Wartune-Server] Subindo processo principal wartune-server run..."
    exec python -c "
import asyncio
from wartune_server.config import Settings
from wartune_server.cli import _run

settings = Settings()
asyncio.run(_run(settings))
"
else
    exec "$@"
fi
