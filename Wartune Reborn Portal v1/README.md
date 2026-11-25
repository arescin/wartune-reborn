# Wartune Reborn: portal e CDN

Fica no Apache do XAMPP, em `http://127.0.0.1:8090/wartune-reborn/`. O servidor do jogo (Python)
está em `D:\wartune\servidor`.

| Pasta | O quê |
|---|---|
| `portal/` | cadastro e login (contas), lista de servidores, emissão do ticket, `config.xml` de cada servidor e a página de jogar (projector ou Ruffle) |
| `cdn/` | link para o espelho do CDN oficial inglês, `D:\xampp\htdocs\wartune\mirror\res134-bmclas-sq.7road.net` |
| `game/` | link para o espelho do site do jogo inglês (S134: `client/Loading.swf`, `resouececheck.sq`, `xml/`), `D:\xampp\htdocs\wartune\mirror\s134-bmclas-sq.7road.net` |
| `cdn-turco/` | legado: a sobreposição da CDN turca antiga, não é servida pelo portal |

## Configuração

Tudo fica em `portal/config.php`: banco (DSN), URL do portal, URL do CDN e validade do ticket.
O endereço, as portas e a chave RSA de cada servidor de jogo **não** são configurados aqui: vêm da
tabela `game_servers`, que cada processo do servidor preenche ao iniciar. Para ter vários servidores,
basta subir mais processos Python com outro `WARTUNE_SERVER_ID`; eles aparecem sozinhos na lista.

## Contrato com o servidor do jogo

| Tabela | Portal | Servidor do jogo |
|---|---|---|
| `accounts` | cria; guarda a senha com `password_hash` | só lê |
| `play_tickets` | cria um por "Jogar" (validade em `ticket_ttl`) | valida no `POST /login` |
| `game_servers` | só lê | publica host, portas e chave RSA |
| `characters` | lê; o painel GM edita `gold`, `point`, `gift_token`, `strategy`, `novice_process`, `grades` e apaga (reset), sempre depois do `POST /gm/kick` | cria e atualiza |
| `login_history` | grava `source='portal'` no login do portal; o painel GM lê | grava `source='game'` no `/login` e no 20001 |
| `cash_ledger` | grava edições GM (`reason='gm'`) e recargas (`'recharge'`) na mesma transação do UPDATE | grava o que o jogo dá/gasta (`'item'` no 5006...) |
| `item_log` | só lê | grava uso e ganho de itens (5006) |

Datas são gravadas em UTC (`Y-m-d H:i:s`). As tabelas são criadas pelo servidor do jogo.

## Painel GM (`portal/admin.php`)

Só para os usuários em `gm_users` (`config.php`). `gm_secret` tem de ser igual ao `WARTUNE_GM_SECRET`
do servidor. Rotas HTTP do servidor usadas (cabeçalho `X-GM-Secret`):

| Rota | Campos | Efeito |
|---|---|---|
| `POST /gm/kick` | `character_id` | derruba o personagem e espera a sessão gravar; 200 = pode editar o banco |
| `POST /gm/ban` | `account_id`, `banned` 0/1 | marca `accounts.banned`; ao banir derruba o personagem e invalida as chaves de login |

Conexão recusada = servidor fora do ar: o painel grava direto (no ban, só marca `accounts.banned`).
403, 404 (rota desligada sem segredo), timeout ou outro erro: a edição é recusada.

## Atualizar o CDN

O espelho é baixado por `D:\xampp\htdocs\wartune\download.php`. O que o cliente pediu e deu 404
no Apache: `cd D:\wartune\servidor; uv run python tools/fetch_missing.py`. Não rode o
`tools/build_cdn_overrides.py` contra `cdn/`: ele é da CDN turca e gravaria dentro do espelho.
