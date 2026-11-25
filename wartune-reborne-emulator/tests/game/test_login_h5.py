from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.test_end_to_end import EVENTS, TEMPLATES
from wartune_server.app import GameServerApp, build_services
from wartune_server.config import Settings
from wartune_server.game.handlers.login_h5 import (
    decode_protobuf,
    encode_field_string,
    encode_field_varint,
)
from wartune_server.protocol import Packet, PacketDecoder, StreamCipher
from wartune_server.protocol.cipher import DEFAULT_KEY
from wartune_server.protocol.messages import wartune_pb2 as pb

pytestmark = pytest.mark.skipif(not TEMPLATES.exists(), reason="precisa de data/templates/tempinfos.xml")


class FakeWsClient:
    def __init__(self, ws) -> None:  # type: ignore[no-untyped-def]
        self.ws = ws
        self.out = StreamCipher()
        self.decoder = PacketDecoder(StreamCipher())
        self.rekeyed = False

    async def send(self, code: int, body: bytes = b"", msg: object | None = None) -> None:
        raw_body = msg.SerializeToString() if msg is not None else body  # type: ignore[attr-defined]
        await self.ws.send_bytes(self.out.encrypt(Packet(code, raw_body).encode()))

    def rekey_both(self, key: bytes) -> None:
        self.rekeyed = True
        self.out.reset(key)
        self.decoder.cipher.reset(key)

    async def recv_packet(self) -> Packet:
        while (pkt := self.decoder.next_packet()) is None:
            data = await asyncio.wait_for(self.ws.receive_bytes(), 5)
            self.decoder.feed(data)
        # No pré-login H5 o servidor reseta _send_cipher para DEFAULT_KEY antes de cada resposta
        if not self.rekeyed and pkt.code in (3846, 3843, 3844, 3845, 28680):
            self.decoder.cipher.reset(DEFAULT_KEY)
        return pkt

    async def until(self, code: int) -> list[Packet]:
        got: list[Packet] = []
        while True:
            pkt = await self.recv_packet()
            got.append(pkt)
            if pkt.code == code:
                return got


async def test_h5_new_account_register_gateway_and_novice(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'h5.db'}",
        rsa_key_file=tmp_path / "rsa.pem",
        log_dir=tmp_path / "logs",
        public_host="0.0.0.0",
        skip_tutorial=False,
        events_file=EVENTS,
        _env_file=None,  # type: ignore[call-arg]
    )
    services = await build_services(settings)
    server = GameServerApp(settings, services)
    http = TestClient(TestServer(server.http_app))
    await http.start_server()
    try:
        # 1. Pré-login em WebSocket de login (/ws): conta nova deve retornar "Login Succeed No Visualize" e userId > 0
        async with http.ws_connect("/ws") as login_ws:
            client = FakeWsClient(login_ws)
            prep_req = (
                encode_field_string(1, "h5_novo")
                + encode_field_string(2, "token_abc")
                + encode_field_string(3, "senha_rnd")
                + encode_field_string(4, settings.site)
                + encode_field_varint(5, 0)
            )
            await client.send(28674, prep_req)
            rsp = await client.recv_packet()
            assert rsp.code == 3844
            fields = decode_protobuf(rsp.body)
            assert fields[1][0] == b"h5_novo"
            assert fields[3][0] == 1
            assert fields[4][0] == b"Login Succeed No Visualize"
            char_id = int(fields[5][0])
            assert char_id > 0
            assert fields[6][0] == b"wss://bots-wartune.thnsdu.easypanel.host/ws"

            # 2. Nickname inválido no L_REGISTER_ROLE deve responder value=0 e não ativar o personagem
            bad_reg = (
                encode_field_varint(1, char_id)
                + encode_field_string(2, "h5_novo")
                + encode_field_string(3, "x")
                + encode_field_varint(4, 1)
                + encode_field_varint(5, 1)
                + encode_field_varint(6, 1)
                + encode_field_string(7, settings.site)
                + encode_field_string(8, hashlib.md5(b"senha_rnd").hexdigest())
            )
            await client.send(28676, bad_reg)
            bad_rsp = await client.recv_packet()
            assert bad_rsp.code == 3845
            bad_fields = decode_protobuf(bad_rsp.body)
            assert bad_fields[3][0] == 0
            assert bad_fields[4][0] == 1

            # 3. Criação válida via HTTP /nicknamecheck + L_REGISTER_ROLE
            nick_rsp = await (await http.post("/nicknamecheck", data={"nickname": "HeroiH5", "rnd": "1"})).text()
            assert 'value="true"' in nick_rsp

            md5_pass = hashlib.md5(b"senha_rnd").hexdigest()
            ok_reg = (
                encode_field_varint(1, char_id)
                + encode_field_string(2, "h5_novo")
                + encode_field_string(3, "HeroiH5")
                + encode_field_varint(4, 1)
                + encode_field_varint(5, 1)
                + encode_field_varint(6, 1)
                + encode_field_string(7, settings.site)
                + encode_field_string(8, md5_pass)
            )
            await client.send(28676, ok_reg)
            ok_rsp = await client.recv_packet()
            assert ok_rsp.code == 3845
            assert decode_protobuf(ok_rsp.body)[3][0] == 1

        # 4. Gateway WebSocket: 20001 -> rekey -> 8224 (user/tower) -> 20008 (4234 sem resetar cifra) -> 5017
        async with http.ws_connect("/ws") as gate_ws:
            gate = FakeWsClient(gate_ws)
            ekeys = os.urandom(8)
            await gate.send(20001, msg=pb.LoginReqMsg(key=md5_pass, ekeys=list(ekeys)))
            gate.rekey_both(ekeys)
            rsp_3841 = await gate.recv_packet()
            assert rsp_3841.code == 3841
            tail = await gate.until(150)
            assert [p.code for p in tail] == [3, 150]

            await gate.send(
                8224,
                msg=pb.PlayerDataMsg(castle=True, army=True, build=True, sys=True, tower=True, aas=True),
            )
            init_pkts = await gate.until(4173)
            recover_pkt = next(p for p in init_pkts if p.code == 4912)
            assert recover_pkt.body == b""

            await gate.send(8224, msg=pb.PlayerDataMsg(user=True))
            user_pkts = await gate.until(6)
            assert any(p.code == 4177 for p in user_pkts)
            sign_pkt = next(p for p in user_pkts if p.code == 4177)
            assert pb.PlayerSignRspMsg.FromString(sign_pkt.body).signDate
            rate_pkt = next(p for p in user_pkts if p.code == 4247)
            assert rate_pkt.body == b""

            # Heartbeat 20008 retorna 4234 mantendo a chave de sessão ekeys (não DEFAULT_KEY)
            await gate.send(20008, msg=pb.SynchronizedTimeMsg())
            sync_pkts = await gate.until(4234)
            assert any(p.code == 4234 for p in sync_pkts)

            # Tutorial H5 (5017 tag 8 = newNoviceProcess 150) persiste e volta em tag 136 do PlayerMsg (3) antes do S_NOVICE (1)
            await gate.send(5017, body=encode_field_varint(8, 150))
            novice_pkts = await gate.until(1)
            player_pkt = next(p for p in reversed(novice_pkts) if p.code == 3)
            assert decode_protobuf(player_pkt.body)[136][0] == b"_150"
    finally:
        await http.close()
        server.acceptor.close_all()
        await services.database.dispose()


async def test_h5_login_with_existing_character_and_skip_tutorial(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'h5_skip.db'}",
        rsa_key_file=tmp_path / "rsa.pem",
        log_dir=tmp_path / "logs",
        skip_tutorial=True,
        events_file=EVENTS,
        _env_file=None,  # type: ignore[call-arg]
    )
    services = await build_services(settings)
    server = GameServerApp(settings, services)
    http = TestClient(TestServer(server.http_app))
    await http.start_server()
    try:
        async with http.ws_connect("/ws") as login_ws:
            client = FakeWsClient(login_ws)
            prep = (
                encode_field_string(1, "h5_skip")
                + encode_field_string(3, "pwd123")
                + encode_field_string(4, settings.site)
            )
            await client.send(28674, prep)
            rsp = await client.recv_packet()
            char_id = int(decode_protobuf(rsp.body)[5][0])
            md5_pass = hashlib.md5(b"pwd123").hexdigest()
            reg = (
                encode_field_varint(1, char_id)
                + encode_field_string(2, "h5_skip")
                + encode_field_string(3, "SkipH5")
                + encode_field_varint(4, 1)
                + encode_field_varint(5, 1)
                + encode_field_varint(6, 1)
                + encode_field_string(7, settings.site)
                + encode_field_string(8, md5_pass)
            )
            await client.send(28676, reg)
            assert decode_protobuf((await client.recv_packet()).body)[3][0] == 1

            # Segundo prepare_login da mesma conta já ativa retorna "succeed"
            await client.send(28674, prep)
            rsp2 = await client.recv_packet()
            f2 = decode_protobuf(rsp2.body)
            assert f2[4][0] == b"succeed"
            assert int(f2[5][0]) == char_id

        async with http.ws_connect("/ws") as gate_ws:
            gate = FakeWsClient(gate_ws)
            ekeys = os.urandom(8)
            await gate.send(20001, msg=pb.LoginReqMsg(key=md5_pass, ekeys=list(ekeys)))
            gate.rekey_both(ekeys)
            tail = await gate.until(150)
            p_msg = next(p for p in tail if p.code == 3)
            new_novice = decode_protobuf(p_msg.body)[136][0].decode()
            assert "5" in new_novice.split("_") and "150" in new_novice.split("_")
    finally:
        await http.close()
        server.acceptor.close_all()
        await services.database.dispose()
