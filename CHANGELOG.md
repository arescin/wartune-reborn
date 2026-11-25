# CHANGELOG — WARTUNE REBORN

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

## [1.0.0] - 2026-11-25

### Adicionado
- **Auditoria Arquitetural Completa:** Criação do relatório `AUDITORIA.md` com diagnóstico detalhado dos 3 componentes (`CDN`, `Portal` e `Servidor`), matriz de criticidade de problemas e roadmap de execução.
- **Arquitetura Docker Modular:**
  - `docker/server/Dockerfile`: Imagem Python 3.12-slim com dependências do emulador e entrypoint inteligente que aguarda o banco e roda migrações automaticamente.
  - `docker/portal/Dockerfile` e `docker/portal/apache.conf`: Imagem PHP 8.2 Apache com extensões PDO (PostgreSQL, MySQL, SQLite) e cabeçalhos CORS liberados.
  - `docker/cdn/Dockerfile` e `docker/cdn/nginx.conf`: Nginx Alpine com suporte a CORS, tipos MIME especiais do Flash (`.swf`, `.bswf`, `.flv`, `.sq`, `.maps`) e roteamento para `/cdn/` e `/game/`.
  - `docker-compose.yml`: Orquestração completa para desenvolvimento e testes locais com PostgreSQL 16.
  - `docker-compose.prod.yml`: Orquestração voltada para produção e implantação no EasyPanel.
  - `.env.example`: Modelo centralizado e documentado de variáveis de ambiente.
- **Teste de Integração Real Ponta a Ponta:**
  - `wartune-reborne-emulator/test_full_chain.py`: Validação real local cobrindo banco, emissão de tickets, login RSA, ativação de herói e handshake TCP 20001 com entrada no mapa.
  - `wartune-reborne-emulator/test_live_vps.py`: Script de homologação em tempo real executado contra a VPS Hostinger (`179.198.96.49:5000` e `https://wartune-server.thnsdu.easypanel.host`), validando com 100% de sucesso:
    1. Obtenção do `config.xml` dinâmico e extração da chave pública RSA.
    2. Criação de conta e emissão de ticket via `POST /api/auth`.
    3. Criptografia RSA PKCS1v15 do ticket e login HTTP (`POST /login`).
    4. Ativação do personagem via `POST /visualizeregister` e avanço do tutorial (`noviceProcess`) via `/updateplayernovice`.
    5. Estabelecimento do socket TCP com `179.198.96.49:5000`.
    6. Envio do pacote 20001 (Handshake) com StreamCipher, recebimento de `PlayerMsg` (opcode 3), envio de `PlayerDataMsg` (opcode 8224) e confirmação de entrada no mapa com `LoginStateMsg` (opcode 6, state 0).
- **Implantação na VPS Hostinger / EasyPanel:**
  - Configurado o serviço `wartune-server` no projeto `bots` no EasyPanel em `thnsdu.easypanel.host`.
  - Mapeadas as portas públicas 5000 (TCP direto Flash) e 5001 (WebSocket bridge).
  - Configurado roteamento HTTPS Traefik para o domínio `wartune-server.thnsdu.easypanel.host`.
  - Validado carregamento do cliente web Ruffle e do Flash Projector Standalone Desktop.
- **Documentação de Implantação e Operação:**
  - `DEPLOYMENT.md`: Guia de arquitetura, portas públicas, volumes persistentes, configuração passo a passo no EasyPanel, rotinas de backup/restore e diagnóstico.
  - `README.md`: Visão geral do ecossistema, fluxo de inicialização e instruções de uso.

### Corrigido
- **Provisionamento de Templates no Servidor:**
  - Copiado o arquivo `tempinfos.xml` de `CDN/s134-bmclas-sq.7road.net/xml/tempinfos.xml` para `wartune-reborne-emulator/data/templates/tempinfos.xml`.
  - Resolvido o erro `FileNotFoundError` que causava a quebra de 458 testes unitários e impedia a subida do servidor.
- **Parametrização do Portal PHP:**
  - Refatorado `Wartune Reborn Portal v1/portal/config.php` para carregar valores dinamicamente a partir de variáveis de ambiente (`WARTUNE_DB_DSN`, `WARTUNE_PORTAL_URL`, `WARTUNE_CDN_URL`, `WARTUNE_GAME_URL`, `WARTUNE_GM_SECRET`, etc.) com fallbacks seguros para ambiente de desenvolvimento local.
  - Eliminados caminhos absolutos hardcoded do Windows (`sqlite:D:/wartune/servidor/...`) e referências a IPs locais estáticos.
- **Banco de Dados e Chaves RSA:**
  - Executadas com sucesso as 150 migrações Alembic e importados os 68.085 nós de templates no banco de dados.
  - Geração da chave RSA e registro do servidor `S1 - Local` na tabela `game_servers`.
