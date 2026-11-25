"""Script de validação de integração real ponta a ponta do Wartune Reborn."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote_from_bytes

import aiohttp

from wartune_server.app import GameServerApp, build_services
from wartune_server.config import Settings
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
            data = await asyncio.wait_for(self.reader.read(65536), 5)
            assert data, f"conexão fechada esperando {code}"
            self.decoder.feed(data)


async def test_full_chain() -> None:
    print("=" * 60)
    print("INICIANDO TESTE DE INTEGRAÇÃO REAL — WARTUNE REBORN")
    print("=" * 60)

    db_path = Path("data/wartune.db")
    assert db_path.exists(), f"Banco {db_path} não encontrado"
    print(f"[1/8] Banco SQLite verificado: {db_path} ({db_path.stat().st_size} bytes)")

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT id FROM game_servers WHERE id = 1")
    assert cur.fetchone() is not None, "Servidor 1 não encontrado em game_servers"

    test_user = f"auditor_{int(time.time()) % 10000}"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    cur.execute(
        "INSERT INTO accounts (username, password_hash, created_at, banned) VALUES (?, ?, ?, 0)",
        (test_user, "$2y$10$dummyhashfordiagnostictestonly", now_str),
    )
    account_id = cur.lastrowid

    ticket_token = f"TICKET_AUDIT_{int(time.time())}"
    exp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 300))
    cur.execute(
        "INSERT INTO play_tickets (token, account_id, server_id, created_at, expires_at) VALUES (?, ?, 1, ?, ?)",
        (ticket_token, account_id, now_str, exp_str),
    )
    con.commit()
    con.close()
    print(f"[2/8] Conta e ticket criados no banco: User '{test_user}', Ticket '{ticket_token}'")

    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
        public_host="127.0.0.1",
        http_port=8080,
        socket_port=5000,
        websocket_port=5001,
        policy_port=None,
        skip_tutorial=True,
    )
    services = await build_services(settings)
    app = GameServerApp(settings, services)
    stop_event = asyncio.Event()

    server_task = asyncio.create_task(app.serve(stop_event))
    await asyncio.sleep(1.0)
    print("[3/8] Servidor GameServerApp iniciado (HTTP :8080 e Socket TCP :5000)")

    try:
        temp_pass = "7654321"
        key = hashlib.md5(temp_pass.encode()).hexdigest()

        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:8080/crossdomain.xml") as resp:
                assert resp.status == 200
                print("[4/8] HTTP GET /crossdomain.xml OK (200)")

            escaped = quote_from_bytes(test_user.encode("utf-8"), safe="")
            raw_payload = f"{escaped}|{ticket_token}|{temp_pass}|0".encode()
            b64_cipher = services.keys.encrypt_b64(raw_payload)

            async with session.post("http://127.0.0.1:8080/login", data={"p": b64_cipher, "site": "local_0001"}) as resp:
                xml_login = await resp.text()
                assert 'value="true"' in xml_login
                user_id = int(re.search(r'userId="(\d+)"', xml_login).group(1))
                print(f"[5/8] HTTP POST /login OK (userId: {user_id})")

            async with session.post(
                "http://127.0.0.1:8080/visualizeregister",
                data={
                    "userid": user_id,
                    "username": test_user,
                    "nickname": f"Aud{int(time.time()) % 1000}",
                    "sex": 0,
                    "camp": 1,
                    "icon": 6,
                    "key": key,
                },
            ) as resp:
                xml_reg = await resp.text()
                assert 'value="true"' in xml_reg, f"visualizeregister falhou: {xml_reg}"
                print(f"[6/8] HTTP POST /visualizeregister OK (Personagem registrado)")

            async with session.post(
                "http://127.0.0.1:8080/updateplayernovice",
                data={"op": 1, "userid": user_id, "noviceprocess": 0, "key": key},
            ) as resp:
                assert await resp.text() == "19000"
                print("[6/8] HTTP POST /updateplayernovice OK (noviceProcess = 19000, castelo desbloqueado)")

        reader, writer = await asyncio.open_connection("127.0.0.1", 5000)
        client = FakeFlashClient(reader, writer)
        ekeys = os.urandom(8)
        client.send(20001, pb.LoginReqMsg(key=key, ekeys=list(ekeys)))
        client.rekey(ekeys)
        print("[7/8] Socket TCP conectado na porta 5000 e pacote 20001 enviado")

        got = await client.until(150)
        assert [p.code for p in got] == [3841, 3, 150]
        player = pb.PlayerMsg.FromString(got[1].body)
        print(f"[8/8] Pacote PlayerMsg (opcode 3) recebido! Nick: '{player.nickName}', Nível: {player.grades}, Novice: {player.noviceProcess}")

        flags = {f: True for f in ("castle", "army", "build", "tree", "aas", "friend", "sys", "snsReq")}
        client.send(8224, pb.PlayerDataMsg(**flags))
        await client.until(4173)

        client.send(8224, pb.PlayerDataMsg(user=True))
        login_state = await client.until(6)
        assert pb.LoginStateMsg.FromString(login_state[-1].body).playerId == user_id
        print(f"[8/8] Pacote LoginStateMsg (opcode 6) recebido com state: 0! Entrada no mundo autorizada!")

        print("=" * 60)
        print("RESULTADO: FLUXO COMPLETO 100% OPERACIONAL E HOMOLOGADO!")
        print("Portal -> Banco -> Ticket -> HTTP /login -> Criação de Herói -> Socket TCP 5000 -> Castelo/Mundo.")
        print("=" * 60)

        writer.close()
        await writer.wait_closed()
    finally:
        stop_event.set()
        await server_task
        await services.database.dispose()


if __name__ == "__main__":
    asyncio.run(test_full_chain())
