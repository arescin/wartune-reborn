# Auditoria e correções — tutorial e assets

## Escopo

A investigação compara o emulador com a base auxiliar `G:\projects\legend-online-main`, concentrando-se no tutorial, movimentação de campanha, entrada em batalha e assets Flash.

## Conclusões confirmadas

- `5124` (`U_C_CAMPAIGN_SYNCPOS`) é enviado pelo cliente sem resposta direta do servidor. Ele sincroniza a rota já calculada localmente pelo cliente.
- `5125` (`U_C_CAMPAIGN_ARRIVE`) é o pacote de chegada ao nó e pode iniciar a batalha quando o nó e o estado do tutorial correspondem.
- A base auxiliar documenta a cena de campanha no módulo `m3` e a cena de batalha no módulo `m10`.
- `legend-online-main` não contém `maps/10002/10002.maps` nem `maps/10002/10002.titles`; a própria documentação registra o mapa 10002 como não baixado. Portanto, não há malha de navegação comprovada para copiar dessa base.
- O script `tools/repack_tempinfos.py` do emulador injeta `MapInfo.Id="10001"` com `MapFileId="10002"`. Assim, `10001` é o identificador lógico usado pelo servidor, enquanto `10002` é o recurso físico referenciado. Não foi feita troca de IDs.
- `2.core.swf` da base auxiliar e do emulador possui o mesmo tamanho e o mesmo SHA-256, portanto não precisava ser substituído.

## Complementos aplicados

Foram adicionados à CDN local:

- `bundled_cdn/m3.swf`: módulo da cena de campanha, copiado de `legend-online-main/modules_src/m3.swf`.
- `bundled_cdn/m10.swf`: módulo da cena de batalha, copiado de `legend-online-main/modules_src/m10.swf`.

Os hashes foram verificados após a cópia:

- `m3.swf`: `81E526670978D67DC139288DE7D50E6980B77CBC7CFD2AD516D86F6A2E1EAB77`
- `m10.swf`: `8AA767BFDE13F62A71241EDC8DBD6F1095F0EC09DA0E65DC2161CB688E9D613E`

Nenhum mapa, malha ou protocolo foi inventado ou substituído.

## Áudio e CDN

`/config.xml` deixou de anunciar `audio.swf` e `sounds/` quando esses recursos não existem localmente. O objetivo é evitar que o cliente tente decodificar MP3s ausentes/truncados. Assets ausentes continuam retornando 404 e são registrados no log; não há fallback PNG ou áudio falso.

## Validação

Executado:

```text
PYTHONPATH=src python -m pytest tests/http/test_portal.py tests/game/test_tutorial.py -q
8 passed
```

O teste oficial baseado em captura permanece condicionado à existência da captura externa, que não está disponível nesta máquina.

## Limitações restantes

- A base auxiliar não fornece os arquivos `.maps`/`.titles` do tutorial 10002; a malha ainda precisa vir do CDN oficial, de outra captura ou de uma fonte local compatível.
- A compatibilidade funcional dos módulos só pode ser confirmada no cliente Ruffle, observando carregamento da campanha e a cadeia `5124 → 5125 → 157 → 10007 → 156/153`.
- Não foram copiados indiscriminadamente os 12,73 GB da base auxiliar.
