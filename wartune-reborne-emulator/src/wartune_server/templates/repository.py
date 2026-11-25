"""Templates estáticos do jogo (``tempinfos.xml``): heróis, itens, prédios, mapas...

É o mesmo arquivo que o cliente baixa de ``TEMPLATE_PATH``, então servidor e
cliente sempre concordam: ``wartune-server templates update`` baixa a versão da CDN
para o arquivo local. O arquivo oficial vem comprimido em zlib; aceitamos
também o XML puro. Somente leitura depois de carregado: pode ser compartilhado
entre corrotinas sem trava.
"""

from __future__ import annotations

import asyncio
import json
import os
import struct
import zlib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from xml.etree import ElementTree

import aiohttp

Row = Mapping[str, str]


@dataclass(frozen=True, slots=True)
class HeroTemplate:
    template_id: int
    name: str
    job: int
    sex: int
    power: int
    agility: int
    intellect: int
    captain: int
    physique: int
    live: int
    force_hit: int
    parry: int
    skill_script: str

    @classmethod
    def from_row(cls, row: Row) -> HeroTemplate:
        return cls(
            template_id=int(row["TemplateId"]),
            name=row.get("TemplateName", ""),
            job=int(row["Job"]),
            sex=int(row["Sexs"]),
            power=int(row["Power"]),
            agility=int(row["Agility"]),
            intellect=int(row["Intellect"]),
            captain=int(row["Captain"]),
            physique=int(row["Physique"]),
            live=int(row["Live"]),
            force_hit=int(row["ForceHit"]),
            parry=int(row["Parry"]),
            skill_script=row.get("SkillScript", ""),
        )


class GameTemplates:
    def __init__(
        self,
        categories: dict[str, list[Row]],
        nested: dict[str, list[Row]] | None = None,
        h5_system_open: tuple[int, ...] = (),
    ) -> None:
        """``nested``: as linhas do nível a mais (só o ``TollgateReward``: ``ScoreRewards``, ``BossRewards``...),
        pelo nome do grupo; ``rows``/``get``/``find`` acham também por esse nome."""
        self._categories = categories
        self._nested = nested or {}
        self._index: dict[tuple[str, str], dict[str, Row]] = {}
        self.h5_system_open = h5_system_open
        self._heroes = {
            t.template_id: t for t in (HeroTemplate.from_row(r) for r in categories.get("GameHeroTemp", []))
        }

    @classmethod
    def parse(cls, data: bytes) -> GameTemplates:
        if len(data) >= 5 and data[4:5] == b"\x78":
            data = zlib.decompress(data[4:])
        elif data[:1] == b"\x78":  # cabeçalho zlib
            data = zlib.decompress(data)

        # Formato binário oficial 7Road (versão uint32 + tabelas com tamanho de nome e corpo)
        if len(data) >= 4 and not data.lstrip().startswith(b"<"):
            p = 4
            categories: dict[str, list[Row]] = {}
            nested: dict[str, list[Row]] = {}
            while p < len(data):
                n = data[p]
                p += 1
                name = data[p : p + n].decode("utf-8", "ignore")
                p += n
                ln = struct.unpack(">i", data[p : p + 4])[0]
                p += 4
                xml_bytes = data[p : p + ln]
                p += ln
                try:
                    root = ElementTree.fromstring(xml_bytes)
                except ElementTree.ParseError:
                    continue
                categories[root.tag] = [MappingProxyType(dict(item.attrib)) for item in root]
                for group in root:
                    if len(group):
                        nested[group.tag] = [MappingProxyType(dict(row.attrib)) for row in group]
            return cls(categories, nested)

        root = ElementTree.fromstring(data)
        categories = {}
        nested = {}
        for category in root:
            categories[category.tag] = [MappingProxyType(dict(item.attrib)) for item in category]
            for group in category:
                if len(group):
                    nested[group.tag] = [MappingProxyType(dict(row.attrib)) for row in group]
        return cls(categories, nested)

    @classmethod
    async def load(cls, path: Path) -> GameTemplates:
        data = await asyncio.to_thread(path.read_bytes)
        templates = await asyncio.to_thread(cls.parse, data)
        extras_path = path.with_name("h5_extras.json")
        if await asyncio.to_thread(extras_path.is_file):
            raw_extras = await asyncio.to_thread(extras_path.read_text, "utf-8")
            extras = json.loads(raw_extras)
            templates._merge_h5_extras(extras)
        return templates

    def _merge_h5_extras(self, extras: dict[str, object]) -> None:
        """Complementa ``ShopTempInfos``/``ItemTempInfos`` com ofertas e itens exclusivos do cliente H5."""
        for cat, key in (("ShopTempInfos", "Id"), ("ItemTempInfos", "TemplateId")):
            rows = extras.get(cat)
            if not isinstance(rows, list):
                continue
            existing = self._categories.setdefault(cat, [])
            known = {r.get(key, "") for r in existing}
            for item in rows:
                if not isinstance(item, dict):
                    continue
                val = str(item.get(key, ""))
                if val and val not in known:
                    existing.append(MappingProxyType({str(k): str(v) for k, v in item.items()}))
                    known.add(val)
        sys_ids = extras.get("H5SystemOpen")
        if isinstance(sys_ids, list):
            self.h5_system_open = tuple(int(x) for x in sys_ids)
        self._index.clear()

    @classmethod
    async def download(cls, url: str, path: Path) -> GameTemplates:
        """Baixa da CDN e troca o arquivo local; um arquivo que não abre não substitui o atual."""
        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as http,
            http.get(url) as resp,
        ):
            resp.raise_for_status()
            data = await resp.read()
        templates = await asyncio.to_thread(cls.parse, data)
        await asyncio.to_thread(_replace, path, data)
        return templates

    @property
    def categories(self) -> list[str]:
        return sorted(self._categories)

    def rows(self, category: str) -> list[Row]:
        return self._categories.get(category) or self._nested.get(category, [])

    def find(self, category: str, **attrs: object) -> Iterator[Row]:
        wanted = {k: str(v) for k, v in attrs.items()}
        for row in self.rows(category):
            if all(row.get(k) == v for k, v in wanted.items()):
                yield row

    def get(self, category: str, template_id: int | str, key: str = "TemplateId") -> Row | None:
        """Busca indexada pela chave (a primeira linha vence se houver repetição)."""
        index = self._index.get((category, key))
        if index is None:
            index = {}
            for row in self.rows(category):
                index.setdefault(row.get(key, ""), row)
            self._index[(category, key)] = index
        return index.get(str(template_id))

    def hero(self, template_id: int) -> HeroTemplate:
        try:
            return self._heroes[template_id]
        except KeyError:
            raise KeyError(f"template de herói {template_id} não existe") from None


def _replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
