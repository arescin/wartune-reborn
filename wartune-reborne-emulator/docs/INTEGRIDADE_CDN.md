# Integridade da CDN

Espelho: `G:\projects\wartune-reborn-emulator\CDN\res134-bmclas-sq.7road.net` — 38942 arquivos.
Gerado por `tools/auditar_cdn.py` a partir de `data/templates/tempinfos.xml`.

## Cobertura por referência

| Categoria | Atributo | Caminho | Distintos | Presentes | Faltando |
|---|---|---|---:|---:|---:|
| ItemTempInfos | Icon | `icon{v}` | 4515 | 4515 | 0 |
| SkillTempInfos | Icons | `icon{v}` | 237 | 237 | 0 |
| SkillBufferTempInfos | Icon | `icon{v}` | 338 | 338 | 0 |
| BuildingTempInfos | Icon | `icon{v}` | 19 | 19 | 0 |
| CampaignBufferTemps | Icon | `icon{v}` | 34 | 34 | 0 |
| ConsortiaLevelInfos | Icon | `icon{v}` | 7 | 7 | 0 |
| EffectTempInfos | Icon | `icon{v}` | 20 | 20 | 0 |
| PawnTempInfos | Icon | `icon{v}` | 14 | 14 | 0 |
| PowCardSuiteTemInfos | Icon | `icon{v}` | 5 | 5 | 0 |
| PowcardTempInfos | Icon | `icon{v}` | 20 | 20 | 0 |
| RuneTempInfos | Icon | `icon{v}` | 10 | 10 | 0 |
| VehicleBuffTempInfos | Icon | `icon{v}` | 8 | 8 | 0 |
| VehicleSkillTempInfos | Icons | `icon{v}` | 39 | 39 | 0 |
| starTempInfos | Icon | `icon{v}` | 63 | 63 | 0 |
| GameHeroTemp | Icon | `icon{v}` | 93 | 93 | 0 |
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

**Total: 8805/9669 referências resolvidas (91.06%).**

## Faltando

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
