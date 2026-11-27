"""Audita a integridade da CDN cruzando ``tempinfos.xml`` com os arquivos do espelho local.

Para cada atributo de template que vira URL no cliente, monta o caminho e verifica se existe em
``CDN/res134-bmclas-sq.7road.net``. Gera cobertura por regra, a lista do que falta (com os templates
que pedem) e as pastas de avatar que ninguém referencia.

    python tools\\auditar_cdn.py
    python tools\\auditar_cdn.py --saida docs\\INTEGRIDADE_CDN.md
    python tools\\auditar_cdn.py --cdn D:\\espelho\\res134-bmclas-sq.7road.net

As fórmulas abaixo foram conferidas uma a uma contra o espelho; nenhuma é suposição. Casos que
pareciam caminho e não são (``MarrySpecTempInfos.Path`` guarda coordenadas ``x,y|x,y``) ficam de fora.
"""

from __future__ import annotations

import argparse
import sys
import zlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "data" / "templates" / "tempinfos.xml"
CDN = ROOT.parent / "CDN" / "res134-bmclas-sq.7road.net"
EXEMPLOS = 8  # quantos faltantes listar por regra


@dataclass(frozen=True, slots=True)
class Regra:
    """``alvo`` usa ``{v}`` para o valor do atributo, sem a barra inicial duplicada."""

    categoria: str
    atributo: str
    alvo: str
    alternativo: str = ""  # segundo caminho aceito quando o valor já embute o prefixo
    pasta: bool = False
    separador: str = ""  # divide o valor; só a primeira parte é caminho (PicPath)
    extensao: str = ""  # aplicada quando o valor não traz nenhuma
    so_com_barra: bool = False  # valores sem "/" não são caminho (EffectTempInfos usa "0")


REGRAS = (
    # Ícones: o atributo já vem com a barra inicial, o prefixo é sempre "icon". Alguns (os prédios)
    # repetem "icon/" dentro do próprio valor e aí o caminho é relativo à raiz, daí o alternativo.
    Regra("ItemTempInfos", "Icon", "icon{v}", so_com_barra=True),
    Regra("SkillTempInfos", "Icons", "icon{v}", so_com_barra=True),
    Regra("SkillBufferTempInfos", "Icon", "icon{v}", so_com_barra=True),
    Regra("BuildingTempInfos", "Icon", "icon{v}", alternativo="{v}", so_com_barra=True),
    Regra("CampaignBufferTemps", "Icon", "icon{v}", so_com_barra=True),
    Regra("ConsortiaLevelInfos", "Icon", "icon{v}", so_com_barra=True),
    Regra("EffectTempInfos", "Icon", "icon{v}", so_com_barra=True),
    Regra("PawnTempInfos", "Icon", "icon{v}", so_com_barra=True),
    Regra("PowCardSuiteTemInfos", "Icon", "icon{v}", so_com_barra=True),
    Regra("PowcardTempInfos", "Icon", "icon{v}", extensao=".png", so_com_barra=True),
    Regra("RuneTempInfos", "Icon", "icon{v}", so_com_barra=True),
    Regra("VehicleBuffTempInfos", "Icon", "icon{v}", so_com_barra=True),
    Regra("VehicleSkillTempInfos", "Icons", "icon{v}", so_com_barra=True),
    Regra("starTempInfos", "Icon", "icon{v}", so_com_barra=True),
    Regra("GameHeroTemp", "Icon", "icon{v}", so_com_barra=True),
    Regra("SpecialTempInfos", "ResPath", "icon{v}", so_com_barra=True),
    # Avatares: a pasta guarda um arquivo por peça e sexo ("1_0.swf", "2_1.swf"...), por isso a
    # verificação é da pasta e não de um nome fixo.
    Regra("ItemTempInfos", "Avata", "equip{v}", pasta=True),
    Regra("ItemTempInfos", "Avata", "swf/avatar{v}", pasta=True),
    Regra("GameHeroTemp", "ArmPath", "equip{v}", pasta=True),
    Regra("GameHeroTemp", "ClothPath", "equip{v}", pasta=True),
    Regra("PetTempInfos", "PetAvatar", "equip{v}", pasta=True),
    Regra("MountTempInfos", "AvatarPath", "swf/avatar{v}", pasta=True),
    Regra("VehicleObjectTempInfos", "Avatar", "vehicle/avatar{v}", pasta=True),
    # SWF com nome repetido na pasta.
    Regra("PawnTempInfos", "Swf", "swf/{v}/{v}.swf"),
    Regra("GameHeroTemp", "ResPath", "swf/{v}/{v}.swf"),
    Regra("FishTemplateInfos", "Path", "fish{v}.swf"),
    # Música de mapa: o atributo é só o nome ("BGM000") e os arquivos do espelho são .flv.
    Regra("MapInfos", "MusicPath", "sounds/{v}.flv"),
    # PicPath é "images/x.swf|classe_view|classe_effect": só a primeira parte é arquivo.
    Regra("BuildingTempInfos", "PicPath", "{v}", separador="|"),
    # Mapas usam MapFileId, não Id: vários Ids diferentes compartilham o mesmo arquivo.
    Regra("MapInfos", "MapFileId", "sceneIma/{v}/map{v}.swf"),
    Regra("MapInfos", "MapFileId", "maps/{v}/{v}.maps"),
    Regra("MapInfos", "MapFileId", "maps/{v}/{v}.titles"),
    Regra("MapInfos", "Id", "images/mapName/{v}.png"),
)

# Pastas varridas para achar avatar sem referência nenhuma nos templates.
POOLS = ("equip", "swf/avatar", "vehicle/avatar")


def carregar(caminho: Path) -> dict[str, list[dict[str, str]]]:
    dados = caminho.read_bytes()
    if dados[:1] == b"\x78":  # cabeçalho zlib, igual ao que o cliente baixa
        dados = zlib.decompress(dados)
    raiz = ElementTree.fromstring(dados)
    return {categoria.tag: [dict(item.attrib) for item in categoria] for categoria in raiz}


def resolver(regra: Regra, valor: str) -> list[str]:
    """Caminhos aceitos para o valor; vazio quando o atributo não é caminho nesta linha."""
    if regra.separador:
        valor = valor.split(regra.separador)[0]
    valor = valor.strip()
    if not valor or (regra.so_com_barra and not valor.startswith("/")):
        return []
    if regra.extensao and "." not in valor.rsplit("/", 1)[-1]:
        valor += regra.extensao
    formatos = [regra.alvo, regra.alternativo] if regra.alternativo else [regra.alvo]
    return [f.replace("{v}", valor).replace("//", "/").lstrip("/") for f in formatos]


def existe(cdn: Path, caminhos: list[str], pasta: bool) -> bool:
    return any((cdn / c).is_dir() if pasta else (cdn / c).is_file() for c in caminhos)


def auditar(
    categorias: dict[str, list[dict[str, str]]], cdn: Path
) -> list[tuple[Regra, int, dict[str, list[str]]]]:
    """Por regra: total de valores distintos e os caminhos ausentes com quem os pede."""
    resultado = []
    for regra in REGRAS:
        pedidos: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for linha in categorias.get(regra.categoria, []):
            caminhos = resolver(regra, linha.get(regra.atributo) or "")
            if caminhos:
                pedidos[tuple(caminhos)].append(linha.get("TemplateId") or linha.get("Id") or "?")
        faltando = {
            chave[0]: quem for chave, quem in pedidos.items() if not existe(cdn, list(chave), regra.pasta)
        }
        resultado.append((regra, len(pedidos), faltando))
    return resultado


def orfaos(categorias: dict[str, list[dict[str, str]]], cdn: Path) -> dict[str, list[str]]:
    """Pastas de avatar no espelho que nenhuma regra de pasta aponta."""
    usados: set[str] = set()
    for regra in REGRAS:
        if not regra.pasta:
            continue
        for linha in categorias.get(regra.categoria, []):
            usados.update(resolver(regra, linha.get(regra.atributo) or ""))
    saida: dict[str, list[str]] = {}
    for pool in POOLS:
        base = cdn / pool
        if not base.is_dir():
            continue
        saida[pool] = sorted(d.name for d in base.iterdir() if d.is_dir() and f"{pool}/{d.name}" not in usados)
    return saida


def relatorio(auditoria, sem_uso: dict[str, list[str]], cdn: Path) -> str:  # type: ignore[no-untyped-def]
    arquivos = sum(1 for _ in cdn.rglob("*") if _.is_file())
    linhas = [
        "# Integridade da CDN",
        "",
        f"Espelho: `{cdn}` — {arquivos} arquivos.",
        "Gerado por `tools/auditar_cdn.py` a partir de `data/templates/tempinfos.xml`.",
        "",
        "## Cobertura por referência",
        "",
        "| Categoria | Atributo | Caminho | Distintos | Presentes | Faltando |",
        "|---|---|---|---:|---:|---:|",
    ]
    total = ausentes = 0
    for regra, distintos, faltando in auditoria:
        total += distintos
        ausentes += len(faltando)
        linhas.append(
            f"| {regra.categoria} | {regra.atributo} | `{regra.alvo}`"
            f"{' (pasta)' if regra.pasta else ''} | {distintos} | {distintos - len(faltando)} |"
            f" {len(faltando)} |"
        )
    pct = 100 * (total - ausentes) / total if total else 100.0
    linhas += ["", f"**Total: {total - ausentes}/{total} referências resolvidas ({pct:.2f}%).**", ""]

    linhas += ["## Faltando", ""]
    if not ausentes:
        linhas.append("Nenhuma referência sem arquivo.")
    for regra, _, faltando in auditoria:
        if not faltando:
            continue
        linhas.append(f"### {regra.categoria}.{regra.atributo} → `{regra.alvo}` ({len(faltando)})")
        linhas.append("")
        for caminho in sorted(faltando)[:EXEMPLOS]:
            quem = faltando[caminho]
            amostra = ", ".join(quem[:5]) + (f" (+{len(quem) - 5})" if len(quem) > 5 else "")
            linhas.append(f"- `{caminho}` — pedido por {len(quem)} template(s): {amostra}")
        if len(faltando) > EXEMPLOS:
            linhas.append(f"- … mais {len(faltando) - EXEMPLOS}")
        linhas.append("")

    linhas += ["## Pastas de avatar sem referência nos templates", ""]
    for pool, nomes in sem_uso.items():
        linhas.append(f"- `{pool}/`: {len(nomes)} sem referência" + (f" (ex.: {', '.join(nomes[:5])})" if nomes else ""))
    linhas.append("")
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--templates", type=Path, default=TEMPLATES)
    parser.add_argument("--cdn", type=Path, default=CDN)
    parser.add_argument("--saida", type=Path, help="grava o relatório em markdown; sem isso, imprime")
    args = parser.parse_args()
    if not args.cdn.is_dir():
        sys.exit(f"espelho da CDN não encontrado: {args.cdn}")
    categorias = carregar(args.templates)
    texto = relatorio(auditar(categorias, args.cdn), orfaos(categorias, args.cdn), args.cdn)
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(texto, encoding="utf-8")
        print(f"relatório em {args.saida}")
    else:
        print(texto)


if __name__ == "__main__":
    main()
