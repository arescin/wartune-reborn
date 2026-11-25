# GUIA DE IMPLANTAÇÃO E OPERAÇÃO (DEPLOYMENT) — WARTUNE REBORN

Este documento é o manual oficial de infraestrutura, arquitetura, segurança e implantação do **Wartune Reborn** em VPS (Hostinger) utilizando Docker e EasyPanel.

---

## 1. ARQUITETURA DE SERVIÇOS

O ecossistema é dividido em 4 serviços desacoplados operando em rede Docker interna (`wartune-net`):

```
                        Navegador / Flash Player Projector
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │ HTTP :80 (HTTPS 443)       │ HTTP :8081                 │ TCP :5000 (Jogo)
           │ (Traefik / EasyPanel)      │ (Traefik / EasyPanel)      │ WS  :5001 (Ruffle)
           ▼                            ▼                            ▼
  ┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
  │ wartune-portal  │          │   wartune-cdn   │          │ wartune-server  │
  │  (PHP 8.2 +     │          │  (Nginx Alpine) │          │  (Python 3.12   │
  │     Apache)     │          │                 │          │   + asyncio)    │
  └────────┬────────┘          └─────────────────┘          └────────┬────────┘
           │                                                         │
           │                     Rede Docker                         │
           └───────────────────────────┬─────────────────────────────┘
                                       ▼
                              ┌─────────────────┐
                              │   wartune-db    │
                              │ (PostgreSQL 16) │
                              └─────────────────┘
```

---

## 2. PORTAS E PROTOCOLOS DE REDE

| Serviço | Porta do Container | Porta do Host | Protocolo | Exposição Pública | Finalidade |
|---|---|---|---|---|---|
| `wartune-portal` | 80 | 8090 (ou 80 via Traefik) | HTTP / HTTPS | Sim (Domínio) | Portal de contas, login, tickets e admin GM |
| `wartune-cdn` | 80 | 8081 (ou 80 via Traefik) | HTTP / HTTPS | Sim (Subdomínio) | Assets estáticos (SWFs, imagens, XMLs) |
| `wartune-server` | 8080 | 8080 | HTTP / HTTPS | Sim (Domínio/IP) | `REQUEST_PATH`: Endpoints dinâmicos do Flash |
| `wartune-server` | 5000 | 5000 | TCP puro | **Sim (Direta no Host)** | Socket principal do jogo (Flash Player) |
| `wartune-server` | 5001 | 5001 | TCP / WebSocket | **Sim (Direta no Host)** | Ponte WebSocket para jogar no navegador (Ruffle) |
| `wartune-server` | 843 | 843 | TCP puro | Opcional | Flash Policy Server dedicado |
| `wartune-db` | 5432 | Nenhuma | TCP | **Não (Apenas interna)** | Banco de dados relacional compartilhado |

> [!IMPORTANT]
> **Atenção sobre Portas no EasyPanel:**  
> O EasyPanel gerencia proxies HTTP/HTTPS na porta 80/443 via Traefik.  
> As portas **5000 (TCP)** e **5001 (WebSocket/TCP)** são sockets binários do cliente Flash e **NÃO** podem passar pelo proxy HTTP comum. Elas precisam ser mapeadas diretamente como **Portas Públicas no Host** nas configurações do serviço `wartune-server` no EasyPanel ou no Firewall da VPS.

---

## 3. DOMÍNIOS E SUBDOMÍNIOS RECOMENDADOS

* **Portal:** `https://portal.seudominio.com` (apontando para o serviço `wartune-portal`)
* **CDN / Assets:** `https://cdn.seudominio.com` (apontando para o serviço `wartune-cdn`)
* **Servidor HTTP do Jogo:** `http://game.seudominio.com:8080` (apontando para `wartune-server:8080`)
* **Host de Conexão TCP:** `game.seudominio.com` ou o IP público da VPS (porta 5000)

---

## 4. VOLUMES PERSISTENTES

1. `wartune_db_data`: Armazena todos os dados das contas, personagens, heróis, itens, guildas e progresso (`/var/lib/postgresql/data`).
2. `wartune_server_data`: Armazena a chave RSA privada persistente `rsa_private.pem`, templates e arquivos de dados (`/app/data`).
3. `wartune_server_logs`: Armazena logs de pacotes e depuração (`/app/logs`).
4. Volume da CDN: A pasta de assets (~9,83 GB) deve ser montada como volume de leitura no container `wartune-cdn`:
   * `/usr/share/nginx/html/res134-bmclas-sq.7road.net`
   * `/usr/share/nginx/html/s134-bmclas-sq.7road.net`

---

## 5. VARIÁVEIS DE AMBIENTE (ENV)

Configuração central no `.env`:

```env
# Host público para o cliente Flash conectar (IP ou DNS sem protocolo e sem porta)
WARTUNE_PUBLIC_HOST=123.45.67.89

# URLs com protocolo e barra final
WARTUNE_PORTAL_URL=https://portal.seudominio.com/portal/
WARTUNE_CDN_URL=https://cdn.seudominio.com/cdn/
WARTUNE_GAME_URL=https://cdn.seudominio.com/game/

# Banco de dados
POSTGRES_DB=wartune
POSTGRES_USER=wartune
POSTGRES_PASSWORD=gere_uma_senha_forte_aqui

# Servidor do jogo
WARTUNE_SERVER_ID=1
WARTUNE_SERVER_NAME=S1 - Wartune Reborn
WARTUNE_SITE=local_0001
WARTUNE_GAME_TIMEZONE=UTC
WARTUNE_SKIP_TUTORIAL=false

# Segurança
WARTUNE_GM_SECRET=segredo_exclusivo_do_painel_gm
WARTUNE_GM_USERS=admin
```

---

## 6. INSTÂNCIA ATIVA NA VPS HOSTINGER (EASYPANEL)

A implantação em produção foi concluída e validada na VPS Hostinger com EasyPanel:

* **VPS IP:** `179.198.96.49`
* **Domínio EasyPanel:** `thnsdu.easypanel.host`
* **Projeto EasyPanel:** `bots`
* **Serviço Principal:** `wartune-server` (Container ativo consumindo ~453 MB RAM, Python 3.12 asyncio)
* **URL do Portal / Web Player:** `https://wartune-server.thnsdu.easypanel.host/`
* **Página de Jogo (Web Ruffle):** `https://wartune-server.thnsdu.easypanel.host/play?user=NOME_DO_JOGADOR`
* **Link Direto Flash Projector (Desktop):** `https://wartune-server.thnsdu.easypanel.host/projector?user=NOME_DO_JOGADOR`
* **Configuração do Cliente (`config.xml`):** `https://wartune-server.thnsdu.easypanel.host/config.xml`
* **Socket TCP Principal (Flash):** `179.198.96.49:5000` (Porta direta do host aberta e validada)
* **Ponte WebSocket (WSS):** `wss://wartune-server.thnsdu.easypanel.host/ws` (compatível com navegadores modernos)
* **Assets CDN (SWFs / XMLs / Imagens):** `https://wartune-server.thnsdu.easypanel.host/cdn/...`

### Evidência de Homologação Ponta a Ponta (`test_live_vps.py`)

O script de integração de ponta a ponta executou com 100% de sucesso contra a infraestrutura ativa na VPS Hostinger:
1. Extração da chave pública RSA do `config.xml` dinâmico.
2. Emissão de ticket de acesso via `/api/auth`.
3. Criptografia RSA do ticket e aprovação do login HTTP (`/login`).
4. Ativação do herói via `/visualizeregister`.
5. Conexão TCP ao socket `179.198.96.49:5000`.
6. Envio de pacote 20001, recebimento de `PlayerMsg` (opcode 3) e confirmação de entrada no mapa com `LoginStateMsg` (opcode 6, state 0).

---

## 7. IMPLANTAÇÃO PASSO A PASSO NO EASYPANEL

### Método 1: Via Docker Compose (Recomendado)

1. No EasyPanel, crie um novo Projeto chamado `wartune-reborn`.
2. Adicione um serviço do tipo **Docker Compose**.
3. No campo Compose File, utilize o arquivo `docker-compose.prod.yml`.
4. Na aba **Environment**, insira as variáveis de ambiente baseadas no `.env.example`.
5. Garanta que o volume de arquivos da CDN esteja presente no disco da VPS no caminho indicado no compose (ex: `/var/data/wartune/CDN`).
6. Clique em **Deploy**. O entrypoint do `wartune-server` aguardará o banco, executará as migrações automaticamente e subirá o emulador.

### Método 2: Via Serviços Separados no EasyPanel

Caso prefira gerenciar cada container individualmente na interface do EasyPanel:

1. **Serviço 1 — Banco de Dados:**
   * Crie um serviço **PostgreSQL** (1 clique no EasyPanel).
   * Anote a senha gerada e o host interno (ex: `postgres:5432`).
2. **Serviço 2 — Servidor Python (`wartune-server`):**
   * Tipo: **App** (Build from Git ou Dockerfile `docker/server/Dockerfile`).
   * Portas:
     * Expor porta 8080 (HTTP).
     * Mapear porta pública 5000 no host (TCP) e 5001 (WS).
   * Montar volumes para `/app/data` e `/app/logs`.
   * Configurar `WARTUNE_DATABASE_URL=postgresql+asyncpg://wartune:senha@postgres:5432/wartune`.
3. **Serviço 3 — Portal PHP (`wartune-portal`):**
   * Tipo: **App** (Dockerfile `docker/portal/Dockerfile`).
   * Configurar domínio (ex: `portal.seudominio.com`).
   * Configurar as variáveis `WARTUNE_DB_*` apontando para o banco.
4. **Serviço 4 — CDN (`wartune-cdn`):**
   * Tipo: **App** (Dockerfile `docker/cdn/Dockerfile`).
   * Configurar subdomínio (ex: `cdn.seudominio.com`).
   * Montar pasta da CDN da VPS nos diretórios correspondentes.

---

## 7. ROTINAS DE MANUTENÇÃO E OPERAÇÃO

### Como consultar logs
```bash
docker logs -f wartune-server
docker logs -f wartune-portal
docker logs -f wartune-cdn
```

### Como reiniciar os serviços
```bash
docker compose restart wartune-server
```

### Backup do Banco de Dados
```bash
# Executar dump do PostgreSQL
docker exec -t wartune-db pg_dump -U wartune wartune > /backups/wartune_$(date +%Y%m%d_%H%M%S).sql
```

### Restauração do Banco de Dados
```bash
cat backup.sql | docker exec -i wartune-db psql -U wartune -d wartune
```

### Como Atualizar o Projeto pelo Git
```bash
git pull origin main
docker compose build wartune-server wartune-portal
docker compose up -d
```

---

## 8. DIAGNÓSTICO DE FALHAS COMUNS

1. **"Nenhum servidor publicado ainda" no Portal:**
   * Causa: O processo do `wartune-server` ainda não subiu ou não conseguiu conectar ao banco para registrar o servidor em `game_servers`.
   * Solução: Verifique `docker logs wartune-server`. Certifique-se de que o PostgreSQL está saudável.

2. **O jogo trava na tela de carregamento (Loading.swf 0% ou tela preta):**
   * Causa: A URL do `config.xml` (`client-config.php`) retornou 404 ou o arquivo `tempinfos.xml` / `language.txt` deu erro na CDN.
   * Solução: Abra a aba Network do navegador (F12) e inspecione as requisições com status 404 ou CORS bloqueado.

3. **"Conexão recusada" ao entrar no jogo após criar o herói:**
   * Causa: O Flash Player tentou conectar na porta 5000 do host, mas a porta está fechada no firewall da VPS ou não foi exposta no EasyPanel.
   * Solução: Libere a porta 5000 TCP no firewall da Hostinger/UFW (`sudo ufw allow 5000/tcp`).
