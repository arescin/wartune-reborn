# Wartune Reborn Emulator — Ecossistema Completo

Emulador e infraestrutura completa para o jogo **Legend Online / Wartune** (versão cliente Flash 7Road), composto por Portal Web de autenticação, Servidor de Jogo assíncrono em Python e CDN de recursos gráficos e módulos SWF.

---

## 1. VISÃO GERAL DA ARQUITETURA

O projeto é organizado em três componentes integrados:

1. **`CDN/`**: Espelho dos recursos do jogo oficial S134 (~9,83 GB em 38.237 arquivos):
   - `res134-bmclas-sq.7road.net/`: Recursos gráficos, avatares, equipamentos, mapas, sons e módulos de código SWF/PNG.
   - `s134-bmclas-sq.7road.net/`: Loader principal (`Loading.swf`), tabelas de verificação (`resouececheck.sq`), templates (`tempinfos.xml`) e versões.
2. **`Wartune Reborn Portal v1/`** (Portal):
   - Aplicação PHP 8.1+ para registro de contas, autenticação, seleção de servidores, emissão de tickets criptográficos (`play_tickets`), geração dinâmica de `config.xml` (`ClientConfig.php`) e painel administrativo (GM).
   - Suporte duplo de execução do cliente: via **Flash Player Projector** nativo (desktop) e via **Ruffle** (emulador Flash WebAssembly no navegador).
3. **`wartune-reborne-emulator/`** (Servidor do Jogo):
   - Servidor assíncrono em Python 3.12+ (`asyncio`, `aiohttp`, `SQLAlchemy 2.0`, `Alembic`, `Protobuf`, `structlog`).
   - Portas:
     - `8080`: HTTP dinâmico do cliente Flash (`REQUEST_PATH`).
     - `5000`: Socket TCP principal do jogo (mensagens Protobuf com cifra de fluxo Wartune e Flash Policy).
     - `5001`: WebSocket bridge para conexões via navegador usando o emulador Ruffle (`socketProxy`).
     - `843`: Policy Server dedicado.

---

## 2. REQUISITOS DE SISTEMA

### Ambiente Local (Desenvolvimento)
- **Python:** 3.12 ou 3.13 com as dependências listadas em `wartune-reborne-emulator/pyproject.toml`.
- **Banco de Dados:** SQLite (padrão local em `data/wartune.db`) ou PostgreSQL / MariaDB.
- **Cliente:** Flash Player Projector ou navegador web moderno com suporte a WebAssembly (Ruffle).

### Ambiente de Produção (Docker / VPS / EasyPanel)
- VPS Linux (ex: Hostinger) com Docker e Docker Compose instalados.
- EasyPanel (opcional, para gerenciamento simplificado com interface gráfica).
- Banco de Dados: PostgreSQL 16 (recomendado para integridade transacional multi-container).

---

## 3. INICIALIZAÇÃO RÁPIDA

### Modo Docker (Recomendado)
```bash
# 1. Copie o arquivo de variáveis de ambiente
cp .env.example .env

# 2. Ajuste as variáveis do .env conforme seu IP ou domínio

# 3. Suba todos os serviços
docker compose up -d

# 4. Acompanhe os logs
docker compose logs -f wartune-server
```

Acesse o portal em: `http://localhost:8090/portal/`

### Modo Local (Python Direto no Host)
```powershell
# 1. No diretório do servidor
cd wartune-reborne-emulator

# 2. Execute a inicialização do banco e importação dos templates
python -c "import asyncio; from wartune_server.config import Settings; from wartune_server.cli import _db_init; asyncio.run(_db_init(Settings()))"

# 3. Inicie o servidor
python -c "import asyncio; from wartune_server.config import Settings; from wartune_server.cli import _run; asyncio.run(_run(Settings()))"
```

---

## 4. ESTRUTURA DO PROJETO

```
wartune-reborn-emulator/
├── CDN/                                # Espelho dos assets do jogo (~9.8 GB)
│   ├── res134-bmclas-sq.7road.net/     # Assets visuais, SWFs, mapas, sons
│   └── s134-bmclas-sq.7road.net/       # Loading.swf, tempinfos.xml, version.xml
├── Wartune Reborn Portal v1/           # Aplicação Web PHP (Portal do jogador)
│   ├── index.php                       # Redirecionador para /portal
│   └── portal/                         # Código PHP, classes e templates
│       ├── config.php                  # Configurações dinâmicas (ENV)
│       ├── index.php                   # Cadastro, login e lista de servidores
│       ├── play.php                    # Tela de jogo (Projector e Ruffle)
│       ├── client-config.php           # Geração do config.xml em tempo real
│       └── admin.php                   # Painel GM
├── wartune-reborne-emulator/           # Backend do jogo em Python
│   ├── src/wartune_server/             # Código-fonte modular do emulador
│   ├── data/                           # Banco de dados, templates e chave RSA
│   ├── tests/                          # 1012 testes automatizados
│   └── docs/                           # Documentação técnica profunda
├── docker/                             # Arquivos de conteinerização
│   ├── server/                         # Dockerfile e entrypoint do servidor
│   ├── portal/                         # Dockerfile e apache.conf do portal
│   └── cdn/                            # Dockerfile e nginx.conf da CDN
├── docker-compose.yml                  # Orquestração local (Postgres, Server, Portal, CDN)
├── docker-compose.prod.yml             # Orquestração para Produção / EasyPanel
├── .env.example                        # Modelo de variáveis de ambiente
├── AUDITORIA.md                        # Relatório da auditoria completa e diagnóstico
├── CHANGELOG.md                        # Histórico de alterações
└── DEPLOYMENT.md                       # Manual detalhado de implantação em VPS
```

---

## 5. TESTES E HOMOLOGAÇÃO

O projeto conta com mais de 1000 testes automatizados cobrindo protocolo, banco de dados, regras de negócio e o fluxo completo do jogador:

```powershell
cd wartune-reborne-emulator
$env:PYTHONPATH="src"
python -m pytest tests/test_end_to_end.py -v
python -m pytest tests/services/test_login_flow.py -v
```

---

## 6. DOCUMENTAÇÃO ADICIONAL

* Para detalhes da auditoria e problemas corrigidos: [AUDITORIA.md](AUDITORIA.md)
* Para histórico de mudanças: [CHANGELOG.md](CHANGELOG.md)
* Para o guia de implantação na VPS e EasyPanel: [DEPLOYMENT.md](DEPLOYMENT.md)
