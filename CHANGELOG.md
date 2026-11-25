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
  - `wartune-reborne-emulator/test_full_chain.py`: Validação real cobrindo:
    1. Abertura do banco e verificação de tabelas;
    2. Cadastro e emissão de ticket no formato do Portal PHP;
    3. Inicialização dos serviços HTTP e TCP do emulador;
    4. Criptografia RSA do ticket e requisição HTTP `/login`;
    5. Ativação de personagem via HTTP `/visualizeregister` (respeitando limites de nickname);
    6. Handshake TCP 20001 com chave de sessão;
    7. Recebimento de `PlayerMsg` (opcode 3) e `LoginStateMsg` (opcode 6, state 0), autorizando a entrada no mundo.
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
