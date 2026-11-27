"""Repara os arquivos do cliente Flash baixando os originais da origem da 7road.

Todo arquivo que o ``Loading.swf`` consome vem embrulhado em ``road7`` + 32 caracteres
com o MD5 do conteúdo + o conteúdo. O ``MD5Installer`` descarta esses 37 bytes antes do
``loadBytes``; um arquivo cru entra no player com 37 bytes a menos e simplesmente não
abre — sem erro, sem log, a cena fica preta.

Esta ferramenta confere cada entrada do ``resouececheck.sq`` contra o espelho local e,
para o que estiver ausente, cru, truncado ou adulterado, baixa o original da origem e só
grava se o MD5 do conteúdo bater com o que o manifesto declara. O manifesto nunca é
reescrito: ele é a referência, não o alvo.

Uso::

    python tools/reparar_cliente.py --cdn G:/projects/wartune-reborn-emulator/CDN
    python tools/reparar_cliente.py --cdn ... --aplicar
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path

MARCA = b"road7"
CABECALHO = len(MARCA) + 32
MANIFESTO = "s134-bmclas-sq.7road.net/client/resouececheck.sq"
ESPELHOS = ("s134-bmclas-sq.7road.net", "res134-bmclas-sq.7road.net")
ORIGENS = tuple(f"https://{espelho}/" for espelho in reversed(ESPELHOS))
TEMPO_LIMITE = 60


@dataclass(frozen=True, slots=True)
class Defeito:
    nome: str
    motivo: str


def manifesto(cdn: Path) -> str:
    bruto = (cdn / MANIFESTO).read_bytes()
    return (zlib.decompress(bruto) if bruto[:1] == b"\x78" else bruto).decode("utf-8-sig")


def itens(texto: str) -> list[tuple[str, str]]:
    return re.findall(r'<Item name="([^"]+)" md5="([^"]*)" />', texto)


def destino(cdn: Path, nome: str) -> Path:
    relativo = nome.replace("\\", "/")
    for espelho in ESPELHOS:
        caminho = cdn / espelho / relativo
        if caminho.is_file():
            return caminho
    return cdn / ESPELHOS[1] / relativo


def diagnosticar(caminho: Path, md5: str) -> str:
    if not caminho.is_file():
        return "ausente"
    bruto = caminho.read_bytes()
    if bruto[: len(MARCA)] != MARCA:
        return "sem envelope"
    declarado = bruto[len(MARCA) : CABECALHO].decode("latin1").lower()
    if declarado != md5:
        return "versão diferente"
    if hashlib.md5(bruto[CABECALHO:]).hexdigest() != declarado:
        return "conteúdo adulterado"
    return ""


def baixar(nome: str, md5: str) -> bytes | None:
    relativo = nome.replace("\\", "/")
    for origem in ORIGENS:
        try:
            with urllib.request.urlopen(origem + relativo, timeout=TEMPO_LIMITE) as resposta:
                bruto = resposta.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
        if bruto[: len(MARCA)] != MARCA:
            continue
        if hashlib.md5(bruto[CABECALHO:]).hexdigest() == md5:
            return bruto
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdn", type=Path, required=True, help="raiz do espelho da CDN")
    parser.add_argument("--aplicar", action="store_true", help="baixa e grava os originais")
    args = parser.parse_args(argv)

    lista = itens(manifesto(args.cdn))
    defeitos = [
        Defeito(nome, motivo)
        for nome, md5 in lista
        if (motivo := diagnosticar(destino(args.cdn, nome), md5))
    ]
    esperados = dict(lista)

    print(f"{len(lista)} itens no manifesto; {len(defeitos)} com defeito")
    for defeito in defeitos:
        print(f"  {defeito.nome}: {defeito.motivo}")

    if not args.aplicar or not defeitos:
        return 0

    perdidos = []
    for defeito in defeitos:
        bruto = baixar(defeito.nome, esperados[defeito.nome])
        if bruto is None:
            perdidos.append(defeito.nome)
            print(f"  {defeito.nome}: origem não devolveu o original")
            continue
        caminho = destino(args.cdn, defeito.nome)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(bruto)
        print(f"  {defeito.nome}: restaurado com {len(bruto)} bytes")
    return 1 if perdidos else 0


if __name__ == "__main__":
    sys.exit(main())
