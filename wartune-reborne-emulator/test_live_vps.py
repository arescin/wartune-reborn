"""Script de teste ao vivo contra a VPS Hostinger do Wartune Reborn."""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import asyncio
import base64
import hashlib
import os
import re
import time
from urllib.parse import quote_from_bytes
import xml.etree.ElementTree as ET

import aiohttp
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

from wartune_server.protocol import Packet, PacketDecoder, StreamCipher
from wartune_server.protocol.messages import wartune_pb2 as pb


class FakeFlashClient:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader, self.writer = reader, writer
        self.out, self.decoder = StreamCipher(), PacketDecoder(StreamCipher())

    def send(self, code: int, msg: object | None = None, extend1: int = 0) -> None:
        body = msg.SerializeToString() if msg is not None else b""
        self.writer.write(self.out.encrypt(Packet(code, body, extend1=extend1).encode()))

    def rekey(self, key: bytes) -> None:
        self.out.reset(key)
        self.decoder.cipher.reset(key)

    async def until(self, code: int) -> list[Packet]:
        got: list[Packet] = []
        while True:
            while (p := self.decoder.next_packet()) is not None:
                got.append(p)
                if p.code == code:
                    return got
            data = await asyncio.wait_for(self.reader.read(65536), 10)
            assert data, f"conexão fechada esperando opcode {code}"
            self.decoder.feed(data)


async def run_live_test() -> None:
    http_base = "https://wartune-server.thnsdu.easypanel.host"
    tcp_host = "179.198.96.49"
    tcp_port = 5000

    print("=" * 65)
    print("TESTE DE HOMOLOGAÇÃO REAL — WARTUNE REBORN NA VPS HOSTINGER")
    print(f"Alvo HTTP: {http_base}")
    print(f"Alvo TCP : {tcp_host}:{tcp_port}")
    print("=" * 65)

    async with aiohttp.ClientSession() as session:
        # 1. Obter config.xml e extrair chave pública RSA
        print("\n[Etapa 1/6] Obtendo config.xml do servidor...")
        async with session.get(f"{http_base}/config.xml") as resp:
            assert resp.status == 200, f"HTTP {resp.status} em /config.xml"
            xml_text = await resp.text()
            root = ET.fromstring(xml_text)
            rsa_node = root.find(".//RSAKey")
            assert rsa_node is not None, "RSAKey não encontrada no config.xml"
            mod_b64 = rsa_node.attrib["PublicKeyModulus"]
            exp_b64 = rsa_node.attrib["publicExponent"]
            print(f"  ✓ config.xml obtido com sucesso! RSA Modulus: {mod_b64[:20]}...")

        # Reconstruir chave pública RSA
        mod_bytes = base64.b64decode(mod_b64)
        exp_bytes = base64.b64decode(exp_b64)
        n = int.from_bytes(mod_bytes, "big")
        e = int.from_bytes(exp_bytes, "big")
        pub_key = RSAPublicNumbers(e, n).public_key()

        # 2. Gerar conta e ticket via API de autenticação
        test_user = f"Live_{int(time.time()) % 10000}"
        print(f"\n[Etapa 2/6] Registrando conta de teste e emitindo ticket para '{test_user}'...")
        async with session.post(f"{http_base}/api/auth", data={"username": test_user}) as resp:
            assert resp.status == 200, f"HTTP {resp.status} em /api/auth"
            auth_data = await resp.json()
            assert auth_data.get("ok"), f"Auth falhou: {auth_data}"
            ticket = auth_data["ticket"]
            print(f"  ✓ Ticket emitido com sucesso: {ticket}")

        # 3. Simular login HTTP do Flash (criptografia RSA)
        print("\n[Etapa 3/6] Executando autenticação HTTP (/login)...")
        temp_pass = "7654321"
        key = hashlib.md5(temp_pass.encode()).hexdigest()
        escaped_user = quote_from_bytes(test_user.encode("utf-8"), safe="")
        payload = f"{escaped_user}|{ticket}|{temp_pass}|0".encode("utf-8")

        cipher_bytes = pub_key.encrypt(payload, padding.PKCS1v15())
        b64_cipher = base64.b64encode(cipher_bytes).decode("ascii")

        async with session.post(
            f"{http_base}/login",
            data={"p": b64_cipher, "site": "local_0001"}
        ) as resp:
            assert resp.status == 200, f"HTTP {resp.status} em /login"
            login_xml = await resp.text()
            assert 'value="true"' in login_xml, f"Login recusado: {login_xml}"
            user_id = int(re.search(r'userId="(\d+)"', login_xml).group(1))
            print(f"  ✓ Login HTTP aprovado! User ID: {user_id}")

        # 4. Registrar herói se necessário
        print("\n[Etapa 4/6] Registrando personagem (/visualizeregister)...")
        hero_nick = f"H{int(time.time()) % 10000}"
        async with session.post(
            f"{http_base}/visualizeregister",
            data={
                "userid": user_id,
                "username": test_user,
                "nickname": hero_nick,
                "sex": 0,
                "camp": 1,
                "icon": 6,
                "key": key,
            }
        ) as resp:
            reg_xml = await resp.text()
            assert 'value="true"' in reg_xml, f"Registro falhou: {reg_xml}"
            print(f"  ✓ Herói '{hero_nick}' ativado com sucesso!")

        # Atualizar novice para liberar castelo
        async with session.post(
            f"{http_base}/updateplayernovice",
            data={"op": 1, "userid": user_id, "noviceprocess": 0, "key": key}
        ) as resp:
            assert resp.status == 200

    # 5. Conectar via Socket TCP na VPS
    print(f"\n[Etapa 5/6] Conectando ao Socket TCP em {tcp_host}:{tcp_port}...")
    reader, writer = await asyncio.open_connection(tcp_host, tcp_port)
    client = FakeFlashClient(reader, writer)
    print("  ✓ Conexão TCP estabelecida com sucesso!")

    # 6. Handshake do protocolo de jogo Wartune (pacote 20001)
    print("\n[Etapa 6/6] Realizando handshake do protocolo de jogo (Pacote 20001)...")
    ekeys = os.urandom(8)
    client.send(20001, pb.LoginReqMsg(key=key, ekeys=list(ekeys)))
    client.rekey(ekeys)

    # Aguardar pacotes de inicialização (PlayerMsg - opcode 3)
    got = await client.until(150)
    assert [p.code for p in got] == [3841, 3, 150]
    player = pb.PlayerMsg.FromString(got[1].body)
    print(f"  ✓ Pacote PlayerMsg (opcode 3) recebido!")
    print(f"    - Nickname : {player.nickName}")
    print(f"    - Grade/Lvl: {player.grades}")
    print(f"    - Novice   : {player.noviceProcess}")

    # Enviar requisições de dados do castelo e exército
    flags = {f: True for f in ("castle", "army", "build", "tree", "aas", "friend", "sys", "snsReq")}
    client.send(8224, pb.PlayerDataMsg(**flags))
    await client.until(4173)

    # Confirmar entrada no jogo (LoginStateMsg - opcode 6)
    client.send(8224, pb.PlayerDataMsg(user=True))
    login_state = await client.until(6)
    state_msg = pb.LoginStateMsg.FromString(login_state[-1].body)
    assert state_msg.playerId == user_id
    assert state_msg.state == 0
    print(f"  ✓ Pacote LoginStateMsg (opcode 6) recebido com state=0 (Entrada no mapa autorizada)!")

    writer.close()
    await writer.wait_closed()

    print("\n" + "=" * 65)
    print("VERIFICAÇÃO CONCLUÍDA COM 100% DE SUCESSO!")
    print("O servidor na VPS Hostinger está plenamente operacional,")
    print("autenticando jogadores, sincronizando templates e autorizando")
    print("conexões ativas de socket no mundo do jogo!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_live_test())
