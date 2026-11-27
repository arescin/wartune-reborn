"""Confere o pacote do cliente Flash contra o ``resouececheck.sq`` da CDN.

O ``Loading.swf`` baixa ``client/resouececheck.sq`` (XML comprimido em zlib) e usa o
MD5 de cada entrada para decidir o que precisa buscar. Se um arquivo da lista não
existir, o Nginx da CDN devolve o ``empty.swf``/``empty.png`` com HTTP 200 e o jogo
trava sem erro visível — por isso a conferência tem que ser por MD5, não por status.

Uso::

    python tools/auditar_cliente.py --base https://wartune-cdn.thnsdu.easypanel.host
    python tools/auditar_cliente.py --saida docs/INTEGRIDADE_CLIENTE.md
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import xml.etree.ElementTree as ET
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_PADRAO = "https://wartune-cdn.thnsdu.easypanel.host"
BOOTSTRAP = "/game/client/resouececheck.sq"
# Placeholders que o Nginx devolve no lugar de um arquivo ausente.
VAZIOS = ("/empty.swf", "/empty.png", "/empty.mp3", "/empty.xml")


@dataclass(frozen=True, slots=True)
class Esperado:
    nome: str
    md5: str

    @property
    def caminho(self) -> str:
        return "/game/" + self.nome.replace("\\", "/")


@dataclass(frozen=True, slots=True)
class Achado:
    esperado: Esperado
    status: int
    tamanho: int
    md5: str

    @property
    def situacao(self) -> str:
        if self.status != 200:
            return "ausente"
        if self.md5 == self.esperado.md5:
            return "ok"
        return "divergente"


def baixar(url: str, tempo: int = 60) -> tuple[int, bytes]:
    pedido = Request(url, headers={"User-Agent": "wartune-auditoria/1.0"})
    try:
        with urlopen(pedido, timeout=tempo) as resposta:
            return resposta.status, resposta.read()
    except HTTPError as erro:
        return erro.code, b""
    except (URLError, TimeoutError, OSError):
        return 0, b""


def descomprimir(bruto: bytes) -> bytes:
    """O ``.sq`` é zlib puro; versões antigas do empacotador deixavam o XML cru."""
    if bruto[:1] != b"\x78":
        return bruto
    return zlib.decompress(bruto)


def esperados(base: str) -> list[Esperado]:
    status, bruto = baixar(base + BOOTSTRAP)
    if status != 200 or not bruto:
        raise SystemExit(f"não consegui baixar {BOOTSTRAP} (HTTP {status})")
    raiz = ET.fromstring(descomprimir(bruto).decode("utf-8-sig"))
    return [
        Esperado(item.attrib["name"], item.attrib.get("md5", "").lower())
        for item in raiz.iter("Item")
        if item.attrib.get("name")
    ]


def placeholders(base: str) -> dict[str, str]:
    """MD5 de cada arquivo vazio, para separar 'ausente' de 'conteúdo errado'."""
    marcas: dict[str, str] = {}
    for caminho in VAZIOS:
        status, corpo = baixar(base + caminho)
        if status == 200 and corpo:
            marcas[hashlib.md5(corpo).hexdigest()] = caminho
    return marcas


def conferir(base: str, item: Esperado, vazios: dict[str, str]) -> Achado:
    status, corpo = baixar(base + item.caminho)
    digest = hashlib.md5(corpo).hexdigest() if corpo else ""
    if status == 200 and digest in vazios:
        status = 404  # placeholder do Nginx: o arquivo não existe de verdade
    return Achado(item, status, len(corpo), digest)


def relatorio(base: str, achados: list[Achado]) -> str:
    ausentes = [a for a in achados if a.situacao == "ausente"]
    divergentes = [a for a in achados if a.situacao == "divergente"]
    total = len(achados)
    ok = total - len(ausentes) - len(divergentes)
    linhas = [
        "# Integridade do cliente Flash",
        "",
        f"Origem: `{base}{BOOTSTRAP}`",
        "",
        f"- Arquivos exigidos pelo `resouececheck.sq`: **{total}**",
        f"- Conferem pelo MD5: **{ok}** ({ok / total:.2%})" if total else "- lista vazia",
        f"- Ausentes (ou servidos como placeholder vazio): **{len(ausentes)}**",
        f"- Presentes com MD5 diferente: **{len(divergentes)}**",
        "",
    ]
    if ausentes:
        linhas += ["## Ausentes", "", "| arquivo |", "| --- |"]
        linhas += [f"| `{a.esperado.nome}` |" for a in ausentes]
        linhas.append("")
    if divergentes:
        linhas += [
            "## MD5 diferente",
            "",
            "| arquivo | esperado | obtido | bytes |",
            "| --- | --- | --- | ---: |",
        ]
        linhas += [
            f"| `{a.esperado.nome}` | `{a.esperado.md5}` | `{a.md5}` | {a.tamanho} |"
            for a in divergentes
        ]
        linhas.append("")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=BASE_PADRAO, help="raiz da CDN")
    parser.add_argument("--saida", type=Path, help="arquivo Markdown do relatório")
    parser.add_argument("--paralelo", type=int, default=16, help="downloads simultâneos")
    args = parser.parse_args(argv)

    base = args.base.rstrip("/")
    lista = esperados(base)
    vazios = placeholders(base)
    print(f"{len(lista)} arquivos na lista; {len(vazios)} placeholders conhecidos")

    with ThreadPoolExecutor(max_workers=args.paralelo) as pool:
        achados = list(pool.map(lambda item: conferir(base, item, vazios), lista))

    texto = relatorio(base, achados)
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(texto, encoding="utf-8")
        print(f"relatório em {args.saida}")
    else:
        print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
