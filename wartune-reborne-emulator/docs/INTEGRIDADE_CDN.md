# Integridade da CDN

Espelho: `G:\projects\wartune-reborn-emulator\CDN\res134-bmclas-sq.7road.net` — 38273 arquivos.
Gerado por `tools/auditar_cdn.py` a partir de `data/templates/tempinfos.xml`.

## Cobertura por referência

| Categoria | Atributo | Caminho | Distintos | Presentes | Faltando |
|---|---|---|---:|---:|---:|
| ItemTempInfos | Icon | `icon{v}` | 4515 | 4490 | 25 |
| SkillTempInfos | Icons | `icon{v}` | 237 | 234 | 3 |
| SkillBufferTempInfos | Icon | `icon{v}` | 338 | 141 | 197 |
| BuildingTempInfos | Icon | `icon{v}` | 19 | 19 | 0 |
| CampaignBufferTemps | Icon | `icon{v}` | 34 | 34 | 0 |
| ConsortiaLevelInfos | Icon | `icon{v}` | 7 | 7 | 0 |
| EffectTempInfos | Icon | `icon{v}` | 20 | 20 | 0 |
| PawnTempInfos | Icon | `icon{v}` | 14 | 14 | 0 |
| PowCardSuiteTemInfos | Icon | `icon{v}` | 5 | 0 | 5 |
| PowcardTempInfos | Icon | `icon{v}` | 20 | 12 | 8 |
| RuneTempInfos | Icon | `icon{v}` | 10 | 10 | 0 |
| VehicleBuffTempInfos | Icon | `icon{v}` | 8 | 8 | 0 |
| VehicleSkillTempInfos | Icons | `icon{v}` | 39 | 26 | 13 |
| starTempInfos | Icon | `icon{v}` | 63 | 63 | 0 |
| GameHeroTemp | Icon | `icon{v}` | 93 | 89 | 4 |
| SpecialTempInfos | ResPath | `icon{v}` | 5 | 5 | 0 |
| ItemTempInfos | Avata | `equip{v}` (pasta) | 1200 | 1194 | 6 |
| ItemTempInfos | Avata | `swf/avatar{v}` (pasta) | 1200 | 918 | 282 |
| GameHeroTemp | ArmPath | `equip{v}` (pasta) | 7 | 1 | 6 |
| GameHeroTemp | ClothPath | `equip{v}` (pasta) | 6 | 5 | 1 |
| PetTempInfos | PetAvatar | `equip{v}` (pasta) | 18 | 18 | 0 |
| MountTempInfos | AvatarPath | `swf/avatar{v}` (pasta) | 388 | 387 | 1 |
| VehicleObjectTempInfos | Avatar | `vehicle/avatar{v}` (pasta) | 20 | 18 | 2 |
| PawnTempInfos | Swf | `swf/{v}/{v}.swf` | 72 | 72 | 0 |
| GameHeroTemp | ResPath | `swf/{v}/{v}.swf` | 104 | 103 | 1 |
| FishTemplateInfos | Path | `fish{v}.swf` | 13 | 13 | 0 |
| MapInfos | MusicPath | `sounds/{v}.flv` | 39 | 37 | 2 |
| BuildingTempInfos | PicPath | `{v}` | 19 | 17 | 2 |
| MapInfos | MapFileId | `sceneIma/{v}/map{v}.swf` | 249 | 5 | 244 |
| MapInfos | MapFileId | `maps/{v}/{v}.maps` | 249 | 248 | 1 |
| MapInfos | MapFileId | `maps/{v}/{v}.titles` | 249 | 248 | 1 |
| MapInfos | Id | `images/mapName/{v}.png` | 409 | 94 | 315 |

**Total: 8550/9669 referências resolvidas (88.43%).**

## Faltando

### ItemTempInfos.Icon → `icon{v}` (25)

- `icon/box_star_teer.png` — pedido por 1 template(s): 2060472
- `icon/box_superfashion.png` — pedido por 1 template(s): 2060471
- `icon/boxvip_lv20.png` — pedido por 3 template(s): 2060455, 2060458, 2060461
- `icon/boxvip_lv30.png` — pedido por 3 template(s): 2060456, 2060459, 2060462
- `icon/boxvip_lv40.png` — pedido por 3 template(s): 2060457, 2060460, 2060463
- `icon/compose_80EX_cloth.png` — pedido por 1 template(s): 2129804
- `icon/compose_80EX_hat.png` — pedido por 1 template(s): 2129803
- `icon/compose_80EX_necklace.png` — pedido por 1 template(s): 2129806
- … mais 17

### SkillTempInfos.Icons → `icon{v}` (3)

- `icon/skill_fate03.png` — pedido por 31 template(s): 2200, 2201, 2202, 2203, 2204 (+26)
- `icon/skill_pawn_010.png` — pedido por 1 template(s): 86
- `icon/skill_pawn_011.png` — pedido por 1 template(s): 96

### SkillBufferTempInfos.Icon → `icon{v}` (197)

- `icon/buff-armor-down.png` — pedido por 24 template(s): 22142105, 76500003, 83980301, 83980302, 83980303 (+19)
- `icon/buff-armor-up.png` — pedido por 31 template(s): 6261011, 6261012, 6261013, 6261014, 6261015 (+26)
- `icon/buff-attack-down.png` — pedido por 10 template(s): 83960301, 83960302, 83960303, 83960304, 83960305 (+5)
- `icon/buff-attack-up.png` — pedido por 16 template(s): 8010729, 8020000, 8020002, 41000011, 41000018 (+11)
- `icon/buff-bossfrenzy.png` — pedido por 10 template(s): 52021, 52022, 52023, 52024, 52025 (+5)
- `icon/buff-easy2hurt.png` — pedido por 50 template(s): 51091, 51092, 51093, 51094, 51095 (+45)
- `icon/buff-hard2hurt.png` — pedido por 7 template(s): 705408, 8010715, 9151402, 9151404, 25670001 (+2)
- `icon/buff-healeffect-down.png` — pedido por 8 template(s): 5031080, 5032080, 5033080, 5041080, 5042080 (+3)
- … mais 189

### PowCardSuiteTemInfos.Icon → `icon{v}` (5)

- `icon/cardsuit1.png` — pedido por 1 template(s): 1000
- `icon/cardsuit2.png` — pedido por 1 template(s): 1001
- `icon/cardsuit3.png` — pedido por 1 template(s): 1003
- `icon/cardsuit4.png` — pedido por 1 template(s): 1002
- `icon/cardsuit5.png` — pedido por 1 template(s): 1004

### PowcardTempInfos.Icon → `icon{v}` (8)

- `icon/card_skeleton01.png` — pedido por 1 template(s): 10011
- `icon/card_skeleton02.png` — pedido por 1 template(s): 10012
- `icon/card_skeleton03.png` — pedido por 1 template(s): 10013
- `icon/card_skeleton04.png` — pedido por 1 template(s): 10014
- `icon/card_tauren01.png` — pedido por 2 template(s): 10001, 10005
- `icon/card_tauren02.png` — pedido por 1 template(s): 10002
- `icon/card_tauren03.png` — pedido por 1 template(s): 10003
- `icon/card_tauren04.png` — pedido por 1 template(s): 10004

### VehicleSkillTempInfos.Icons → `icon{v}` (13)

- `icon/hunter_002.png` — pedido por 1 template(s): 570902
- `icon/hunter_003.png` — pedido por 1 template(s): 570903
- `icon/hunter_004.png` — pedido por 1 template(s): 571003
- `icon/hunter_007.png` — pedido por 2 template(s): 570901, 571001
- `icon/hunter_011.png` — pedido por 1 template(s): 571002
- `icon/warrior_001.png` — pedido por 2 template(s): 570801, 570701
- `icon/warrior_002.png` — pedido por 1 template(s): 570702
- `icon/warrior_008.png` — pedido por 1 template(s): 570803
- … mais 5

### GameHeroTemp.Icon → `icon{v}` (4)

- `icon/head_monster001A.png` — pedido por 1 template(s): 5054
- `icon/head_monster006B.jpg` — pedido por 4 template(s): 70014, 70034, 71014, 71034
- `icon/head_monster019E.jpg` — pedido por 3 template(s): 5030, 5080, 6010
- `icon/head_unknown.png` — pedido por 7 template(s): 1051, 1072, 1152, 1202, 1222 (+2)

### ItemTempInfos.Avata → `equip{v}` (6)

- `equip/farm/EXP` — pedido por 14 template(s): 2160010, 2160011, 2160012, 2160022, 2160023 (+9)
- `equip/farm/crystal` — pedido por 11 template(s): 2160007, 2160008, 2160009, 2160019, 2160020 (+6)
- `equip/farm/gift` — pedido por 5 template(s): 2160037, 2160038, 2160039, 2160040, 2160041
- `equip/farm/gold` — pedido por 11 template(s): 2160001, 2160002, 2160003, 2160013, 2160014 (+6)
- `equip/farm/medal` — pedido por 6 template(s): 2125031, 2160042, 2160043, 2160044, 2160045 (+1)
- `equip/farm/soul` — pedido por 11 template(s): 2160004, 2160005, 2160006, 2160016, 2160017 (+6)

### ItemTempInfos.Avata → `swf/avatar{v}` (282)

- `swf/avatar/farm/EXP` — pedido por 14 template(s): 2160010, 2160011, 2160012, 2160022, 2160023 (+9)
- `swf/avatar/farm/crystal` — pedido por 11 template(s): 2160007, 2160008, 2160009, 2160019, 2160020 (+6)
- `swf/avatar/farm/gift` — pedido por 5 template(s): 2160037, 2160038, 2160039, 2160040, 2160041
- `swf/avatar/farm/gold` — pedido por 11 template(s): 2160001, 2160002, 2160003, 2160013, 2160014 (+6)
- `swf/avatar/farm/medal` — pedido por 6 template(s): 2125031, 2160042, 2160043, 2160044, 2160045 (+1)
- `swf/avatar/farm/soul` — pedido por 11 template(s): 2160004, 2160005, 2160006, 2160016, 2160017 (+6)
- `swf/avatar/fashion_hat_37wan` — pedido por 1 template(s): 1101801
- `swf/avatar/fashion_hat_HK` — pedido por 1 template(s): 1101501
- … mais 274

### GameHeroTemp.ArmPath → `equip{v}` (6)

- `equip/hunter_arms050` — pedido por 1 template(s): 8
- `equip/warrior_arms020` — pedido por 10 template(s): 11006, 11007, 11008, 11009, 11010 (+5)
- `equip/warrior_arms030` — pedido por 10 template(s): 11011, 11012, 11013, 11014, 11015 (+5)
- `equip/warrior_arms040` — pedido por 10 template(s): 11016, 11017, 11018, 11019, 11020 (+5)
- `equip/warrior_arms050` — pedido por 8 template(s): 11021, 11022, 11023, 11024, 14021 (+3)
- `equip/warrior_arms060` — pedido por 13 template(s): 7, 11025, 11026, 11027, 11028 (+8)

### GameHeroTemp.ClothPath → `equip{v}` (1)

- `equip/warrior_body02` — pedido por 1 template(s): 14006

### MountTempInfos.AvatarPath → `swf/avatar{v}` (1)

- `swf/avatar/mount_FlyDragon` — pedido por 1 template(s): 7001

### VehicleObjectTempInfos.Avatar → `vehicle/avatar{v}` (2)

- `vehicle/avatar/tower` — pedido por 11 template(s): 3205, 570301, 570302, 570303, 3001 (+6)
- `vehicle/avatar/vehicle_2001` — pedido por 4 template(s): 2191, 8001, 7000, 6004

### GameHeroTemp.ResPath → `swf/{v}/{v}.swf` (1)

- `swf/monster019E/monster019E.swf` — pedido por 3 template(s): 5030, 5080, 6010

### MapInfos.MusicPath → `sounds/{v}.flv` (2)

- `sounds/BGM201402.flv` — pedido por 3 template(s): 1111, 1451, 1452
- `sounds/bgm_wedding.flv` — pedido por 3 template(s): 4301, 4302, 4303

### BuildingTempInfos.PicPath → `{v}` (2)

- `images/tree_1.swf` — pedido por 1 template(s): 150901
- `images/tree_2.swf` — pedido por 1 template(s): 150902

### MapInfos.MapFileId → `sceneIma/{v}/map{v}.swf` (244)

- `sceneIma/100/map100.swf` — pedido por 1 template(s): 100
- `sceneIma/10000/map10000.swf` — pedido por 1 template(s): 10000
- `sceneIma/10001/map10001.swf` — pedido por 1 template(s): 10001
- `sceneIma/10002/map10002.swf` — pedido por 1 template(s): 10002
- `sceneIma/1011/map1011.swf` — pedido por 1 template(s): 1011
- `sceneIma/1021/map1021.swf` — pedido por 1 template(s): 1021
- `sceneIma/1031/map1031.swf` — pedido por 1 template(s): 1031
- `sceneIma/1032/map1032.swf` — pedido por 1 template(s): 1032
- … mais 236

### MapInfos.MapFileId → `maps/{v}/{v}.maps` (1)

- `maps/8301/8301.maps` — pedido por 1 template(s): 8301

### MapInfos.MapFileId → `maps/{v}/{v}.titles` (1)

- `maps/8301/8301.titles` — pedido por 1 template(s): 8301

### MapInfos.Id → `images/mapName/{v}.png` (315)

- `images/mapName/10000.png` — pedido por 1 template(s): 10000
- `images/mapName/10002.png` — pedido por 1 template(s): 10002
- `images/mapName/1032.png` — pedido por 1 template(s): 1032
- `images/mapName/1072.png` — pedido por 1 template(s): 1072
- `images/mapName/1073.png` — pedido por 1 template(s): 1073
- `images/mapName/1082.png` — pedido por 1 template(s): 1082
- `images/mapName/1083.png` — pedido por 1 template(s): 1083
- `images/mapName/1132.png` — pedido por 1 template(s): 1132
- … mais 307

## Pastas de avatar sem referência nos templates

- `equip/`: 31 sem referência (ex.: hunter_default_arms, hunter_default_body, hunter_default_body_cloak, hunter_default_hair, mystery_default_body)
- `swf/avatar/`: 1855 sem referência (ex.: fashion_cloth_2015_chinese_new_year_mount, fashion_cloth_37wan_mount, fashion_cloth_HK_mount, fashion_cloth_Leather_mount, fashion_cloth_Saint_mount)
- `vehicle/avatar/`: 0 sem referência
