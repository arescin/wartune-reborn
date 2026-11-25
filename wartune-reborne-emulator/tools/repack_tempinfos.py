"""Utilitário para empacotar tempinfos.xml binário 7Road com tabelas corretas."""

import os
import re
import struct
import zlib


def fix_quest_and_nodes_xml(xml_data: bytes) -> bytes:
    # 1. MapNodeInfos: Nós 2 e 3 de MapId 10000
    idx_node2 = xml_data.find(b'Id="2" MapId="10000"')
    if idx_node2 != -1:
        end_node2 = xml_data.find(b'/>', idx_node2) + 2
        chunk2 = xml_data[idx_node2:end_node2].replace(b'PosX="301" PosY="148"', b'PosX="108" PosY="88"')
        xml_data = xml_data[:idx_node2] + chunk2 + xml_data[end_node2:]

    idx_node3 = xml_data.find(b'Id="3" MapId="10000"')
    if idx_node3 != -1:
        end_node3 = xml_data.find(b'/>', idx_node3) + 2
        chunk3 = xml_data[idx_node3:end_node3].replace(b'PosX="392" PosY="96"', b'PosX="36" PosY="128"')
        xml_data = xml_data[:idx_node3] + chunk3 + xml_data[end_node3:]

    # 2. QuestTemps: 183, 765, 100, 863, 910, 390, 173
    for qid in (b'183', b'765', b'910', b'390', b'173'):
        idx = xml_data.find(b'<QuestTempInfo TemplateId="' + qid + b'"')
        if idx != -1:
            end = xml_data.find(b'/>', idx) + 2
            chunk = xml_data[idx:end].replace(b'EndDate="2000-01-01 00:00:00"', b'EndDate="2050-01-01 00:00:00"')
            if qid == b'765':
                chunk = chunk.replace(b'PreQuestId="100"', b'PreQuestId=""')
            xml_data = xml_data[:idx] + chunk + xml_data[end:]

    idx_100 = xml_data.find(b'<QuestTempInfo TemplateId="100"')
    if idx_100 != -1:
        end_100 = xml_data.find(b'/>', idx_100) + 2
        chunk100 = xml_data[idx_100:end_100].replace(b'PreQuestId=""', b'PreQuestId="80,81,90"')
        xml_data = xml_data[:idx_100] + chunk100 + xml_data[end_100:]

    idx_863 = xml_data.find(b'<QuestTempInfo TemplateId="863"')
    if idx_863 != -1:
        end_863 = xml_data.find(b'/>', idx_863) + 2
        chunk863 = xml_data[idx_863:end_863].replace(b'NeedMinLevel="11"', b'NeedMinLevel="10"').replace(b'EndDate="2000-01-01 00:00:00"', b'EndDate="2050-10-12 00:00:00"')
        xml_data = xml_data[:idx_863] + chunk863 + xml_data[end_863:]

    # 3. QuestCondictionInfos: 764, 922
    idx_764_c = xml_data.find(b'<QuestConditionInfo TemplateId="764" CondictionType="10"')
    if idx_764_c != -1:
        end_764_c = xml_data.find(b'/>', idx_764_c) + 2
        chunk764_c = xml_data[idx_764_c:end_764_c].replace(b'Para2="20"', b'Para2="5"')
        xml_data = xml_data[:idx_764_c] + chunk764_c + xml_data[end_764_c:]

    idx_922_c = xml_data.find(b'<QuestConditionInfo TemplateId="922"')
    if idx_922_c != -1:
        end_922_c = xml_data.find(b'/>', idx_922_c) + 2
        new_922_c = b'<QuestConditionInfo TemplateId="922" CondictionType="85" CondictionTitle="Conversar com Azrael" Para1="0" Para2="1" Para3="0" Para4="10000,3"/>'
        xml_data = xml_data[:idx_922_c] + new_922_c + xml_data[end_922_c:]

    # 4. QuestGoods: 863, 9
    if b'<QuestGoods>' in xml_data:
        goods_inject = b''
        if b'<QuestGood TemplateId="863"' not in xml_data:
            goods_inject += b'<QuestGood TemplateId="863" RewardItemID="208015" IsSelect="false" RewardItemCount="10" ToJob="0" ValidDate="0"/>'
        if b'<QuestGood TemplateId="9"' not in xml_data:
            goods_inject += b'<QuestGood TemplateId="9" RewardItemID="2060013" IsSelect="false" RewardItemCount="1" ToJob="0" ValidDate="0"/><QuestGood TemplateId="9" RewardItemID="208005" IsSelect="false" RewardItemCount="2" ToJob="0" ValidDate="0"/>'
        if goods_inject:
            xml_data = xml_data.replace(b'<QuestGoods>', b'<QuestGoods>' + goods_inject, 1)

    return xml_data


def fix_building_population(xml_data: bytes) -> bytes:
    def repl(m: re.Match) -> bytes:
        grade = int(m.group(1))
        pop = 600 + grade * 300
        return m.group(0).replace(b'Property2="0"', f'Property2="{pop}"'.encode('utf-8'))

    pattern = rb'<BuildingTempInfo[^>]+SonType="1201"[^>]+BuildingGrade="(\d+)"[^>]*>'
    return re.sub(pattern, repl, xml_data)


def repack(orig_path: str = "G:/projects/legend-online-main/raw/xml/tempinfos.xml") -> None:
    raw_data = open(orig_path, "rb").read()
    if not raw_data.startswith(b"x\xda"):
        raw_data = raw_data[4:]
    raw = zlib.decompress(raw_data)

    version = struct.unpack(">I", raw[:4])[0]
    print(f"Original version: {version}, size: {len(raw)} bytes")

    offset = 4
    tables: list[tuple[str, bytes]] = []
    while offset < len(raw):
        name_len = raw[offset]
        offset += 1
        name = raw[offset : offset + name_len].decode("utf-8", errors="ignore")
        offset += name_len
        xml_len = struct.unpack(">I", raw[offset : offset + 4])[0]
        offset += 4
        xml_bytes = raw[offset : offset + xml_len]
        offset += xml_len
        tables.append((name, xml_bytes))

    print(f"Parsed {len(tables)} tables.")

    # Injetar MapInfo 10001 e CampaignInfo 10001 para suportar o tutorial inicial
    map_entry = (
        b'<MapInfo Id="10001" CampaignId="10002" MapName="Monte do Drag\xc3\xa3o Divino" '
        b'Type="1" MinLevel="0" MaxLevel="0" Width="2000" Height="2000" MapFileId="10002" '
        b'BattleGround="14" MusicPath="bgm_10002" Description="" Index="0"/>'
    )
    camp_entry = (
        b'<CampaignInfo CampaignId="10001" CampaignName="Monte do Drag\xc3\xa3o Divino" Types="0" '
        b'SonTypes="0" LandId="0" DungeonId="0" AreaId="0" MinLevel="1" MaxLevel="5" PreCampaignId="0" '
        b'NextCampaignId="0" Capacity="1" DifficultyGrade="1" Description="" CardPayment="0" PosX="0" PosY="0" '
        b'Item="" StandSecond="0" StandardDamage="0" StandardHurt="0" BaseGp="0" OpenTime="" StopTime="" '
        b'NeedTransfer="false" NeedFightPower="0" MapIds="" NeedChangeJob="false" NeedThirdTransfer="false" '
        b'NeedTransferType="0" EnterNumb="0"/>'
    )

    # Injetar soldados do tutorial (PawnTempInfos: 1001, 2001, 2002, 2003)
    pawn_entries = (
        b'<PawnTempInfo TemplateId="1001" MasterType="101" SonType="2101" Camp="1" Level="1" NextLevelTemplateId="0" '
        b'PawnName="Soldado" Description="" CrystalsConsume="0" GoldConsume="0" NeedBuilding="0" NeedTime="0" '
        b'NeedPopulation="1" Live="8" Attack="60" Defence="0" MagicAttack="60" MagicDefence="0" ForceHit="64" '
        b'Parry="0" Swf="001" AttackType="1" DefaultSkill="10000" Icon="/head_001.jpg" HighSkill="" HeroSkill="" '
        b'AI="2006" ReduceResi="0" FireResi="0" WaterResi="0" ElectResi="0" WindResi="0" DarkResi="0" LightResi="0" '
        b'Penetrate="0" ReduceResiAgainst="0" ResiPenetrate="0" StunAttr="-1"/>'
        b'<PawnTempInfo TemplateId="2001" MasterType="101" SonType="2101" Camp="1" Level="1" NextLevelTemplateId="0" '
        b'PawnName="Huntera" Description="" CrystalsConsume="0" GoldConsume="0" NeedBuilding="0" NeedTime="0" '
        b'NeedPopulation="1" Live="8" Attack="60" Defence="0" MagicAttack="60" MagicDefence="0" ForceHit="64" '
        b'Parry="0" Swf="monster002b" AttackType="1" DefaultSkill="10000" Icon="/head_monster002.jpg" HighSkill="" '
        b'HeroSkill="" AI="2006" ReduceResi="0" FireResi="0" WaterResi="0" ElectResi="0" WindResi="0" DarkResi="0" '
        b'LightResi="0" Penetrate="0" ReduceResiAgainst="0" ResiPenetrate="0" StunAttr="-1"/>'
        b'<PawnTempInfo TemplateId="2002" MasterType="101" SonType="2101" Camp="1" Level="2" NextLevelTemplateId="0" '
        b'PawnName="Ca\xc3\xa7ador" Description="" CrystalsConsume="0" GoldConsume="0" NeedBuilding="0" NeedTime="0" '
        b'NeedPopulation="1" Live="8" Attack="60" Defence="0" MagicAttack="60" MagicDefence="0" ForceHit="64" '
        b'Parry="0" Swf="monster012a" AttackType="1" DefaultSkill="10000" Icon="/head_monster012.jpg" HighSkill="" '
        b'HeroSkill="" AI="2006" ReduceResi="0" FireResi="0" WaterResi="0" ElectResi="0" WindResi="0" DarkResi="0" '
        b'LightResi="0" Penetrate="0" ReduceResiAgainst="0" ResiPenetrate="0" StunAttr="-1"/>'
        b'<PawnTempInfo TemplateId="2003" MasterType="101" SonType="2101" Camp="1" Level="3" NextLevelTemplateId="0" '
        b'PawnName="Urso Voraz" Description="" CrystalsConsume="0" GoldConsume="0" NeedBuilding="0" NeedTime="0" '
        b'NeedPopulation="1" Live="8" Attack="60" Defence="0" MagicAttack="60" MagicDefence="0" ForceHit="64" '
        b'Parry="0" Swf="monster022a" AttackType="1" DefaultSkill="10000" Icon="/head_monster022.jpg" HighSkill="" '
        b'HeroSkill="" AI="2006" ReduceResi="0" FireResi="0" WaterResi="0" ElectResi="0" WindResi="0" DarkResi="0" '
        b'LightResi="0" Penetrate="0" ReduceResiAgainst="0" ResiPenetrate="0" StunAttr="-1"/>'
    )

    # Injetar heróis do tutorial (GameHeroTemp: 1002, 1003, 1004, 1005)
    hero_entries = (
        b'<GameHeroTempInfo TemplateId="1002" TemplateName="Tauren Axeman" HeroType="3" Job="1" Sexs="1" '
        b'Icon="/head_boss002.jpg" Grades="5" AI="0" DefaultSkill="10000" Power="50" Agility="50" Intellect="50" '
        b'Captain="100" Physique="50" Attack="50" Defence="20" MagicAttack="20" MagicDefence="20" Live="300" '
        b'Conat="0" ForceHit="10" Parry="10" SkillScript="50021,50022" ResPath="boss002" ArmPath="" ClothPath="" '
        b'RejectType="" FireResi="0" WaterResi="0" ElectResi="0" WindResi="0" DarkResi="0" LightResi="0" '
        b'ReduceResi="0" ReduceResiAgainst="0" ResiPenetrate="0"/>'
        b'<GameHeroTempInfo TemplateId="1003" TemplateName="Exhausted Soldier" HeroType="3" Job="1" Sexs="1" '
        b'Icon="/head_001.jpg" Grades="1" AI="0" DefaultSkill="10000" Power="10" Agility="10" Intellect="10" '
        b'Captain="100" Physique="10" Attack="20" Defence="10" MagicAttack="10" MagicDefence="10" Live="140" '
        b'Conat="0" ForceHit="10" Parry="10" SkillScript="10,11" ResPath="001" ArmPath="" ClothPath="" '
        b'RejectType="" FireResi="0" WaterResi="0" ElectResi="0" WindResi="0" DarkResi="0" LightResi="0" '
        b'ReduceResi="0" ReduceResiAgainst="0" ResiPenetrate="0"/>'
        b'<GameHeroTempInfo TemplateId="1004" TemplateName="Dinah" HeroType="3" Job="2" Sexs="2" '
        b'Icon="/head_monster018a.jpg" Grades="1" AI="0" DefaultSkill="10000" Power="20" Agility="20" Intellect="30" '
        b'Captain="100" Physique="20" Attack="20" Defence="20" MagicAttack="30" MagicDefence="20" Live="250" '
        b'Conat="0" ForceHit="10" Parry="10" SkillScript="40180,40181" ResPath="monster018A" ArmPath="" ClothPath="" '
        b'RejectType="" FireResi="0" WaterResi="0" ElectResi="0" WindResi="0" DarkResi="0" LightResi="0" '
        b'ReduceResi="0" ReduceResiAgainst="0" ResiPenetrate="0"/>'
        b'<GameHeroTempInfo TemplateId="1005" TemplateName="Dinah" HeroType="3" Job="2" Sexs="2" '
        b'Icon="/head_monster018a.jpg" Grades="1" AI="0" DefaultSkill="10000" Power="20" Agility="20" Intellect="30" '
        b'Captain="100" Physique="20" Attack="20" Defence="20" MagicAttack="30" MagicDefence="20" Live="250" '
        b'Conat="0" ForceHit="10" Parry="10" SkillScript="40180,40181" ResPath="monster018A" ArmPath="" ClothPath="" '
        b'RejectType="" FireResi="0" WaterResi="0" ElectResi="0" WindResi="0" DarkResi="0" LightResi="0" '
        b'ReduceResi="0" ReduceResiAgainst="0" ResiPenetrate="0"/>'
    )

    thief_entries = b"".join(
        f'<GameHeroTempInfo TemplateId="{tid}" TemplateName="Master Treasure Thief" HeroType="3" Job="10" Sexs="0" Icon="/head_monster030.jpg" Grades="{50 + (tid - 72001) * 2}" AI="82031" DefaultSkill="10000" Power="0" Agility="0" Intellect="0" Captain="4" Physique="0" Attack="5000" Defence="500" MagicAttack="5000" MagicDefence="500" Live="50000" Conat="0" ForceHit="0" Parry="0" SkillScript="" ResPath="monster030" ArmPath="" ClothPath="" RejectType="19,13,100,38,39" FireResi="0" WaterResi="0" ElectResi="0" WindResi="0" DarkResi="0" LightResi="0" ReduceResi="0" ReduceResiAgainst="0" ResiPenetrate="0"/>'.encode()
        for tid in range(72001, 72015)
    )

    shop_entries = (
        b'<ShopTempInfo Id="602" ShopType="1" Area="2" ItemId="208002" Point="0" GiftToken="195" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="602" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="32" ShopType="100" Area="2" ItemId="2090101" Point="0" GiftToken="0" Gold="5000" ConsortiaOffer="0" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="32" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="90" ShopType="1" Area="2" ItemId="2040103" Point="35" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="90" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="625" ShopType="1" Area="2" ItemId="2040103" Point="0" GiftToken="35" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="625" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="327" ShopType="1" Area="2" ItemId="3270101" Point="80" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="327" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="324" ShopType="1" Area="2" ItemId="3240101" Point="80" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="324" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="325" ShopType="1" Area="2" ItemId="3250101" Point="80" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="325" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="326" ShopType="1" Area="2" ItemId="3260101" Point="80" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="326" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="871" ShopType="1" Area="7" ItemId="3037040" Point="0" GiftToken="395" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="871" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="5001" ShopType="5" Area="2" ItemId="208001" Point="20" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="26" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="5001" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="100" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="26" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="5002" ShopType="5" Area="2" ItemId="208002" Point="50" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="26" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="5002" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="100" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="26" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="5003" ShopType="5" Area="2" ItemId="2040101" Point="10" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="26" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="5003" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="100" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="26" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="5004" ShopType="5" Area="2" ItemId="2050101" Point="30" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="26" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="5004" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="100" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="26" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="5005" ShopType="5" Area="2" ItemId="2127001" Point="15" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="26" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="5005" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="100" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="26" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="5006" ShopType="5" Area="2" ItemId="2030101" Point="25" GiftToken="0" Gold="0" ConsortiaOffer="0" Honor="0" NeedGrades="26" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="5006" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="100" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="26" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="2000" ShopType="6" Area="61" ItemId="2160001" Point="0" GiftToken="0" Gold="600" ConsortiaOffer="0" Honor="0" NeedGrades="1" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="0" NeedMinVip="0" VIP0Count="-1" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="600" Discount="0" Price="0" Sort="2000" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
    )

    guild_shop_extras = (
        b'<ShopTempInfo Id="19" ShopType="2" Area="11" ItemId="2040106" Point="0" GiftToken="0" Gold="0" ConsortiaOffer="40" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="6" NeedMinVip="0" VIP0Count="500" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="6" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
        b'<ShopTempInfo Id="665" ShopType="2" Area="11" ItemId="2131064" Point="0" GiftToken="0" Gold="0" ConsortiaOffer="40" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="1" NeedMinVip="0" VIP0Count="5" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="7" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
    )

    compose_entries = (
        b'<ComposeTempInfo Id="1" Types="1" Material1="2129001" Count1="5" Material2="2128101" Count2="1" Material3="0" Count3="0" Material4="0" Count4="0" NeedMinLevel="20" NeedBuildingTemp="0" NewMaterial="1991011" Counts="1" NeedGold="10000" Property1="0" IsLearn="0"/>'
        b'<ComposeTempInfo Id="108" Types="5" Material1="1991081" Count1="1" Material2="2129600" Count2="150" Material3="2129601" Count3="15" Material4="0" Count4="0" NeedMinLevel="60" NeedBuildingTemp="0" NewMaterial="1891081" Counts="1" NeedGold="700000" Property1="0" IsLearn="0"/>'
        b'<ComposeTempInfo Id="344" Types="10" Material1="1130301" Count1="1" Material2="3240101" Count2="100" Material3="0" Count3="0" Material4="0" Count4="0" NeedMinLevel="1" NeedBuildingTemp="0" NewMaterial="1130401" Counts="1" NeedGold="10000" Property1="0" IsLearn="0"/>'
    )

    # Injetar LeedTemp (devoção diária)
    leed_temp_entries = (
        b'<LeedTempInfo TemplateId="1" PassCount="1" Num="5" Title="Daily Login" Desc="" RewardDesc="" Sort="1" Type="1" />'
        b'<LeedTempInfo TemplateId="4" PassCount="1" Num="5" Title="Complete a solo dungeon" Desc="" RewardDesc="" Sort="4" Type="1" />'
        b'<LeedTempInfo TemplateId="5" PassCount="1" Num="5" Title="Complete a multi-player dungeon" Desc="" RewardDesc="" Sort="5" Type="1" />'
        b'<LeedTempInfo TemplateId="8" PassCount="1" Num="5" Title="Practice Astral" Desc="" RewardDesc="" Sort="8" Type="1" />'
        b'<LeedTempInfo TemplateId="9" PassCount="1" Num="5" Title="Plunder mine" Desc="" RewardDesc="" Sort="9" Type="1" />'
        b'<LeedTempInfo TemplateId="10" PassCount="1" Num="5" Title="Plunder another player" Desc="" RewardDesc="" Sort="10" Type="1" />'
        b'<LeedTempInfo TemplateId="12" PassCount="2" Num="5" Title="Perform a guild blessing" Desc="" RewardDesc="" Sort="12" Type="1" />'
        b'<LeedTempInfo TemplateId="13" PassCount="1" Num="5" Title="Arena Party" Desc="" RewardDesc="" Sort="13" Type="1" />'
        b'<LeedTempInfo TemplateId="15" PassCount="1" Num="10" Title="Consume Balens/Bound Balens" Desc="" RewardDesc="" Sort="15" Type="1" />'
        b'<LeedTempInfo TemplateId="16" PassCount="1" Num="5" Title="Speak in world chat" Desc="" RewardDesc="" Sort="16" Type="1" />'
        b'<LeedTempInfo TemplateId="17" PassCount="1" Num="5" Title="Capture an Astral" Desc="" RewardDesc="" Sort="17" Type="1" />'
        b'<LeedTempInfo TemplateId="18" PassCount="1" Num="5" Title="Fight a World BOSS" Desc="" RewardDesc="" Sort="18" Type="1" />'
        b'<LeedTempInfo TemplateId="19" PassCount="10" Num="5" Title="Challenge another player" Desc="" RewardDesc="" Sort="19" Type="1" />'
        b'<LeedTempInfo TemplateId="20" PassCount="3" Num="5" Title="Complete a daily quest" Desc="" RewardDesc="" Sort="20" Type="1" />'
        b'<LeedTempInfo TemplateId="22" PassCount="1" Num="5" Title="Enter the Altar of Ennoblement" Desc="" RewardDesc="" Sort="22" Type="1" />'
        b'<LeedTempInfo TemplateId="23" PassCount="1" Num="5" Title="Enter Forgotten Catacombs" Desc="" RewardDesc="" Sort="23" Type="1" />'
        b'<LeedTempInfo TemplateId="24" PassCount="5" Num="5" Title="Complete Bounty Quest" Desc="" RewardDesc="" Sort="24" Type="1" />'
        b'<LeedTempInfo TemplateId="25" PassCount="1" Num="5" Title="Harvest from your own farm" Desc="" RewardDesc="" Sort="25" Type="1" />'
        b'<LeedTempInfo TemplateId="27" PassCount="1" Num="5" Title="Enter Battleground" Desc="" RewardDesc="" Sort="27" Type="1" />'
        b'<LeedTempInfo TemplateId="28" PassCount="1" Num="5" Title="Enter the Spire" Desc="" RewardDesc="" Sort="28" Type="1" />'
        b'<LeedTempInfo TemplateId="33" PassCount="1" Num="5" Title="Spin the Blessing Wheel" Desc="" RewardDesc="" Sort="33" Type="1" />'
    )

    mine_campaign = (
        b'<CampaignInfo CampaignId="30000" CampaignName="Amethyst Mine" Types="11" SonTypes="0" LandId="0" '
        b'DungeonId="0" AreaId="0" MinLevel="30" MaxLevel="100" PreCampaignId="0" NextCampaignId="0" '
        b'Capacity="10000" DifficultyGrade="1" Description="Amethyst Mine" CardPayment="0" PosX="0" PosY="0" '
        b'Item="" StandSecond="0" StandardDamage="0" StandardHurt="0" BaseGp="0" OpenTime="" StopTime="" '
        b'NeedTransfer="false" NeedFightPower="0" MapIds="" NeedChangeJob="false" NeedThirdTransfer="false" '
        b'NeedTransferType="0" EnterNumb="0" />'
    )

    battleground_campaigns = b"".join(
        f'<CampaignInfo CampaignId="{cid}" CampaignName="Campo de Batalha" Types="5" SonTypes="0" LandId="0" DungeonId="0" AreaId="0" MinLevel="30" MaxLevel="100" PreCampaignId="0" NextCampaignId="0" Capacity="30" DifficultyGrade="1" Description="Batalhando no Campo de Batalha receber\xc3\xa1 Honra e Ins\xc3\xadgnia" CardPayment="0" PosX="0" PosY="0" Item="" StandSecond="0" StandardDamage="0" StandardHurt="0" BaseGp="0" OpenTime="{h:02d}:00" StopTime="{h:02d}:25" NeedTransfer="false" NeedFightPower="0" MapIds="" NeedChangeJob="false" NeedThirdTransfer="false" NeedTransferType="0" EnterNumb="2" />'.encode()
        for cid, h in zip(range(4001, 4012), range(11, 22))
    )

    vip_prerogative_entries = (
        b''.join(f'<VipPrerogativeTempInfo id="{700+g}" name="Bonus Kyanite from Plunder" type="7" grade="{g}" para1="{500 if g >= 4 else 0}" para2="7" para3="0"/>'.encode() for g in range(1, 10))
        + b''.join(f'<VipPrerogativeTempInfo id="{800+g}" name="More Alchemy Attempts" type="8" grade="{g}" para1="{max(0, g - 2)}" para2="8" para3="0"/>'.encode() for g in range(1, 10))
        + b''.join(f'<VipPrerogativeTempInfo id="{900+g}" name="Add Daru Alchemy Attempts" type="9" grade="{g}" para1="{max(0, g - 2)}" para2="9" para3="0"/>'.encode() for g in range(1, 10))
        + b''.join(f'<VipPrerogativeTempInfo id="{1200+g}" name="VIP Daily Quests" type="12" grade="{g}" para1="1" para2="12" para3="0"/>'.encode() for g in range(1, 10))
        + b''.join(f'<VipPrerogativeTempInfo id="{1400+g}" name="Add Mystery Shop Attempts" type="14" grade="{g}" para1="{(g - 3) * 10 if g >= 4 else 0}" para2="14" para3="0"/>'.encode() for g in range(1, 10))
        + b''.join(f'<VipPrerogativeTempInfo id="{1700+g}" name="1-Click Blessing" type="17" grade="{g}" para1="1" para2="17" para3="0"/>'.encode() for g in range(1, 10))
    )

    fate_skill_entry = b'<SkillTempInfo TemplateId="2100" SonType="3000" Grades="0" TemplateName="Destino" SkillName="Destino" ActionEffectName="" Description="" ColdDown="0" AttackType="0" SkillType="0" LevelLimit="0" NeedCareer="0" NeedSp="0" CostRage="0" HurtRage="0" IsUse="0" UseDelay="0" DelayAttack="0" Icon="" Buffs="" Property1="0" Property2="0" Property3="0" Property4="0" Property5="0" Property6="0" Property7="0" Property8="0" Property9="0" Property10="0" Range="0" Target="0" ConsumeMaterial="0" ConsumeNumber="0" />'

    card_upgrade_entries = b"".join(
        f'<UpGradeTempInfo Id="{90000000 + t * 100 + g}" Types="{t}" TemplateId="0" TemplateName="Card Grade" Grades="{g}" Data="{10 * (g - 1)}" ActiveObject="0"/>'.encode()
        for t in range(30, 35)
        for g in range(1, 11)
    )

    powcards_entries = (
        b'<PowcardTempInfo TemplateId="10001" TemplateName="Card 10001" SuiteId="1000" SonType="1" BufId="3040" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10002" TemplateName="Card 10002" SuiteId="1000" SonType="1" BufId="3020" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10003" TemplateName="Card 10003" SuiteId="1000" SonType="1" BufId="3000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10011" TemplateName="Card 10011" SuiteId="1001" SonType="1" BufId="4060" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10012" TemplateName="Card 10012" SuiteId="1001" SonType="1" BufId="4020" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10013" TemplateName="Card 10013" SuiteId="1001" SonType="1" BufId="4000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10015" TemplateName="Card 10015" SuiteId="1002" SonType="1" BufId="6000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10016" TemplateName="Card 10016" SuiteId="1002" SonType="1" BufId="6000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10017" TemplateName="Card 10017" SuiteId="1002" SonType="1" BufId="6000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10018" TemplateName="Card 10018" SuiteId="1002" SonType="1" BufId="6000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10019" TemplateName="Card 10019" SuiteId="1003" SonType="1" BufId="7000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10020" TemplateName="Card 10020" SuiteId="1003" SonType="1" BufId="7000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10021" TemplateName="Card 10021" SuiteId="1003" SonType="1" BufId="7000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10023" TemplateName="Card 10023" SuiteId="1004" SonType="1" BufId="8000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10024" TemplateName="Card 10024" SuiteId="1004" SonType="1" BufId="8000" Profile="1" fixvalue="0" percent="0" />'
        b'<PowcardTempInfo TemplateId="10025" TemplateName="Card 10025" SuiteId="1004" SonType="1" BufId="8000" Profile="1" fixvalue="0" percent="0" />'
    )
    powcard_suites_entries = (
        b'<PowCardSuiteTemInfo TemplateId="1000" TemplateName="Deck 1000" Template3s="0" Property3="0" Template4s="0" Property4="0" Template5s="0" Property5="0" fixvalue="0" percent="0" />'
        b'<PowCardSuiteTemInfo TemplateId="1001" TemplateName="Deck 1001" Template3s="0" Property3="0" Template4s="0" Property4="0" Template5s="0" Property5="0" fixvalue="0" percent="0" />'
        b'<PowCardSuiteTemInfo TemplateId="1002" TemplateName="Deck 1002" Template3s="1004" Property3="40001" Template4s="1004" Property4="40002" Template5s="0" Property5="0" fixvalue="0" percent="0" />'
        b'<PowCardSuiteTemInfo TemplateId="1003" TemplateName="Deck 1003" Template3s="0" Property3="0" Template4s="0" Property4="0" Template5s="0" Property5="0" fixvalue="0" percent="0" />'
        b'<PowCardSuiteTemInfo TemplateId="1004" TemplateName="Deck 1004" Template3s="0" Property3="0" Template4s="0" Property4="0" Template5s="0" Property5="0" fixvalue="0" percent="0" />'
    )
    card_buffer_entries = (
        b'<CampaignBufferTemp TemplateId="3041" Types="800" Attack="0" Defence="0" MagicAttack="0" MagicDefence="0" Live="600" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="3020" Types="800" Attack="80" Defence="40" MagicAttack="80" MagicDefence="40" Live="0" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="3000" Types="800" Attack="80" Defence="40" MagicAttack="80" MagicDefence="40" Live="0" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="4061" Types="802" Attack="0" Defence="0" MagicAttack="0" MagicDefence="0" Live="600" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="4020" Types="802" Attack="80" Defence="40" MagicAttack="80" MagicDefence="40" Live="0" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="4000" Types="802" Attack="80" Defence="40" MagicAttack="80" MagicDefence="40" Live="0" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="40001" Types="806" Attack="400" Defence="200" MagicAttack="400" MagicDefence="200" Live="1505" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="40002" Types="806" Attack="400" Defence="200" MagicAttack="400" MagicDefence="200" Live="1505" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="6001" Types="0" Attack="0" Defence="0" MagicAttack="0" MagicDefence="0" Live="0" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="6000" Types="0" Attack="0" Defence="0" MagicAttack="0" MagicDefence="0" Live="0" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="7001" Types="807" Attack="100" Defence="50" MagicAttack="100" MagicDefence="50" Live="395" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="7000" Types="0" Attack="0" Defence="0" MagicAttack="0" MagicDefence="0" Live="0" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="8001" Types="801" Attack="100" Defence="50" MagicAttack="100" MagicDefence="50" Live="395" Crit="0" Block="0" Leadpawn="0" />'
        b'<CampaignBufferTemp TemplateId="8000" Types="0" Attack="0" Defence="0" MagicAttack="0" MagicDefence="0" Live="0" Crit="0" Block="0" Leadpawn="0" />'
    )
    boss_buffer_entries = b"".join(
        f'<CampaignBufferTemp TemplateId="{400+g}" Types="4" Attack="{5*g}" Defence="{5*g}" MagicAttack="{5*g}" MagicDefence="{5*g}" Live="{5*g}" Crit="0" Block="0" Leadpawn="0" />'.encode()
        for g in range(1, 21)
    )
    item_21261044 = (
        b'<ItemTempInfo TemplateId="21261044" MasterType="2" SonType="206" Sexs="2" NeedGrades="1" MaxCount="999" '
        b'TemplateName="Pacote de Evento" Job="0" Refresh="0" Icon="/gift_001.png" Description="Pacote de evento" '
        b'Profile="2" SellGold="100" DefaultSkill="" Avata="" StrengthenMax="0" RandomSkillCount="0" SuiteId="0" '
        b'StartingPrice="0" TransformId="0" IsCanBatch="true" Feed="0" NeedChangeJob="0" Property1="0" Property2="0"/>'
    )
    simple_tasks_entries = (
        b'<SimpleTask TaskId="1" Type="1" IParam1="10" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Upgrade pawn to Lvl. 10" />'
        b'<SimpleTask TaskId="2" Type="2" IParam1="3" IParam2="3" IParam3="0" IParam4="0" IParam5="0" Detail="3 Guild skills reach Lvl. 3" />'
        b'<SimpleTask TaskId="3" Type="3" IParam1="10" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Upgrade technology to Lvl. 10" />'
        b'<SimpleTask TaskId="4" Type="4" IParam1="30" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Reach Lvl. 30" />'
        b'<SimpleTask TaskId="5" Type="5" IParam1="1" IParam2="3" IParam3="0" IParam4="0" IParam5="0" Detail="Equip 1 Blue Astral" />'
        b'<SimpleTask TaskId="6" Type="6" IParam1="1" IParam2="0" IParam3="30" IParam4="0" IParam5="0" Detail="Equip 1 Lvl. 30 item" />'
        b'<SimpleTask TaskId="7" Type="7" IParam1="40" IParam2="5" IParam3="20" IParam4="0" IParam5="0" Detail="Strengthen item to 20" />'
        b'<SimpleTask TaskId="8" Type="8" IParam1="1" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Pass Catacombs" />'
        b'<SimpleTask TaskId="9" Type="9" IParam1="3" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Upgrade Astral to Lvl. 3" />'
        b'<SimpleTask TaskId="10" Type="10" IParam1="8" IParam2="1" IParam3="0" IParam4="0" IParam5="0" Detail="Socket 8 Lvl. 1+ Gems" />'
        b'<SimpleTask TaskId="11" Type="11" IParam1="1" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Learn Rune" />'
        b'<SimpleTask TaskId="12" Type="12" IParam1="1" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Get Mount" />'
        b'<SimpleTask TaskId="13" Type="7" IParam1="40" IParam2="5" IParam3="20" IParam4="0" IParam5="0" Detail="Strengthen item to 20" />'
        b'<SimpleTask TaskId="14" Type="2" IParam1="3" IParam2="3" IParam3="0" IParam4="0" IParam5="0" Detail="3 Guild skills reach Lvl. 3" />'
        b'<SimpleTask TaskId="15" Type="10" IParam1="1" IParam2="3" IParam3="0" IParam4="0" IParam5="0" Detail="Socket 1 Lvl. 3+ Gem" />'
        b'<SimpleTask TaskId="16" Type="13" IParam1="9004" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Pass Campaign 9004" />'
        b'<SimpleTask TaskId="17" Type="14" IParam1="500" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Guild Devotion 500" />'
        b'<SimpleTask TaskId="18" Type="15" IParam1="100" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Astral Value 100" />'
        b'<SimpleTask TaskId="19" Type="16" IParam1="8" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Soul Engraving Lvl. 8" />'
        b'<SimpleTask TaskId="20" Type="13" IParam1="9104" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Pass Campaign 9104" />'
        b'<SimpleTask TaskId="21" Type="11" IParam1="1" IParam2="3" IParam3="0" IParam4="0" IParam5="0" Detail="Upgrade Rune to Lvl. 3" />'
        b'<SimpleTask TaskId="22" Type="22" IParam1="5000" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Battle Rating 5000" />'
        b'<SimpleTask TaskId="23" Type="12" IParam1="2" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Mount Soul Lvl. 2" />'
        b'<SimpleTask TaskId="24" Type="17" IParam1="1" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Talent" />'
        b'<SimpleTask TaskId="25" Type="21" IParam1="2000" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Private Title" />'
        b'<SimpleTask TaskId="26" Type="22" IParam1="10000" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Battle Rating 10000" />'
        b'<SimpleTask TaskId="27" Type="21" IParam1="2000" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Private Title" />'
        b'<SimpleTask TaskId="28" Type="13" IParam1="9105" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Pass Campaign 9105" />'
        b'<SimpleTask TaskId="29" Type="23" IParam1="1" IParam2="0" IParam3="0" IParam4="0" IParam5="0" Detail="Spire" />'
    )

    mine_physics_entries = b"".join(
        f'<MapPhysicsTempInfo TemplateId="{200400 + lvl}" MapPhysicsTempName="Mina de Ouro" MasterType="20" SonType="2006" Grades="{lvl}" RefreshTime="43200" Property1="1" Property2="1" Property3="0" Property4="{lvl * 40}" Property5="0" Property6="0" Description="Mina de Ouro" HeroGP="0"/>'.encode("utf-8")
        for lvl in range(1, 61)
    )

    new_tables: list[tuple[str, bytes]] = []
    injected_maps = False
    injected_camps = False
    injected_pawns = False
    injected_heroes = False

    for name, xml_data in tables:
        if name == "MapInfos":
            target = b'<MapInfo Id="10002"'
            if target in xml_data:
                xml_data = xml_data.replace(target, map_entry + target, 1)
                injected_maps = True
                print("Injected 10001 into MapInfos!")
            map_levels = {
                b'1': (b'11', b'20'),
                b'2': (b'21', b'30'),
                b'3': (b'31', b'40'),
                b'4': (b'41', b'50'),
                b'5': (b'51', b'60'),
            }
            for mid, (min_lvl, max_lvl) in map_levels.items():
                prefix = b'<MapInfo Id="' + mid + b'" CampaignId="0"'
                idx = xml_data.find(prefix)
                if idx != -1:
                    end = xml_data.find(b'/>', idx) + 2
                    chunk = xml_data[idx:end].replace(b'Width="10000" Height="10000"', b'Width="80000" Height="80000"').replace(b'MinLevel="1" MaxLevel="999"', b'MinLevel="' + min_lvl + b'" MaxLevel="' + max_lvl + b'"')
                    xml_data = xml_data[:idx] + chunk + xml_data[end:]
        elif name == "Campaigns":
            target = b'<CampaignInfo CampaignId="10002"'
            if target in xml_data:
                xml_data = xml_data.replace(target, camp_entry + target, 1)
                injected_camps = True
                print("Injected 10001 into Campaigns!")
            if b'CampaignId="4001"' not in xml_data:
                xml_data = xml_data.replace(b"<Campaigns>", b"<Campaigns>" + battleground_campaigns, 1)
                print("Injected battleground campaigns (4001-4011) into Campaigns!")
            if b'CampaignId="30000"' not in xml_data:
                xml_data = xml_data.replace(b"<Campaigns>", b"<Campaigns>" + mine_campaign, 1)
                print("Injected mine 30000 into Campaigns!")
            xml_data = xml_data.replace(b'CampaignId="5001" CampaignName="Rei dos Lobos"', b'CampaignId="5001" CampaignName="Bloodfang"')
            xml_data = xml_data.replace(b'CampaignId="5001" CampaignName="Bloodfang" Types="1" SonTypes="0" LandId="0" DungeonId="0" AreaId="0" MinLevel="20" MaxLevel="100" PreCampaignId="0" NextCampaignId="0" Capacity="10000" DifficultyGrade="1" Description="Batalhando o Chef\xc3\xa3o Global receber\xc3\xa1 Ouro e Esp\xc3\xadrito" CardPayment="0" PosX="0" PosY="0" Item="" StandSecond="0" StandardDamage="0" StandardHurt="0" BaseGp="0" OpenTime="11:00" StopTime="12:00"',
                                        b'CampaignId="5001" CampaignName="Bloodfang" Types="1" SonTypes="0" LandId="0" DungeonId="0" AreaId="0" MinLevel="20" MaxLevel="100" PreCampaignId="0" NextCampaignId="0" Capacity="10000" DifficultyGrade="1" Description="Batalhando o Chef\xc3\xa3o Global receber\xc3\xa1 Ouro e Esp\xc3\xadrito" CardPayment="0" PosX="0" PosY="0" Item="" StandSecond="0" StandardDamage="0" StandardHurt="0" BaseGp="0" OpenTime="11:35" StopTime="12:35"')
        elif name == "MarrySpecTempInfos":
            xml_data = xml_data.replace(
                b'Path="34,81|41,88|163,88|194,119|194,144|209,159|278,159|278,135|262,119|194,119|163,88|41,88|34,81"',
                b'Path="171,72|41,88|163,88|194,119|194,144|209,159|278,159|278,135|262,119|194,119|163,88|41,88|34,81"'
            )
            print("Fixed MarrySpecTempInfos 1 path starting with 171,72|!")
        elif name == "PawnTempInfos":
            target = b'<PawnTempInfo TemplateId="2006"'
            if target in xml_data:
                xml_data = xml_data.replace(target, pawn_entries + target, 1)
                injected_pawns = True
                print("Injected tutorial pawns (1001, 2001, 2002, 2003) into PawnTempInfos!")
        elif name == "GameHeroTemp":
            target = b'<GameHeroTempInfo TemplateId="1"'
            if target in xml_data:
                xml_data = xml_data.replace(target, hero_entries + target, 1)
                injected_heroes = True
                print("Injected tutorial heroes (1002, 1003, 1004, 1005) into GameHeroTemp!")
            if b'TemplateId="72001"' not in xml_data:
                xml_data = xml_data.replace(b"<GameHeroTemp>", b"<GameHeroTemp>" + thief_entries, 1)
                print("Injected thieves (72001-72014) into binary GameHeroTemp!")
            xml_data = xml_data.replace(b'TemplateId="1011" TemplateName="Lobo Maligno"', b'TemplateId="1011" TemplateName="Wulfgar"')
        elif name == "ItemTempInfos":
            xml_data = xml_data.replace(b'TemplateId="1011002" MasterType="1" SonType="101" Sexs="1" NeedGrades="1" MaxCount="1" TemplateName="Espada dos Espadachins" Job="1" Refresh="0" Icon="/sword_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70102" Avata=""',
                                       b'TemplateId="1011002" MasterType="1" SonType="101" Sexs="1" NeedGrades="1" MaxCount="1" TemplateName="Espada dos Espadachins" Job="1" Refresh="0" Icon="/sword_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70102" Avata="/warrior_arms002"')
            xml_data = xml_data.replace(b'TemplateId="1012002" MasterType="1" SonType="101" Sexs="1" NeedGrades="1" MaxCount="1" TemplateName="Arco Huno do Santu\xc3\xa1rio" Job="2" Refresh="0" Icon="/crossbows_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70202" Avata=""',
                                       b'TemplateId="1012002" MasterType="1" SonType="101" Sexs="1" NeedGrades="1" MaxCount="1" TemplateName="Arco Huno do Santu\xc3\xa1rio" Job="2" Refresh="0" Icon="/crossbows_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70202" Avata="/ranger_arms002"')
            xml_data = xml_data.replace(b'TemplateId="1013002" MasterType="1" SonType="101" Sexs="2" NeedGrades="1" MaxCount="1" TemplateName="Bast\xc3\xa3o do Santu\xc3\xa1rio" Job="3" Refresh="0" Icon="/rod_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70302" Avata=""',
                                       b'TemplateId="1013002" MasterType="1" SonType="101" Sexs="2" NeedGrades="1" MaxCount="1" TemplateName="Bast\xc3\xa3o do Santu\xc3\xa1rio" Job="3" Refresh="0" Icon="/rod_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70302" Avata="/wizard_arms002"')
            xml_data = xml_data.replace(b'TemplateId="208015" MasterType="2" SonType="292" Sexs="2" NeedGrades="1" MaxCount="9999" TemplateName="Moeda VIP"',
                                       b'TemplateId="208015" MasterType="2" SonType="292" Sexs="2" NeedGrades="1" MaxCount="9999" TemplateName="VIP Token"')
            xml_data = xml_data.replace(b'TemplateId="2030701" MasterType="2" SonType="203" Sexs="2" NeedGrades="20"',
                                       b'TemplateId="2030701" MasterType="2" SonType="203" Sexs="2" NeedGrades="1"')
            xml_data = xml_data.replace(b'TemplateId="2030703" MasterType="2" SonType="203" Sexs="2" NeedGrades="40"',
                                       b'TemplateId="2030703" MasterType="2" SonType="203" Sexs="2" NeedGrades="1"')
            xml_data = xml_data.replace(b'TemplateId="2090101" MasterType="2" SonType="208" Sexs="2" NeedGrades="11" MaxCount="9999" TemplateName="Bolsa de Sangue B\xc3\xa1sico" Job="0" Refresh="0" Icon="/blood_01.png" Description="Itens desnecess\xc3\xa1rios" Profile="2" SellGold="500" DefaultSkill="" Avata="" StrengthenMax="0" RandomSkillCount="0" SuiteId="0" StartingPrice="5" TransformId="0" IsCanBatch="false" Feed="0" NeedChangeJob="0"',
                                       b'TemplateId="2090101" MasterType="2" SonType="209" Sexs="2" NeedGrades="11" MaxCount="9999" TemplateName="Bolsa de Sangue B\xc3\xa1sico" Job="0" Refresh="0" Icon="/blood_01.png" Description="Restaura 10.000 HP" Profile="2" SellGold="500" DefaultSkill="" Avata="" StrengthenMax="0" RandomSkillCount="0" SuiteId="0" StartingPrice="5" TransformId="0" IsCanBatch="false" Feed="0" NeedChangeJob="0" Property1="10000" Property2="0"')
            xml_data = xml_data.replace(b'TemplateId="208068" MasterType="2" SonType="219"', b'TemplateId="208068" MasterType="2" SonType="208"')
            xml_data = xml_data.replace(b'TemplateId="2131055" MasterType="2" SonType="208"', b'TemplateId="2131055" MasterType="2" SonType="316"')
            for mid in (b'2190001', b'2190002', b'2190003', b'2190004'):
                xml_data = xml_data.replace(b'TemplateId="' + mid + b'" MasterType="2" SonType="208"', b'TemplateId="' + mid + b'" MasterType="2" SonType="219"')
            if b'TemplateId="21261044"' not in xml_data:
                xml_data = xml_data.replace(b"<ItemTempInfos>", b"<ItemTempInfos>" + item_21261044, 1)
                print("Injected item 21261044 into binary ItemTempInfos!")
            print("Injected weapon Avata, VIP Token name and EXP Book level into ItemTempInfos!")
        elif name == "MapPhysicsTempInfos":
            if b'SonType="2006"' not in xml_data:
                xml_data = xml_data.replace(b"<MapPhysicsTempInfos>", b"<MapPhysicsTempInfos>" + mine_physics_entries, 1)
                print("Injected mine physics entries into binary MapPhysicsTempInfos!")
        elif name == "SkillBufferTempInfos":
            if b'Id="41"' not in xml_data:
                stun_entry = b'<SkillBufferTempInfo Id="41" BufferName="Atordoado" AttackType="19" ValidCount="1" AttackWay="0" CountWay="1" Description="Stunned - Movement inhibited" Icon="" IsDisplay="true" MasterType="0" NoticeType="0" Priority="0" PropertyType="0" ReplaceType="0" ReviveWay="0" SonType="0" Type="0" Value="0" ValuePercent="0"/>'
                xml_data = xml_data.replace(b"<SkillBufferTempInfos>", b"<SkillBufferTempInfos>" + stun_entry, 1)
                print("Injected stun buffer 41 into binary SkillBufferTempInfos!")
        elif name == "ConfigInfos":
            xml_data = xml_data.replace(b'ConfigName="ShopBuy_MaxCount" ConfigValue="3"', b'ConfigName="ShopBuy_MaxCount" ConfigValue="20"')
            xml_data = xml_data.replace(b'ConfigName="Mount_Point" ConfigValue="5"', b'ConfigName="Mount_Point" ConfigValue="35"')
            xml_data = xml_data.replace(b'ConfigName="pet_up_quality" ConfigValue="5"', b'ConfigName="pet_up_quality" ConfigValue="35"')
            xml_data = xml_data.replace(b'ConfigName="swallow_fullgp_points" ConfigValue="50"', b'ConfigName="swallow_fullgp_points" ConfigValue="295"')
            xml_data = xml_data.replace(b'ConfigName="pet_island_defend_rage_add" ConfigValue="4,10"', b'ConfigName="pet_island_defend_rage_add" ConfigValue="2,5"')
            xml_data = xml_data.replace(b'ConfigName="MatchOfVehicleTime" ConfigValue="16:00,16:25"', b'ConfigName="MatchOfVehicleTime" ConfigValue="10:00,10:25|16:00,16:25"')
            xml_data = xml_data.replace(b'ConfigName="Consortia_ClearCD_Point" ConfigValue="50"', b'ConfigName="Consortia_ClearCD_Point" ConfigValue="395"')
            print("Updated ConfigInfos (ShopBuy_MaxCount=20, Mount_Point=35, pet_up_quality=35, swallow_fullgp_points=295, pet_island_defend_rage_add=2,5, MatchOfVehicleTime=10:00,10:25|16:00,16:25, Consortia_ClearCD_Point=395)!")
        elif name == "VehicleObjectTempInfos":
            xml_data = xml_data.replace(b'TemplateId="2" TemplateName="Mina de F\xc3\xbaria" Attack="150" NeedDiamond="200"', b'TemplateId="2" TemplateName="Mina de F\xc3\xbaria" Attack="150" NeedDiamond="0"')
            xml_data = xml_data.replace(b'TemplateId="3" TemplateName="Lobo Silencioso" Attack="170" NeedDiamond="500" Defence="60" Hp="6500" Dodge="5" GeniusSkill="1003" NormalSkill="1" Description="Lobo Silencioso" Avatar="/vehicle_3" NeedGrades="0"', b'TemplateId="3" TemplateName="Lobo Silencioso" Attack="170" NeedDiamond="1000" Defence="60" Hp="6500" Dodge="5" GeniusSkill="1003" NormalSkill="1" Description="Lobo Silencioso" Avatar="/vehicle_3" NeedGrades="365"')
            print("Updated VehicleObjectTempInfos (FREE=2, PAID=3 with NeedGrades=365)!")
        elif name == "VipPrerogativeTempInfos":
            if b'type="14"' not in xml_data:
                xml_data = xml_data.replace(b"<VipPrerogativeTempInfos>", b"<VipPrerogativeTempInfos>" + vip_prerogative_entries, 1)
                print("Injected missing VIP prerogatives into binary VipPrerogativeTempInfos!")
        elif name == "ShopTempInfos":
            xml_data = xml_data.replace(b'Id="602" ShopType="1" Area="2" ItemId="208002" Point="50"', b'Id="602" ShopType="1" Area="2" ItemId="208002" Point="0"')
            guild_shop_extras = (
                b'<ShopTempInfo Id="19" ShopType="2" Area="11" ItemId="2040106" Point="0" GiftToken="0" Gold="0" ConsortiaOffer="40" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="6" NeedMinVip="0" VIP0Count="500" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="6" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
                b'<ShopTempInfo Id="665" ShopType="2" Area="11" ItemId="2131064" Point="0" GiftToken="0" Gold="0" ConsortiaOffer="40" Honor="0" NeedGrades="0" MazeCoin="0" MazeLayers="0" MazeLayers2="0" NeedConsortiaLevels="1" NeedMinVip="0" VIP0Count="5" VIP1Count="-1" VIP2Count="-1" VIP3Count="-1" VIP4Count="-1" VIP5Count="-1" VIP6Count="-1" FirstPrice="0" Discount="0" Price="0" Sort="7" IsHot="false" Labels="1" ValidDate="0" NeedGeste="0" Rands="0" Score="0" LordsScore="0" NeedItem="0" MineScore="0" NeedMinGrade="0" NeedMaxGrade="0" CrossGuildScore="0" CrossLeagueMedal="0" PokerScore="0" SellMaxCount="0"/>'
            )
            if b'Id="19"' not in xml_data:
                xml_data = xml_data.replace(b"<ShopTempInfos>", b"<ShopTempInfos>" + guild_shop_extras, 1)
                print("Injected guild shop items 19 and 665 into binary ShopTempInfos!")
            if b'ItemId="2160001"' not in xml_data:
                xml_data = xml_data.replace(b"<ShopTempInfos>", b"<ShopTempInfos>" + shop_entries, 1)
                print("Injected custom shop entries into binary ShopTempInfos!")
        elif name == "ComposeTempInfos":
            if b'Id="1"' not in xml_data:
                xml_data = xml_data.replace(b"<ComposeTempInfos>", b"<ComposeTempInfos>" + compose_entries, 1)
                print("Injected custom compose entries into binary ComposeTempInfos!")
        elif name == "BuildingTempInfos":
            xml_data = fix_building_population(xml_data)
            print("Fixed house population in binary BuildingTempInfos!")
        elif name == "MountTempInfos":
            xml_data = xml_data.replace(
                b'TemplateId="1103" TemplateName="Alpaca Dem\xc3\xb4nio" MountType="1" Power="15" Intellect="15" Physique="15" Agility="15"',
                b'TemplateId="1103" TemplateName="Alpaca Dem\xc3\xb4nio" MountType="1" Power="10" Intellect="10" Physique="10" Agility="10"'
            )
            print("Fixed Mount 1103 base stats in binary MountTempInfos!")
        elif name == "SkillTempInfos":
            if b'TemplateId="2100"' not in xml_data:
                xml_data = xml_data.replace(b"<SkillTempInfos>", b"<SkillTempInfos>" + fate_skill_entry, 1)
                print("Injected Fate skill 2100 SonType 3000 into binary SkillTempInfos!")
        elif name == "UpGradeTempInfos":
            if b'TemplateName="Card Grade"' not in xml_data:
                xml_data = xml_data.replace(b"<UpGradeTempInfos>", b"<UpGradeTempInfos>" + card_upgrade_entries, 1)
                print("Injected card upgrades into binary UpGradeTempInfos!")
            xml_data = xml_data.replace(b'<UpGradeTempInfo Id="30009" Types="3" TemplateId="0" TemplateName="" Grades="9" Data="10800" ActiveObject="0"',
                                        b'<UpGradeTempInfo Id="30009" Types="3" TemplateId="0" TemplateName="" Grades="9" Data="10800" ActiveObject="30101"')
        elif name == "TimeDrop":
            if b'DropId="10005"' not in xml_data:
                xml_data = xml_data.replace(b"<TimeDrop>", b"<TimeDrop>" + b'<TimeDrop DropId="10005" Grade="5" TemplateId="2090102" Data="1" Job="0" ValidDate="0"/>', 1)
                print("Injected blood bag into binary TimeDrop!")
        elif name == "CampaignBufferTemps":
            xml_data = xml_data.replace(b"<CampaignBufferTemps>", b"<CampaignBufferTemps>" + card_buffer_entries + boss_buffer_entries, 1)
            print("Injected card & boss buffers into binary CampaignBufferTemps!")
        elif name in ("MapNodeInfos", "QuestTemps", "QuestCondictionInfos"):
            xml_data = fix_quest_and_nodes_xml(xml_data)
            print(f"Applied quest & node fixes to binary {name}!")
        elif name == "QuestGoods":
            entry_863 = b'<QuestGood TemplateId="863" RewardItemID="208015" IsSelect="false" RewardItemCount="10" ToJob="0" ValidDate="0"/>'
            entry_9 = b'<QuestGood TemplateId="9" RewardItemID="2060013" IsSelect="false" RewardItemCount="1" ToJob="0" ValidDate="0"/><QuestGood TemplateId="9" RewardItemID="208005" IsSelect="false" RewardItemCount="2" ToJob="0" ValidDate="0"/>'
            if b'TemplateId="863"' not in xml_data:
                xml_data = xml_data.replace(b"<QuestGoods>", b"<QuestGoods>" + entry_863, 1)
                print("Injected QuestGood 863 into binary QuestGoods!")
            if b'TemplateId="9"' not in xml_data:
                xml_data = xml_data.replace(b"<QuestGoods>", b"<QuestGoods>" + entry_9, 1)
                print("Injected QuestGood 9 into binary QuestGoods!")
        new_tables.append((name, xml_data))

    assert injected_maps and injected_camps and injected_pawns and injected_heroes, "Falha na injeção!"

    leed_full = b"<LeedTemp>" + leed_temp_entries + b"</LeedTemp>"
    found_leed = False
    for i, (name, _) in enumerate(new_tables):
        if name == "LeedTemp":
            new_tables[i] = ("LeedTemp", leed_full)
            found_leed = True
            break
    if not found_leed:
        new_tables.append(("LeedTemp", leed_full))
        print("Injected LeedTemp table into binary tables!")

    # Injetar PowcardTempInfos, PowCardSuiteTemInfos, SimpleTasks nas tabelas binárias
    new_tables.append(("PowcardTempInfos", b"<PowcardTempInfos>" + powcards_entries + b"</PowcardTempInfos>"))
    new_tables.append(("PowCardSuiteTemInfos", b"<PowCardSuiteTemInfos>" + powcard_suites_entries + b"</PowCardSuiteTemInfos>"))
    new_tables.append(("SimpleTasks", b"<SimpleTasks>" + simple_tasks_entries + b"</SimpleTasks>"))
    print("Injected PowcardTempInfos, PowCardSuiteTemInfos, SimpleTasks into binary tables!")

    import xml.etree.ElementTree as ET
    for name, xml_data in new_tables:
        try:
            ET.fromstring(xml_data)
        except Exception as e:
            raise ValueError(f"Table {name} is NOT valid XML: {e}")
    print(f"ALL {len(new_tables)} tables verified as 100% valid XML documents!")

    buf = bytearray()
    buf.extend(struct.pack(">I", version))
    for name, xml_data in new_tables:
        name_bytes = name.encode("utf-8")
        buf.append(len(name_bytes))
        buf.extend(name_bytes)
        buf.extend(struct.pack(">i", len(xml_data)))
        buf.extend(xml_data)

    decompressed_new = bytes(buf)
    print(f"New decompressed size: {len(decompressed_new)} bytes")

    # Validar que simula shiftTempInfo perfeitamente
    test_offset = 4
    parsed_count = 0
    while test_offset < len(decompressed_new):
        nlen = decompressed_new[test_offset]
        test_offset += 1
        test_offset += nlen
        xlen = struct.unpack(">i", decompressed_new[test_offset : test_offset + 4])[0]
        test_offset += 4
        test_offset += xlen
        parsed_count += 1

    assert test_offset == len(decompressed_new), f"Offset mismatch! {test_offset} vs {len(decompressed_new)}"
    assert parsed_count == len(new_tables), f"Count mismatch! {parsed_count} vs {len(new_tables)}"
    print(f"ShiftTempInfo simulation SUCCESS! All {parsed_count} tables cleanly parsed without trailing bytes.")

    compressed = zlib.compress(decompressed_new, level=9)
    cdn_payload = struct.pack(">I", len(compressed)) + compressed

    for p in ["bundled_cdn/xml/tempinfos.xml", "data/cdn/xml/tempinfos.xml"]:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(cdn_payload)
        print(f"Saved {len(cdn_payload)} bytes to {p}")

    tpl_path = "data/templates/tempinfos.xml"
    tpl_data = open(tpl_path, "rb").read()
    if tpl_data[:1] == b"\x78":
        tpl_raw = zlib.decompress(tpl_data)
    else:
        tpl_raw = tpl_data

    if b'<MapInfo Id="10001"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<MapInfo Id="10002"', map_entry + b'<MapInfo Id="10002"', 1)
    if b'<CampaignInfo CampaignId="10001"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<CampaignInfo CampaignId="10002"', camp_entry + b'<CampaignInfo CampaignId="10002"', 1)
    if b'<PawnTempInfo TemplateId="2001"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<PawnTempInfo TemplateId="2006"', pawn_entries + b'<PawnTempInfo TemplateId="2006"', 1)
    if b'<GameHeroTempInfo TemplateId="1002"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<GameHeroTempInfo TemplateId="1"', hero_entries + b'<GameHeroTempInfo TemplateId="1"', 1)

    # Injetar ou atualizar LeedTemp no tpl_raw do Python
    leed_tag = b"<LeedTemp>" + leed_temp_entries + b"</LeedTemp>"
    if b"<LeedTemp>" in tpl_raw:
        start = tpl_raw.find(b"<LeedTemp>")
        end = tpl_raw.find(b"</LeedTemp>") + len(b"</LeedTemp>")
        tpl_raw = tpl_raw[:start] + leed_tag + tpl_raw[end:]
        print("Updated <LeedTemp> in tpl_raw!")
    else:
        tpl_raw = tpl_raw.replace(b"</root>", leed_tag + b"</root>", 1)
        print("Injected <LeedTemp> into tpl_raw!")

    # Injetar Avata das armas no tpl_raw
    tpl_raw = tpl_raw.replace(b'TemplateId="1011002" MasterType="1" SonType="101" Sexs="1" NeedGrades="1" MaxCount="1" TemplateName="Espada dos Espadachins" Job="1" Refresh="0" Icon="/sword_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70102" Avata=""',
                             b'TemplateId="1011002" MasterType="1" SonType="101" Sexs="1" NeedGrades="1" MaxCount="1" TemplateName="Espada dos Espadachins" Job="1" Refresh="0" Icon="/sword_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70102" Avata="/warrior_arms002"')
    tpl_raw = tpl_raw.replace(b'TemplateId="1012002" MasterType="1" SonType="101" Sexs="1" NeedGrades="1" MaxCount="1" TemplateName="Arco Huno do Santu\xc3\xa1rio" Job="2" Refresh="0" Icon="/crossbows_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70202" Avata=""',
                             b'TemplateId="1012002" MasterType="1" SonType="101" Sexs="1" NeedGrades="1" MaxCount="1" TemplateName="Arco Huno do Santu\xc3\xa1rio" Job="2" Refresh="0" Icon="/crossbows_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70202" Avata="/ranger_arms002"')
    tpl_raw = tpl_raw.replace(b'TemplateId="1013002" MasterType="1" SonType="101" Sexs="2" NeedGrades="1" MaxCount="1" TemplateName="Bast\xc3\xa3o do Santu\xc3\xa1rio" Job="3" Refresh="0" Icon="/rod_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70302" Avata=""',
                             b'TemplateId="1013002" MasterType="1" SonType="101" Sexs="2" NeedGrades="1" MaxCount="1" TemplateName="Bast\xc3\xa3o do Santu\xc3\xa1rio" Job="3" Refresh="0" Icon="/rod_002.png" Description="" Profile="2" SellGold="150" DefaultSkill="70302" Avata="/wizard_arms002"')
    tpl_raw = tpl_raw.replace(b'TemplateId="208015" MasterType="2" SonType="292" Sexs="2" NeedGrades="1" MaxCount="9999" TemplateName="Moeda VIP"',
                             b'TemplateId="208015" MasterType="2" SonType="292" Sexs="2" NeedGrades="1" MaxCount="9999" TemplateName="VIP Token"')
    tpl_raw = tpl_raw.replace(b'TemplateId="2030701" MasterType="2" SonType="203" Sexs="2" NeedGrades="20"',
                             b'TemplateId="2030701" MasterType="2" SonType="203" Sexs="2" NeedGrades="1"')
    tpl_raw = tpl_raw.replace(b'TemplateId="2030703" MasterType="2" SonType="203" Sexs="2" NeedGrades="40"',
                             b'TemplateId="2030703" MasterType="2" SonType="203" Sexs="2" NeedGrades="1"')
    tpl_raw = tpl_raw.replace(b'TemplateId="2090101" MasterType="2" SonType="208" Sexs="2" NeedGrades="11" MaxCount="9999" TemplateName="Bolsa de Sangue B\xc3\xa1sico" Job="0" Refresh="0" Icon="/blood_01.png" Description="Itens desnecess\xc3\xa1rios" Profile="2" SellGold="500" DefaultSkill="" Avata="" StrengthenMax="0" RandomSkillCount="0" SuiteId="0" StartingPrice="5" TransformId="0" IsCanBatch="false" Feed="0" NeedChangeJob="0"',
                             b'TemplateId="2090101" MasterType="2" SonType="209" Sexs="2" NeedGrades="11" MaxCount="9999" TemplateName="Bolsa de Sangue B\xc3\xa1sico" Job="0" Refresh="0" Icon="/blood_01.png" Description="Restaura 10.000 HP" Profile="2" SellGold="500" DefaultSkill="" Avata="" StrengthenMax="0" RandomSkillCount="0" SuiteId="0" StartingPrice="5" TransformId="0" IsCanBatch="false" Feed="0" NeedChangeJob="0" Property1="10000" Property2="0"')
    tpl_raw = tpl_raw.replace(b'TemplateId="1011" TemplateName="Lobo Maligno"', b'TemplateId="1011" TemplateName="Wulfgar"')
    tpl_raw = tpl_raw.replace(b'TemplateId="208068" MasterType="2" SonType="219"', b'TemplateId="208068" MasterType="2" SonType="208"')
    tpl_raw = tpl_raw.replace(b'TemplateId="2131055" MasterType="2" SonType="208"', b'TemplateId="2131055" MasterType="2" SonType="316"')
    for mid in (b'2190001', b'2190002', b'2190003', b'2190004'):
        tpl_raw = tpl_raw.replace(b'TemplateId="' + mid + b'" MasterType="2" SonType="208"', b'TemplateId="' + mid + b'" MasterType="2" SonType="219"')

    if b'<MapPhysicsTempInfo TemplateId="200401"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<MapPhysicsTempInfos>', b'<MapPhysicsTempInfos>' + mine_physics_entries, 1)
        print("Injected mine physics entries into tpl_raw!")

    if b'<SkillBufferTempInfo Id="41"' not in tpl_raw:
        stun_entry = b'<SkillBufferTempInfo Id="41" BufferName="Atordoado" AttackType="19" ValidCount="1" AttackWay="0" CountWay="1" Description="Stunned - Movement inhibited" Icon="" IsDisplay="true" MasterType="0" NoticeType="0" Priority="0" PropertyType="0" ReplaceType="0" ReviveWay="0" SonType="0" Type="0" Value="0" ValuePercent="0"/>'
        tpl_raw = tpl_raw.replace(b'<SkillBufferTempInfos>', b'<SkillBufferTempInfos>' + stun_entry, 1)
        print("Injected stun buffer 41 into tpl_raw!")

    if b'<GameHeroTempInfo TemplateId="72001"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<GameHeroTemp>', b'<GameHeroTemp>' + thief_entries, 1)
        print("Injected thieves into tpl_raw!")

    map_levels = {
        b'1': (b'11', b'20'),
        b'2': (b'21', b'30'),
        b'3': (b'31', b'40'),
        b'4': (b'41', b'50'),
        b'5': (b'51', b'60'),
    }
    for mid, (min_lvl, max_lvl) in map_levels.items():
        prefix = b'<MapInfo Id="' + mid + b'" CampaignId="0"'
        idx = tpl_raw.find(prefix)
        if idx != -1:
            end = tpl_raw.find(b'/>', idx) + 2
            chunk = tpl_raw[idx:end].replace(b'Width="10000" Height="10000"', b'Width="80000" Height="80000"').replace(b'MinLevel="1" MaxLevel="999"', b'MinLevel="' + min_lvl + b'" MaxLevel="' + max_lvl + b'"')
            tpl_raw = tpl_raw[:idx] + chunk + tpl_raw[end:]

    tpl_raw = tpl_raw.replace(b'<UpGradeTempInfo Id="30009" Types="3" TemplateId="0" TemplateName="" Grades="9" Data="10800" ActiveObject="0"',
                              b'<UpGradeTempInfo Id="30009" Types="3" TemplateId="0" TemplateName="" Grades="9" Data="10800" ActiveObject="30101"')

    if b'<TimeDrop DropId="10005"' not in tpl_raw:
        time_drop_entry = b'<TimeDrop DropId="10005" Grade="5" TemplateId="2090102" Data="1" Job="0" ValidDate="0"/>'
        tpl_raw = tpl_raw.replace(b'<TimeDrop>', b'<TimeDrop>' + time_drop_entry, 1)
        print("Injected blood bag into tpl_raw TimeDrop!")

    # Atualizações em ConfigInfos
    tpl_raw = tpl_raw.replace(b'ConfigName="ShopBuy_MaxCount" ConfigValue="3"', b'ConfigName="ShopBuy_MaxCount" ConfigValue="20"')
    tpl_raw = tpl_raw.replace(b'ConfigName="Mount_Point" ConfigValue="5"', b'ConfigName="Mount_Point" ConfigValue="35"')
    tpl_raw = tpl_raw.replace(b'ConfigName="pet_up_quality" ConfigValue="5"', b'ConfigName="pet_up_quality" ConfigValue="35"')
    tpl_raw = tpl_raw.replace(b'ConfigName="swallow_fullgp_points" ConfigValue="50"', b'ConfigName="swallow_fullgp_points" ConfigValue="295"')
    tpl_raw = tpl_raw.replace(b'ConfigName="pet_island_defend_rage_add" ConfigValue="4,10"', b'ConfigName="pet_island_defend_rage_add" ConfigValue="2,5"')

    # Atualização em MountTempInfos
    tpl_raw = tpl_raw.replace(
        b'TemplateId="1103" TemplateName="Alpaca Dem\xc3\xb4nio" MountType="1" Power="15" Intellect="15" Physique="15" Agility="15"',
        b'TemplateId="1103" TemplateName="Alpaca Dem\xc3\xb4nio" MountType="1" Power="10" Intellect="10" Physique="10" Agility="10"'
    )

    # Injeção em SkillTempInfos
    if b'TemplateId="2100"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<SkillTempInfos>', b'<SkillTempInfos>' + fate_skill_entry, 1)

    # População da Casa em BuildingTempInfos
    tpl_raw = fix_building_population(tpl_raw)

    # Buffs de cartas e chefes em CampaignBufferTemps
    tpl_raw = tpl_raw.replace(b'<CampaignBufferTemps>', b'<CampaignBufferTemps>' + card_buffer_entries + boss_buffer_entries, 1)

    if b'<ItemTempInfo TemplateId="21261044"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<ItemTempInfos>', b'<ItemTempInfos>' + item_21261044, 1)
        print("Injected item 21261044 into tpl_raw!")

    # Upgrades de cartas em UpGradeTempInfos
    if b'TemplateName="Card Grade"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<UpGradeTempInfos>', b'<UpGradeTempInfos>' + card_upgrade_entries, 1)
        print("Injected card upgrades into tpl_raw!")

    # Shop e VIP
    tpl_raw = tpl_raw.replace(b'Id="602" ShopType="1" Area="2" ItemId="208002" Point="50"', b'Id="602" ShopType="1" Area="2" ItemId="208002" Point="0"')
    if b'<ShopTempInfo Id="19"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<ShopTempInfos>', b'<ShopTempInfos>' + guild_shop_extras, 1)
        print("Injected guild_shop_extras into tpl_raw!")
    if b'type="14"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<VipPrerogativeTempInfos>', b'<VipPrerogativeTempInfos>' + vip_prerogative_entries, 1)
        print("Injected vip_prerogative_entries into tpl_raw!")
    if b'<ShopTempInfo Id="2000" ShopType="6"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<ShopTempInfos>', b'<ShopTempInfos>' + shop_entries, 1)
        print("Injected shop_entries into tpl_raw!")
    if b'<ComposeTempInfo Id="1"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<ComposeTempInfos>', b'<ComposeTempInfos>' + compose_entries, 1)
        print("Injected compose_entries into tpl_raw!")

    # Configs e Veículos
    tpl_raw = tpl_raw.replace(b'ConfigName="MatchOfVehicleTime" ConfigValue="16:00,16:25"', b'ConfigName="MatchOfVehicleTime" ConfigValue="10:00,10:25|16:00,16:25"')
    tpl_raw = tpl_raw.replace(b'ConfigName="Consortia_ClearCD_Point" ConfigValue="50"', b'ConfigName="Consortia_ClearCD_Point" ConfigValue="395"')
    tpl_raw = tpl_raw.replace(b'TemplateId="2" TemplateName="Mina de F\xc3\xbaria" Attack="150" NeedDiamond="200"', b'TemplateId="2" TemplateName="Mina de F\xc3\xbaria" Attack="150" NeedDiamond="0"')
    tpl_raw = tpl_raw.replace(b'TemplateId="3" TemplateName="Lobo Silencioso" Attack="170" NeedDiamond="500" Defence="60" Hp="6500" Dodge="5" GeniusSkill="1003" NormalSkill="1" Description="Lobo Silencioso" Avatar="/vehicle_3" NeedGrades="0"', b'TemplateId="3" TemplateName="Lobo Silencioso" Attack="170" NeedDiamond="1000" Defence="60" Hp="6500" Dodge="5" GeniusSkill="1003" NormalSkill="1" Description="Lobo Silencioso" Avatar="/vehicle_3" NeedGrades="365"')

    # Injetar tabelas PowcardTempInfos, PowCardSuiteTemInfos, SimpleTasks no tpl_raw
    if b'<PowcardTempInfos>' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'</root>', b'<PowcardTempInfos>' + powcards_entries + b'</PowcardTempInfos></root>', 1)
    if b'<PowCardSuiteTemInfos>' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'</root>', b'<PowCardSuiteTemInfos>' + powcard_suites_entries + b'</PowCardSuiteTemInfos></root>', 1)
    if b'<SimpleTasks>' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'</root>', b'<SimpleTasks>' + simple_tasks_entries + b'</SimpleTasks></root>', 1)

    # Injetar campanhas de Campo de Batalha (4001-4011), mina 30000, horário do World Boss 5001 e rota de casamento no tpl_raw
    if b'CampaignId="4001"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<Campaigns>', b'<Campaigns>' + battleground_campaigns, 1)
        print("Injected battleground campaigns into tpl_raw!")
    if b'CampaignId="30000"' not in tpl_raw:
        tpl_raw = tpl_raw.replace(b'<Campaigns>', b'<Campaigns>' + mine_campaign, 1)
        print("Injected mine 30000 into tpl_raw!")
    tpl_raw = tpl_raw.replace(b'CampaignId="5001" CampaignName="Rei dos Lobos"', b'CampaignId="5001" CampaignName="Bloodfang"')
    tpl_raw = tpl_raw.replace(
        b'CampaignId="5001" CampaignName="Bloodfang" Types="1" SonTypes="0" LandId="0" DungeonId="0" AreaId="0" MinLevel="20" MaxLevel="100" PreCampaignId="0" NextCampaignId="0" Capacity="10000" DifficultyGrade="1" Description="Batalhando o Chef\xc3\xa3o Global receber\xc3\xa1 Ouro e Esp\xc3\xadrito" CardPayment="0" PosX="0" PosY="0" Item="" StandSecond="0" StandardDamage="0" StandardHurt="0" BaseGp="0" OpenTime="11:00" StopTime="12:00"',
        b'CampaignId="5001" CampaignName="Bloodfang" Types="1" SonTypes="0" LandId="0" DungeonId="0" AreaId="0" MinLevel="20" MaxLevel="100" PreCampaignId="0" NextCampaignId="0" Capacity="10000" DifficultyGrade="1" Description="Batalhando o Chef\xc3\xa3o Global receber\xc3\xa1 Ouro e Esp\xc3\xadrito" CardPayment="0" PosX="0" PosY="0" Item="" StandSecond="0" StandardDamage="0" StandardHurt="0" BaseGp="0" OpenTime="11:35" StopTime="12:35"'
    )
    tpl_raw = tpl_raw.replace(
        b'Path="34,81|41,88|163,88|194,119|194,144|209,159|278,159|278,135|262,119|194,119|163,88|41,88|34,81"',
        b'Path="171,72|41,88|163,88|194,119|194,144|209,159|278,159|278,135|262,119|194,119|163,88|41,88|34,81"'
    )

    tpl_raw = fix_quest_and_nodes_xml(tpl_raw)
    print("Applied quest & node fixes to tpl_raw!")

    tpl_comp = zlib.compress(tpl_raw, level=9)
    with open(tpl_path, "wb") as f:
        f.write(tpl_comp)
    print(f"Saved updated {tpl_path} ({len(tpl_comp)} bytes)")


if __name__ == "__main__":
    repack()
