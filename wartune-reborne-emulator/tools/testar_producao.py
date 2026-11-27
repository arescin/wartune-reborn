"""Refaz contra o servidor publicado o caminho inteiro de quem vai jogar.

A suíte de testes sobe tudo em memória e por isso nunca enxerga o que só quebra em
produção: domínio errado no portal, ticket que não atravessa o proxy, porta TCP fechada
pelo Traefik, migração que não rodou no banco remoto. Esta ferramenta faz o percurso de
verdade, na ordem em que o navegador faz:

    portal: cadastro/entrada -> play.php (ticket) -> client-config.xml (chave RSA)
    servidor: POST /login -> POST /visualizeregister -> POST /updateplayernovice
    socket: TCP 20001 LoginReqMsg -> troca de chave -> espera o 150 (LoginState)

Chegar no 150 é o critério: dali em diante o personagem está no mundo. Cada etapa é
impressa com o que respondeu, então uma falha aponta sozinha para a camada culpada.

Uso:
    PYTHONPATH=src python tools/testar_producao.py [--portal URL] [--usuario NOME]
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import http.cookiejar
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric import padding, rsa

from wartune_server.protocol import Packet, PacketDecoder, StreamCipher
from wartune_server.protocol.messages import wartune_pb2 as pb

PORTAL_PADRAO = "https://bots-wartune-portal.thnsdu.easypanel.host/"
SENHA = "AuditoriaE2E_2026!"
TEMP_PASSWORD = "7654321"


class Falha(Exception):
    pass


@dataclass
class Navegador:
    """Cliente HTTP com cookies, que é o que o portal usa para manter a sessão."""

    tempo: int = 30

    def __post_init__(self) -> None:
        self.cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
            _RespostaCrua(),
        )

    def abrir(self, url: str, dados: dict[str, str] | None = None) -> tuple[int, bytes]:
        corpo = urllib.parse.urlencode(dados).encode() if dados is not None else None
        pedido = urllib.request.Request(url, data=corpo, headers={"User-Agent": "wartune-auditoria/1.0"})
        with self._opener.open(pedido, timeout=self.tempo) as resposta:
            return resposta.status, resposta.read()


class _RespostaCrua(urllib.request.HTTPErrorProcessor):
    """Entrega a resposta como ela veio, sem seguir redirecionamento nem virar exceção.

    O 302 do portal é informação: diz se a sessão pegou. E um 4xx do servidor precisa ser
    lido, porque o corpo traz o motivo da recusa.
    """

    def http_response(self, request: urllib.request.Request, response: object) -> object:
        return response

    https_response = http_response


def _texto(bruto: bytes) -> str:
    return bruto.decode("utf-8", "replace")


def _achar(padrao: str, texto: str, oque: str) -> str:
    achado = re.search(padrao, texto)
    if achado is None:
        raise Falha(f"não achei {oque} na resposta")
    return achado.group(1)


def entrar(nav: Navegador, portal: str, usuario: str) -> None:
    """Cria a conta; se já existir, entra com ela."""
    status, corpo = nav.abrir(portal)
    if status != 200:
        raise Falha(f"portal respondeu {status}")
    csrf = _achar(r'name="csrf" value="([^"]+)"', _texto(corpo), "o token CSRF")

    for acao in ("register", "login"):
        status, corpo = nav.abrir(
            portal, {"csrf": csrf, "username": usuario, "password": SENHA, "action": acao}
        )
        if status == 302:
            print(f"  portal: {acao} de {usuario} aceito")
            return
        texto = _texto(corpo)
        erro = re.search(r'class="error">([^<]+)', texto)
        print(f"  portal: {acao} recusado ({erro.group(1) if erro else status})")
        csrf = _achar(r'name="csrf" value="([^"]+)"', texto, "o token CSRF")
    raise Falha("não consegui nem criar a conta nem entrar com ela")


def pegar_jogo(nav: Navegador, portal: str, servidor: int) -> dict:
    status, corpo = nav.abrir(f"{portal}play.php?server={servidor}")
    if status != 200:
        raise Falha(f"play.php respondeu {status} (302 = a sessão não sobreviveu)")
    return json.loads(_achar(r"const game = (\{.*?\});", _texto(corpo), "a configuração do Ruffle"))


def chave_publica(nav: Navegador, url: str) -> tuple[rsa.RSAPublicKey, str]:
    status, corpo = nav.abrir(url)
    if status != 200:
        raise Falha(f"client-config.php respondeu {status}")
    xml = _texto(corpo)
    modulo = _achar(r'PublicKeyModulus="([^"]+)"', xml, "o módulo RSA")
    expoente = _achar(r'publicExponent="([^"]+)"', xml, "o expoente RSA")
    numeros = rsa.RSAPublicNumbers(
        int.from_bytes(base64.b64decode(expoente), "big"),
        int.from_bytes(base64.b64decode(modulo), "big"),
    )
    return numeros.public_key(), modulo


def login_http(nav: Navegador, servidor_url: str, jogo: dict, chave: rsa.RSAPublicKey) -> int:
    """O ``p`` do Loading.swf: ``user|ticket|tempPassword|userId`` cifrado e em Base64."""
    fv = jogo["parameters"]
    usuario = urllib.parse.quote_from_bytes(fv["user"].encode(), safe="")
    claro = f"{usuario}|{fv['key']}|{TEMP_PASSWORD}|0".encode()
    cifrado = base64.b64encode(chave.encrypt(claro, padding.PKCS1v15())).decode()

    status, corpo = nav.abrir(f"{servidor_url}login", {"p": cifrado, "site": fv["site"]})
    texto = _texto(corpo)
    if status != 200 or 'value="true"' not in texto:
        raise Falha(f"/login respondeu {status}: {texto[:300]}")
    return int(_achar(r'userId="(\d+)"', texto, "o userId"))


def criar_personagem(nav: Navegador, servidor_url: str, user_id: int, usuario: str, chave: str) -> None:
    status, corpo = nav.abrir(
        f"{servidor_url}visualizeregister",
        {
            "userid": str(user_id),
            "username": usuario,
            "nickname": usuario.capitalize(),
            "sex": "0",
            "camp": "1",
            "icon": "6",
            "key": chave,
        },
    )
    texto = _texto(corpo)
    if 'value="true"' not in texto:
        # type="1" é "esse personagem já existe", que numa segunda execução é o esperado
        print(f"  servidor: personagem não criado agora ({texto.strip()[:120]})")
        return
    print("  servidor: personagem criado")
    status, corpo = nav.abrir(
        f"{servidor_url}updateplayernovice",
        {"op": "1", "userid": str(user_id), "noviceprocess": "0", "key": chave},
    )
    print(f"  servidor: tutorial em {_texto(corpo).strip()}")


async def entrar_no_mundo(host: str, porta: int, chave: str) -> tuple[int, list[int]]:
    """Abre o socket do jogo e segue até o 150, que é o LoginState."""
    leitor, escritor = await asyncio.wait_for(asyncio.open_connection(host, porta), 20)
    saida, decodificador = StreamCipher(), PacketDecoder(StreamCipher())
    ekeys = bytes(range(1, 9))

    corpo = pb.LoginReqMsg(key=chave, ekeys=list(ekeys)).SerializeToString()
    escritor.write(saida.encrypt(Packet(20001, corpo).encode()))
    await escritor.drain()
    saida.reset(ekeys)
    decodificador.cipher.reset(ekeys)

    vistos: list[int] = []
    jogador = 0
    try:
        while True:
            while (p := decodificador.next_packet()) is not None:
                vistos.append(p.code)
                if p.code == 3:
                    jogador = pb.PlayerMsg.FromString(p.body).playerId
                if p.code == 150:
                    return jogador, vistos
            dados = await asyncio.wait_for(leitor.read(65536), 20)
            if not dados:
                raise Falha(f"o servidor fechou o socket; recebi {vistos}")
            decodificador.feed(dados)
    finally:
        escritor.close()


async def principal() -> int:
    opcoes = argparse.ArgumentParser(description=__doc__)
    opcoes.add_argument("--portal", default=PORTAL_PADRAO)
    opcoes.add_argument("--servidor", type=int, default=1)
    opcoes.add_argument("--usuario", default="auditoria")
    args = opcoes.parse_args()
    portal = args.portal if args.portal.endswith("/") else args.portal + "/"

    nav = Navegador()
    try:
        print("1. portal")
        entrar(nav, portal, args.usuario)

        print("2. ticket e configuração do cliente")
        jogo = pegar_jogo(nav, portal, args.servidor)
        print(f"  ticket: {jogo['parameters']['key']}")
        print(f"  socket: {jogo['socket']['host']}:{jogo['socket']['port']} proxy {jogo['socket']['proxy']}")
        chave, modulo = chave_publica(nav, jogo["parameters"]["config"])
        print(f"  chave RSA: {modulo[:24]}... ({len(base64.b64decode(modulo)) * 8} bits)")

        print("3. login no servidor")
        servidor_url = f"https://{jogo['socket']['host']}/"
        user_id = login_http(nav, servidor_url, jogo, chave)
        print(f"  userId: {user_id}")

        print("4. personagem")
        sessao = hashlib.md5(TEMP_PASSWORD.encode()).hexdigest()
        criar_personagem(nav, servidor_url, user_id, jogo["parameters"]["user"], sessao)

        print("5. socket do jogo")
        jogador, vistos = await entrar_no_mundo(jogo["socket"]["host"], jogo["socket"]["port"], sessao)
        print(f"  pacotes até o LoginState: {vistos}")
        print(f"  personagem no mundo: {jogador}")
    except Falha as erro:
        print(f"\nFALHOU: {erro}")
        return 1
    except Exception as erro:  # noqa: BLE001 - qualquer tropeço aqui é resultado do teste
        print(f"\nFALHOU: {type(erro).__name__}: {erro}")
        return 1

    print("\nOK: o caminho inteiro do portal até o mundo do jogo funciona em produção.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(principal()))
