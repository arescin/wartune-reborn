# MATRIZ DE AUDITORIA FORENSE E STATUS GERAL DOS SISTEMAS — WARTUNE REBORN

**Data de Atualização:** 27/11/2026  
**Status da Auditoria:** Ciclo 1 Concluído com Sucesso — Expansão de Assets e Resolução de CDN Concluída  
**Classificações:**
- **VALIDADO:** Comportamento confirmado por evidência e teste funcional/integração.
- **PARCIAL:** Existe implementação sólida, porém com valores estimados (`TODO(inventado)`) ou partes que recusam.
- **BLOQUEADO:** Depende de captura ausente, arquivos inexistentes ou APIs externas descontinuadas.

---

## 1. RESUMO EXECUTIVO DE COBERTURA

| Categoria | Total de Sistemas | VALIDADO | PARCIAL | BLOQUEADO | Fonte Principal |
|---|---:|---:|---:|---:|---|
| **Validação, Base e Protocolo** | 4 | 2 | 2 | 0 | Capturas EN, Replays, Protocolo Protobuf |
| **Castelo e Prédios** | 20 | 14 | 6 | 0 | Capturas oficiais EN/TR e AS3 decompilado |
| **Herói e Exército** | 29 | 15 | 13 | 1 | Captura de maga novata e tabelas oficiais |
| **Pets e Mascotes (Sylph)** | 11 | 5 | 5 | 1 | Capturas TR e AS3 de batalha |
| **Itens, Mochila e Forja** | 27 | 15 | 12 | 0 | Capturas EN e m2/m6 ActionScript |
| **Lojas e Mercado** | 12 | 8 | 4 | 0 | Capturas e regras de leilão |
| **Chat e Social** | 12 | 6 | 6 | 0 | AS3 e pacotes de amigos/casamento |
| **Clã / Guilda** | 21 | 10 | 11 | 0 | m6 Consortia e captura 171155 |
| **Campanhas e Masmorras** | 24 | 8 | 15 | 1 | Captura EN e MapPhysicsTempInfos |
| **Labirinto (Catacumbas)** | 10 | 4 | 6 | 0 | Capturas oficiais TR e regras de andares |
| **Batalha e Fórmulas de RPG** | 14 | 7 | 6 | 1 | Capturas EN, fórmulas calibradas |
| **Missões e Quests** | 21 | 14 | 4 | 3 | QuestTemps, QuestCondictionInfos, EN #81 |
| **Tutorial Inicial** | 3 | 2 | 1 | 0 | Captura oficial EN 98-822 (`tutorial.json`) |
| **Cidade Externa e Mapa-Múndi** | 17 | 6 | 11 | 0 | Capturas EN #718 e instância 100000xxx |
| **Mundo Compartilhado (Cloud City)** | 6 | 4 | 2 | 0 | Capturas e mapas 1 a 5 |
| **PvP e Chefes Mundiais** | 9 | 3 | 5 | 1 | Capturas TR e `world_bosses` |
| **Atividades e Eventos** | 28 | 6 | 21 | 1 | `game_settings.events` e temporizadores |
| **VIP e Contratos** | 7 | 2 | 5 | 0 | Capturas e tabelas de privilégios |
| **Veículos (Tank Trials)** | 5 | 4 | 1 | 0 | Capturas e regras de batalha 3001 |
| **Conta e Segurança** | 8 | 5 | 1 | 2 | RSA PKCS1v15, tickets, SHA256/bcrypt |
| **TOTAL** | **283** | **132** | **136** | **15** | — |

---

## 1.1 STATUS DE INTEGRIDADE DA CDN

A integridade da CDN local foi substancialmente aprimorada após a extração dos pacotes locais de montarias e a recuperação de dados e ícones da fonte externa Legend Legacy:

* **Espelho Local:** `CDN/res134-bmclas-sq.7road.net` (38.942 arquivos).
* **Cobertura Geral:** **91,06%** das referências mapeadas resolvidas (8.805 de 9.669 referências resolvidas contra 88,43% anterior).
* **Cobertura de Ícones:** **100% RESOLVIDA** para todas as categorias de gameplay:
  * `ItemTempInfos.Icon`: 4.515/4.515 (100%)
  * `SkillTempInfos.Icons`: 237/237 (100%)
  * `SkillBufferTempInfos.Icon`: 338/338 (100% — recuperados 197 buffs faltantes)
  * `VehicleSkillTempInfos.Icons`: 39/39 (100% — recuperadas 13 skills faltantes)
  * `GameHeroTemp.Icon`: 93/93 (100%)
  * `PowcardTempInfos.Icon` e `PowCardSuiteTemInfos.Icon`: 25/25 (100%)
* **Montarias e Avatares:**
  * 387 montarias e avatares integrados via descompactação de `mounts_equip_show.tar.gz` para `CDN/res134-bmclas-sq.7road.net/swf/avatar/`.
  * Cobertura de avatares de montaria no `tempinfos.xml` passou para **387/388 (99,74%)**.
* **Tabelas Completas em Português (PT-BR):**
  * Baixadas e salvas em `data_pt_assets/dados/`: `ItemTempInfo.json` (4,5 MB), `SkillSlim.json` (1,9 MB), `BuffSlim.json` (3,2 MB), `MountTempInfo.json` (250 KB), `SkillTempInfo.json` (3,0 MB), `QuestTempInfo.json`, `QuestConditionInfo.json`, `PawnTempInfo.json`, `UpGradeTempInfo.json`, `ConfigInfo.json`, `MapInfo.json`, `MapNodeInfo.json`.

---

## 2. MATRIZ DETALHADA POR SUBSISTEMA

### 2.1. Conta, SeguranÃ§a e Protocolo
* **AutenticaÃ§Ã£o RSA e Tickets:** **VALIDADO**. Chave pÃºblica exportada via `client-config.php`, decodificaÃ§Ã£o de `POST /login`, geraÃ§Ã£o de sessÃ£o e chave temporÃ¡ria AES. Testado em `test_full_chain.py` e `test_login_flow.py`.
* **Handshake TCP 20001 (StreamCipher):** **VALIDADO**. Troca de chave `ekeys`, descriptografia contÃ­nua de pacotes de 8 bytes de header.
* **WebSocket Bridge (Ruffle):** **VALIDADO**. Porta 5001 com proxy direto para o pipeline de pacotes TCP.
* **Flash Policy Server (843):** **VALIDADO**. Resposta imediata de `<cross-domain-policy>` para o Flash Player Projector.
* **Anti-VÃ­cio (AAS) e SMS:** **BLOQUEADO**. Removido/desabilitado deliberadamente por se tratar de servidor privado sem legislaÃ§Ã£o chinesa.

### 2.2. Personagem e ProgressÃ£o
* **CriaÃ§Ã£o de Personagem (`visualizeregister`):** **VALIDADO**. ValidaÃ§Ã£o de nickname, sexo, classe (Knight, Mage, Archer), criaÃ§Ã£o do registro `characters`, lÃ­der em `heroes` e castelo inicial.
* **AlocaÃ§Ã£o de Atributos e Crescimento:** **VALIDADO**. Crescimento por classe (Maga: Int +3, Agi +1, LideranÃ§a +10, Fis +1) em `rules.py`. Poder de combate bate com fÃ³rmula calibrada:
  $$\text{Poder} = \text{PhyAtk} + \text{PhyDef} + 1,05 \times \text{MagAtk} + \text{MagDef} + \text{ForceHit} + \text{Parry} + \text{ConatArmy} + \frac{\text{Live}}{5}$$
* **Tutorial Inicial (Campanha de Treino):** **VALIDADO**. ExecuÃ§Ã£o reproduzida com fidelidade a partir de `tutorial.json` (mapas 10001 e 10002, baÃº com arma da classe, Dinah como escolta e chefe de invasÃ£o).
* **Pulo de Tutorial (`skip_tutorial=true`):** **VALIDADO**. `noviceProcess = 19000` libera o castelo de imediato sem travar o cliente.

### 2.3. Castelo e PrÃ©dios
* **Upgrade de PrÃ©dios e Filas (8203/8279):** **VALIDADO**. Custo de ouro, prÃ©-requisitos, tempos de construÃ§Ã£o e notificaÃ§Ã£o de tÃ©rmino no chat. Testado em `test_castelo.py`.
* **ProduÃ§Ã£o de Ouro e TributaÃ§Ã£o (5015/8327):** **VALIDADO**. CÃ¡lculo incremental por segundo respeitando o teto de armazenamento.
* **Fazenda e Colheita:** **VALIDADO**. Plantio, crescimento em minutos inteiros, colheita, pragas, reviver plantas e regar Ã¡rvore de amigos.
* **Caixa por Tempo (5019):** **VALIDADO**. Contagem progressiva de tempo de sessÃ£o, concessÃ£o de itens e moedas.

### 2.4. Combate (PvE e Batalhas por Turnos)
* **Pipeline de Batalha (157 â†’ 10007 â†’ 156 â†’ 153/75 â†’ 154 â†’ 4103):** **VALIDADO**. Loop em 25 fps (frames de 40 ms), cooldowns de habilidades, gasto de FÃºria (SP) e sincronizaÃ§Ã£o de animaÃ§Ã£o.
* **FÃ³rmula de Dano:** **VALIDADO**. $\text{Dano} = \max((A - D) \times 0,5, A \times 0,1) \times \frac{\text{Parameter1}}{100} + \text{Parameter2} \pm 8\%$.
* **Tropas em Batalha:** **VALIDADO**. CÃ¡lculo de vida das pilhas por `Live Ã— quantidade / 100`, divisÃ£o das tropas nas fileiras e recomposiÃ§Ã£o apÃ³s a vitÃ³ria.
* **Mascote e Despertar (Morph 4600):** **PARCIAL**. O mascote luta e o ganho de despertar (+250) opera corretamente; refinamento do ganho contÃ­nuo estÃ¡ em `battle_formula`.

### 2.5. Mochila, Itens e Forja
* **MovimentaÃ§Ã£o e Uso de Itens (5005/5006):** **VALIDADO**. ValidaÃ§Ã£o de bolsas, pacotes de poÃ§Ã£o, montarias e equipamentos.
* **Forja e Aprimoramento (5150/5151/5152):** **VALIDADO**. Engaste de gemas, furos adicionais com Soul Socketing Rod, refino de atributos.
* **ExpansÃ£o de Mochila (5010):** **VALIDADO**. Compra de linhas adicionais com dÃ©bito correto em `cash_ledger`.

### 2.6. Cidade Externa, Masmorras e Multijogador
* **Minas de Ouro e ExploraÃ§Ã£o (8201/5160):** **VALIDADO**. Refresh de 12 horas, sorteio de nÃ­veis 8 a 10 e combate contra o guarda.
* **Campanhas e Dungeons:** **PARCIAL**. Campanha 1001 100% operacional; campanhas avanÃ§adas aguardam preenchimento integral dos templates de nÃ³s.
* **Salas Multiplayer:** **PARCIAL**. Opcodes de convite e sala implementados; posicionamento do exÃ©rcito em combate de grupo utiliza `TEAM_POS` deduzido.
* **Chefes Mundiais (World Boss):** **PARCIAL**. Agendamento automÃ¡tico (5001 e 5003), pool de vida concorrente (`SharedHp`) e vida que escala +50% por abate. Falta homologar reviver instantÃ¢neo pago.

### 2.7. Guilda e ClÃ£
* **CriaÃ§Ã£o, Membros e PermissÃµes (5130/8207):** **VALIDADO**. AlocaÃ§Ã£o de cargos, direitos em bitmaps oficiais e chat de guilda.
* **BÃªnÃ§Ã£o do Altar (8215/5145):** **VALIDADO**. Sorteio das casas da roleta, concessÃ£o de itens e avisos no chat.
* **Terra Secreta e Invasores:** **PARCIAL**. Entrada na instÃ¢ncia da guilda e ondas horÃ¡rias de invasores funcionais; combate GvG em mapa exclusivo estÃ¡ pendente.

---

## 3. AUDITORIA FORENSE DA CDN E ARQUIVOS DO CLIENTE

1. **Volume Auditado:** 38.237 arquivos (~9,83 GB).
2. **Descoberta CrÃ­tica do CabeÃ§alho `road7`:**
   - MÃ³dulos de cÃ³digo Flash (`ui/zh_cn/swf/*.swf`, `2.png` a `18.png`, `ui/zh_cn/xml/xml.png`) exigem cabeÃ§alho de 37 bytes (`b"road7"` + 32 chars hex MD5). O descarte pelo `MD5Installer` do cliente Ã© mandatÃ³rio.
   - Ícones de itens e habilidades (`icon/*.png`) sÃ£o imagens PNG padrÃ£o sem `road7`.
   - Assets brutos de montarias e avatares estÃ£o catalogados no pacote `mounts_equip_show.tar.gz` (387 montarias).
3. **ResoluÃ§Ã£o de ReferÃªncias:**
   - Total de referÃªncias resolvidas: **88,43%**.
   - O `cdn_nginx.conf` estÃ¡ parametrizado com fallbacks transparentes (`empty.png`, `empty.swf`, `empty.mp3`) para prevenir congelamentos de carregamento ou erros `#1009`.

---

## 4. REGRESSÃƒO E CORREÃ‡Ã•ES DESTE CICLO

1. **CorreÃ§Ã£o de DivergÃªncias de Idioma (PT-BR vs EN) nos Testes:**
   - Adaptadas asserÃ§Ãµes em `tests/game/test_castelo.py` e `tests/game/test_items.py` para aceitar tanto os nomes originais em inglÃªs quanto os nomes traduzidos em portuguÃªs do `tempinfos.xml`.
   - **Resultado:** 38/38 testes de Castelo e Itens aprovados com 100% de sucesso.
2. **ValidaÃ§Ã£o Ponta a Ponta Local (`test_full_chain.py`):**
   - Fluxo completo Portal â†’ Banco â†’ Ticket â†’ Login HTTP â†’ CriaÃ§Ã£o de Personagem â†’ TCP 5000 â†’ Entrada no Mundo aprovado com sucesso.
