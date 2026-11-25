# RELATÓRIO DE AUDITORIA COMPLETA — WARTUNE REBORN

**Data da Auditoria:** 25/11/2026  
**Ambiente de Inspeção:** Windows (Ambiente de Desenvolvimento)  
**Alvo Final de Implantação:** VPS Hostinger com EasyPanel (Docker)  
**Escopo Auditado:** Componentes `CDN`, `Wartune Reborn Portal v1` (Portal) e `wartune-reborne-emulator` (Servidor).

---

## 1. RESUMO EXECUTIVO

O projeto **Wartune Reborn** é composto por uma arquitetura tripartite para execução do emulador do jogo *Legend Online / Wartune* (versão cliente Flash 7Road):

1. **CDN / Assets do Jogo:** Conjunto de ~9,83 GB e 38.237 arquivos espelhados do oficial (S134).
2. **Portal Web (PHP):** Aplicação PHP 8.1+ para gestão de contas, autenticação, emissão de tickets de entrada (`play_tickets`), geração dinâmica de `config.xml` do cliente e painel administrativo (GM).
3. **Servidor do Jogo (Python):** Backend assíncrono em Python 3.12+ (`asyncio`), responsável pelo ciclo de vida do jogo, persistência (SQLAlchemy 2 com 150 migrações Alembic), endpoints HTTP do cliente (`REQUEST_PATH`), socket TCP do jogo (porta 5000), socket proxy WebSocket para Ruffle (porta 5001) e Flash Policy Server (porta 843).

O código possui um nível avançado de modelagem, separação de camadas e testes, porém apresenta **pontos críticos de bloqueio** que impedem o funcionamento imediato sem a devida integração: arquivos de templates ausentes na pasta de execução do servidor, dependências de caminhos hardcoded no Windows/XAMPP no portal, ausência de conteinerização Docker e repositório Git desestruturado.

---

## 2. ESTADO DETALHADO DE CADA COMPONENTE

### 2.1. CDN (`CDN/`)
* **Volume de dados:** 38.237 arquivos | 9.830,11 MB (~9,83 GB).
* **Distribuição de extensões principais:**
  * `.swf`: 15.050 arquivos (módulos Flash de interface, efeitos, montarias, heróis);
  * `.bswf`: 14.822 arquivos (avatares e modelos de equipamentos/montarias);
  * `.png`: 7.348 arquivos (ícones, texturas, sprites, layouts, códigos desembaralhados `2.png` a `18.png`);
  * `.jpg`: 432 arquivos;
  * `.maps` / `.titles`: 248 arquivos cada (dados de mapas e títulos da cidade externa);
  * `.xml`: 19 arquivos;
  * `.flv`: 43 arquivos (músicas de fundo e áudios);
  * `.sq`: 1 arquivo (`resouececheck.sq`).
* **Estrutura interna:**
  * `res134-bmclas-sq.7road.net/`: Fonte dos assets de interface, mapas, sons, avatares, equipamentos e módulos de código. Corresponde à URL `ResourcePath` do `config.xml`.
  * `s134-bmclas-sq.7road.net/`: Arquivos centrais do loader do jogo (`client/Loading.swf`, `client/resouececheck.sq`, `xml/tempinfos.xml` [938 KB], `xml/version.xml`). Corresponde ao `TEMPLATE_PATH` e local de carregamento do cliente.
  * Raiz de `CDN/`: Contém scripts de espelhamento legados (`download.php`, `config.php`, `MAPA_URLS.md`).
* **Estado:** Os arquivos fundamentais para inicialização do cliente Flash estão **completos e presentes**.

### 2.2. Portal (`Wartune Reborn Portal v1/`)
* **Volume:** 112 arquivos | 0,15 MB.
* **Stack:** PHP 8.1+ com tipagem estrita (`declare(strict_types=1)`), PDO, HTML5, CSS3, Ruffle (WebAssembly Flash Player).
* **Estrutura interna:**
  * `index.php` (raiz da pasta): Redireciona para `portal/`.
  * `portal/config.php`: Arquivo central de configurações.
  * `portal/index.php`: Login, registro e seleção de servidor.
  * `portal/play.php`: Tela do jogo (gera flashvars, link para Flash Projector e inicializador do Ruffle).
  * `portal/client-config.php`: Endpoint público que gera o `config.xml` em tempo real para o `Loading.swf`.
  * `portal/admin.php`: Painel de GM (kick, ban, recargas, resets).
  * `portal/src/`: Classes de domínio (`Accounts.php`, `Tickets.php`, `GameServers.php`, `ClientConfig.php`, `Database.php`, `Admin.php`).
* **Estado:** Código bem estruturado e seguro, porém **inoperante em ambiente externo/Docker** devido a caminhos absolutos locais do Windows (`sqlite:D:/wartune/servidor/...`) e URLs com IPs locais fixos (`127.0.0.1:8090`).

### 2.3. Servidor do Jogo (`wartune-reborne-emulator/`)
* **Volume:** 554 arquivos | 10,27 MB.
* **Stack:** Python 3.12+ com `asyncio`, `aiohttp` 3.14+, `sqlalchemy` 2.0+, `alembic` 1.20+, `cryptography` 50+, `protobuf` 7.36+, `pydantic-settings` 2.16+, `structlog` 26+.
* **Bancos suportados:** SQLite (`sqlite+aiosqlite`), PostgreSQL (`postgresql+asyncpg`), MySQL/MariaDB (`mysql+asyncmy`).
* **Estrutura de portas:**
  * `8080`: HTTP do jogo (`REQUEST_PATH`: rotas `/login`, `/visualizeregister`, `/updateplayernovice`, `/crossdomain.xml`, etc.).
  * `5000`: Socket TCP principal do jogo (mensagens codificadas em Protobuf com cifra de fluxo Wartune) e resposta a Flash Policy XML.
  * `5001`: WebSocket bridge para conexões via navegador usando o emulador Ruffle (`socketProxy`).
  * `843`: Policy server dedicado para Flash Player.
* **Estado:** Código altamente avançado com 1012 testes automatizados. Contudo, **falha imediatamente ao inicializar** porque o arquivo de dados `data/templates/tempinfos.xml` não está presente na pasta `data/templates/`, ocasionando `FileNotFoundError` em 458 testes e na subida do servidor.

---

## 3. PROBLEMAS ENCONTRADOS CLASSIFICADOS POR CRITICIDADE

### Criticidade: CRÍTICA (Bloqueia inicialização e conexão)

| ID | Componente | Problema | Impacto |
|---|---|---|---|
| **C-01** | Servidor | Arquivo `tempinfos.xml` ausente em `wartune-reborne-emulator/data/templates/tempinfos.xml`. | O servidor Python não sobe e falha em 458 testes unitários e de integração com `FileNotFoundError: data/templates/tempinfos.xml`. |
| **C-02** | Portal | Configurações hardcoded no arquivo `portal/config.php` (`dsn` apontando para `sqlite:D:/wartune/servidor/data/wartune.db` e URLs `127.0.0.1:8090`). | O portal não conecta ao banco de dados em Linux/Docker e gera URLs inválidas para o cliente do jogo. |
| **C-03** | CDN / Web | Ausência de servidor web configurado para rotear os dois diretórios do CDN (`res134-bmclas-sq.7road.net` e `s134-bmclas-sq.7road.net`) com suporte a CORS e MIME types para `.swf`, `.bswf`, `.xml`, `.sq`. | O Flash Player bloqueia o carregamento dos assets e não localiza `Loading.swf`, `tempinfos.xml` e módulos visuais. |
| **C-04** | Integração | Ausência de inicialização inicial do banco de dados (tabelas e templates). | Sem a execução das migrações Alembic e o cadastro da linha do servidor em `game_servers`, o portal exibe "Nenhum servidor publicado ainda" e não emite tickets. |

### Criticidade: ALTA (Bloqueia conteinerização e implantação)

| ID | Componente | Problema | Impacto |
|---|---|---|---|
| **A-01** | Arquitetura | Inexistência de arquivos Docker (`Dockerfile`, `docker-compose.yml`, scripts de entrypoint, healthchecks). | Impossibilita o deploy automatizado e modular no EasyPanel na VPS Hostinger. |
| **A-02** | Banco de Dados | Em ambiente multi-container, o uso de SQLite através de bind mount compartilhado pode gerar concorrência de I/O e locks de arquivo entre PHP e Python. | Risco de corrupção ou travamento de banco sob acessos simultâneos no portal e no jogo. O emulador suporta nativamente PostgreSQL, sendo esta a solução arquitetural recomendada. |
| **A-03** | Versionamento | Repositório Git inexistente na raiz do projeto. Pasta `Wartune Reborn Portal v1` possui um `.git` isolado de histórico antigo. | Código desorganizado e sem controle de versão centralizado. |
| **A-04** | Nomenclatura | Nomes de diretórios heterogêneos (`CDN`, `Wartune Reborn Portal v1`, `wartune-reborne-emulator`). | Quebra padrões convencionais de scripts e pipelines CI/CD. |

### Criticidade: MÉDIA (Operacional e Segurança)

| ID | Componente | Problema | Impacto |
|---|---|---|---|
| **M-01** | Repositório | Volume de assets do CDN (~9,83 GB) não pode ser versionado no Git comum. | Pode exceder limites do Git remoto (GitHub, GitLab, etc.). O Git deve conter código e templates essenciais, e a CDN deve ser gerenciada via volume persistente ou storage. |
| **M-02** | Segurança | Segredo do painel GM (`WARTUNE_GM_SECRET` e `gm_secret`) vazio por padrão. | Rotas de moderação `/gm/kick` e `/gm/ban` permanecem inativas ou vulneráveis se configuradas de forma insegura. |
| **M-03** | Rede / Portas | Portas 5000 (TCP), 5001 (WS), 8080 (HTTP) e 843 (Policy) precisam de roteamento público direto na VPS, pois o cliente Flash comunica-se via TCP puro. | O EasyPanel por padrão roteia apenas tráfego HTTP reverso via Traefik. Portas TCP (5000/5001) precisam ser expostas diretamente no host da VPS. |

### Criticidade: BAIXA (Refinamento e Conveniência)

| ID | Componente | Problema | Impacto |
|---|---|---|---|
| **B-01** | Portal | Dependência externa de CDN unpkg para o script `ruffle.js`. | Caso o unpkg fique fora do ar ou haja indisponibilidade de internet externa, o Ruffle falha no navegador. |
| **B-02** | Servidor | Chave RSA gerada sob demanda em `data/rsa_private.pem`. | Se o volume não for persistido entre deploys de containers, uma nova chave será gerada, invalidando sessões ativas. |

---

## 4. DEPENDÊNCIAS EXTERNAS E AMBIENTE

1. **Python:** 3.12 ou 3.13 com ferramentas de empacotamento (`uv` ou `pip`).
2. **PHP:** 8.1, 8.2 ou 8.3 com extensões `pdo`, `pdo_pgsql` (ou `pdo_sqlite`/`pdo_mysql`), `openssl`, `session`, `json`, `mbstring`.
3. **Servidor Web:** Nginx com suporte a HTTP/2, WebSocket upstream e headers CORS.
4. **Banco de Dados:** PostgreSQL 16 (ou SQLite para dev local).
5. **Cliente Flash:**
   * Flash Player Projector oficial (modo desktop, conectando via TCP porta 5000); ou
   * Ruffle WebAssembly (modo navegador web, conectando via WebSocket porta 5001).

---

## 5. ARQUIVOS AUSENTES OU REQUERIDOS

1. `wartune-reborne-emulator/data/templates/tempinfos.xml`: Necessário copiar ou linkar de `CDN/s134-bmclas-sq.7road.net/xml/tempinfos.xml`.
2. `.env`: Arquivo de variáveis de ambiente do servidor Python (baseado em `.env.example`).
3. `portal/config.php` adaptável a variáveis de ambiente (`getenv`).
4. `Dockerfile` para `wartune-server`.
5. `Dockerfile` para `wartune-portal`.
6. Configuração do `nginx` para `wartune-cdn`.
7. `docker-compose.yml` para orquestração unificada local e produção.
8. `.gitignore` centralizado e higienizado para o repositório raiz.

---

## 6. LIMITAÇÕES CONHECIDAS DO EMULADOR (CONFORME `docs/progresso.md`)

* **Cobertura de Sistemas:** 123 sistemas 100% implementados com fontes do oficial inglês, 59 parciais, 95 funcionais com fórmulas deduzidas/calibradas, 11 sem implementação.
* **Tutorial:** Se `WARTUNE_SKIP_TUTORIAL=true`, o jogador pula o tutorial inicial e inicia direto na cena do castelo (`noviceProcess >= 19000`). Se for `false`, o fluxo do tutorial ocorre conforme scripts capturados.
* **Rankings:** Gravados sob demanda e a cada 1 hora se `WARTUNE_RANKING_XML_DIR` estiver configurado.
* **Batalhas e Masmorras:** Sistemas essenciais operacionais, combate por turnos sincronizado.

---

## 7. PLANO DE EXECUÇÃO DETALHADO (PRÓXIMAS ETAPAS)

### FASE 1: Correções Imediatas e Unificação Local (Etapa D)
1. **Provisionamento do `tempinfos.xml`:**
   * Copiar com validação o arquivo `CDN/s134-bmclas-sq.7road.net/xml/tempinfos.xml` para `wartune-reborne-emulator/data/templates/tempinfos.xml`.
   * Reexecutar os testes unitários do Python para comprovar a resolução do `FileNotFoundError`.
2. **Parametrização do Portal PHP:**
   * Refatorar `Wartune Reborn Portal v1/portal/config.php` para aceitar variáveis de ambiente (`getenv`) com fallbacks seguros, permitindo configurar `DB_DSN`, `DB_USER`, `DB_PASS`, `PORTAL_URL`, `CDN_URL`, `GAME_URL`, `GM_SECRET` dinamicamente tanto em desenvolvimento quanto em produção no EasyPanel.
3. **Inicialização do Banco e Importação de Templates:**
   * Executar a rotina de criação de tabelas (`migrate`) e importação de templates no banco.

### FASE 2: Arquitetura Docker e Redes (Etapa E)
1. **Criação dos Dockerfiles:**
   * `server.Dockerfile`: Python 3.12-slim com dependências instaladas via `pip`/`uv`, expondo 8080 (HTTP), 5000 (TCP), 5001 (WS) e 843 (Policy).
   * `portal.Dockerfile`: PHP 8.2-fpm/apache com extensões PDO (pgsql/sqlite/mysql).
   * `cdn.Dockerfile` / Nginx config: Servidor de alta performance servindo os diretórios estáticos com cabeçalhos CORS e MIME types adequados.
2. **Orquestração `docker-compose.yml`:**
   * Serviços isolados: `wartune-db` (Postgres 16), `wartune-server`, `wartune-portal`, `wartune-cdn`.
   * Configuração de redes internas (`wartune-net`) e mapeamento das portas públicas.

### FASE 3: Testes de Integração e Validação Funcional (Etapa F)
1. Teste de subida de containers.
2. Teste de disponibilidade HTTP do portal e CDN (retorno 200 OK em `Loading.swf` e `tempinfos.xml`).
3. Teste de registro de conta no portal e gravação no banco.
4. Teste de login e emissão de ticket (`play_tickets`).
5. Teste de carregamento do `client-config.php?server=1` (validação do `config.xml`).
6. Teste de requisição de login HTTP no emulador (`/login`).
7. Teste de conexão de socket TCP / WebSocket no emulador.

### FASE 4: Repositório Git e Preparação para VPS/EasyPanel (Etapas G a K)
1. Higienização de arquivos (ignorar binários temporários, `.env`, logs).
2. Criação de documentações `README.md`, `DEPLOYMENT.md`, `CHANGELOG.md`.
3. Validação prévia de publicação e solicitação de autorização do usuário antes de qualquer ação no Git remoto ou VPS.
