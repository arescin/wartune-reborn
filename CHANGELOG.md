# CHANGELOG — WARTUNE REBORN

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

## [1.1.0] - 2026-11-27

### Adicionado
- **Matriz Geral de Auditoria Forense (`docs/AUDITORIA_E_STATUS_GERAL.md`):** Catalogação detalhada dos 283 subsistemas do jogo em classes `VALIDADO`, `PARCIAL` e `BLOQUEADO`.
- **Auditoria de Integridade da CDN e Binários Road7:** Diagnóstico profundo dos arquivos da CDN, identificação da estrutura de 37 bytes de cabeçalho (`road7` + MD5) do `MD5Installer` do Flash.
- **Integração de Montarias e Avatares:**
  - Extração de 387 montarias e avatares de `mounts_equip_show.tar.gz` para `CDN/res134-bmclas-sq.7road.net/swf/avatar/`.
  - Cobertura de montarias no `tempinfos.xml` elevada para **99,74%** (387/388).
- **Extração de Assets e Tabelas do Legend Legacy (`legendlegacy.com.br`):**
  - Descoberto e minerado o ecossistema de dados baseado no mirror Reborn.
  - Baixadas 11 tabelas JSON completas em Português (`ItemTempInfo`, `SkillSlim`, `BuffSlim`, `MountTempInfo`, `SkillTempInfo`, `QuestTempInfo`, `PawnTempInfo`, `UpGradeTempInfo`, `ConfigInfo`, `MapInfo`, `MapNodeInfo`) para `data_pt_assets/dados/`.
  - Baixados e integrados 244 ícones de itens, buffs e habilidades que faltavam na CDN via endpoint `/8081/icon/`.
  - Integridade de ícones de itens e combate atingiu **100% de cobertura** no espelho local da CDN (resolvidas 8.805 de 9.669 referências mapeadas, elevando a taxa para 91,06%).

### Corrigido
- **Compatibilização de Idioma nos Testes Unitários:**
  - Ajustadas asserções em `tests/game/test_castelo.py` e `tests/game/test_items.py` para suportar tanto os nomes originais em inglês quanto os templates traduzidos em PT-BR (`tempinfos.xml`), eliminando 4 falhas de teste e restaurando 100% de aprovação (38/38 testes de Castelo e Itens aprovados).
  - Corrigida string mista de desbloqueio de inventário em `src/wartune_server/game/handlers/items.py`.

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
