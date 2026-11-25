# Debug E2E Deployment

Status: [OPEN]

## Objetivo
Diagnosticar e corrigir o fluxo completo do Wartune Reborn: Portal v1, PostgreSQL, CDN, servidor HTTP, WebSocket, TCP e Flash Policy.

## Hipóteses
1. O Portal retorna 502 por falha de inicialização ou conexão PostgreSQL.
2. O servidor retorna 502 por falha no boot, migrations, template ou configuração.
3. A CDN retorna 404 porque os assets ou o `default.conf` não estão disponíveis no container.
4. As portas públicas estão configuradas, mas os processos não estão escutando ou o roteamento está incorreto.
5. URLs públicas, registro em `game_servers` ou fluxo de autenticação estão inconsistentes.

## Evidências pré-correção
- Portal: o domínio raiz retornava `502`/erro de disponibilidade.
- Servidor: o domínio HTTP retornava `404` quando consultado na rota `/`, e o domínio esperado não expunha a porta HTTP `8080`.
- CDN: os endpoints de integridade e assets retornavam `404` antes da configuração/mount corretos.
- As portas TCP públicas `5000`, `5001` e `843` estavam acessíveis durante a validação.
- O PostgreSQL `bots/wartune-db` estava habilitado e configurado como PostgreSQL 16.

## Correções
- Confirmada a origem do Portal v1 no commit `88067cf`.
- Corrigido o Portal para aceitar `WARTUNE_SERVER_HTTP_URL`, permitindo apontar `REQUEST_PATH` para o domínio público HTTP do servidor em vez de montar `http://host:8080` diretamente.
- Configurado `WARTUNE_SERVER_HTTP_URL=https://bots-wartune-http.thnsdu.easypanel.host/` no serviço `wartune-portal`.
- Configurado `WARTUNE_WS_URL=wss://bots-wartune-ws.thnsdu.easypanel.host/` no Portal.
- Criado o domínio EasyPanel `bots-wartune-http.thnsdu.easypanel.host` direcionado para `wartune-server:8080`.
- Confirmada a CDN com `/healthz`, `/crossdomain.xml`, `Loading.swf` e `tempinfos.xml` respondendo corretamente.

## Verificação pós-correção
- Portal raiz: `200`, redirecionando para `/portal/`.
- Portal `/portal/`: `200 text/html`.
- Servidor `/crossdomain.xml`: `200 text/xml`.
- Servidor `/loginselectlist`: `200 text/xml`.
- CDN `/healthz`: `200 text/plain`.
- CDN `/game/client/Loading.swf`: `200 application/x-shockwave-flash`.
- CDN `/game/xml/tempinfos.xml`: `200 text/xml`.
- Portas TCP do servidor: `5000`, `5001` e `843` acessíveis externamente.
- O fluxo de cadastro/login real e a batalha tutorial ainda dependem de credenciais de teste e execução efetiva do cliente Flash/Ruffle; não foram declarados como validados apenas por testes HTTP.
