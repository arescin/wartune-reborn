from __future__ import annotations

import asyncio

from wartune_server.net.connection import POLICY_XML, Connection
from wartune_server.protocol import Packet, PacketDecoder, StreamCipher
from wartune_server.protocol.registry import MessageRegistry


class FakeTransport:
    peer = "test"

    def __init__(self, chunks: list[bytes]) -> None:
        self._in: asyncio.Queue[bytes] = asyncio.Queue()
        for c in chunks:
            self._in.put_nowait(c)
        self.sent = bytearray()

    def finish(self) -> None:
        self._in.put_nowait(b"")

    async def read(self) -> bytes:
        return await self._in.get()

    async def write(self, data: bytes) -> None:
        self.sent += data

    async def close(self) -> None:
        pass


NEW_KEY = bytes(range(10, 18))


class EchoRekey:
    """Responde cada pacote com code+1; no 20001 troca a chave (como o jogo)."""

    def __init__(self, conn: Connection, transport: FakeTransport) -> None:
        self.conn, self.transport = conn, transport
        self.got: list[Packet] = []
        self.disconnected = False

    async def on_packet(self, packet: Packet) -> None:
        self.got.append(packet)
        self.conn.send(Packet(packet.code + 1, packet.body))
        if packet.code == 20001:
            self.conn.rekey(NEW_KEY)
        if len(self.got) == 2:
            self.transport.finish()

    async def on_disconnect(self) -> None:
        self.disconnected = True


async def test_rekey_applies_to_both_directions_in_order() -> None:
    client = StreamCipher()
    wire = client.encrypt(Packet(20001, b"login").encode())
    client.reset(NEW_KEY)
    wire += client.encrypt(Packet(8224, b"next").encode())  # chega no mesmo bloco

    transport = FakeTransport([wire])
    conn = Connection(transport, MessageRegistry.load_default(), conn_id=1)
    handler = EchoRekey(conn, transport)
    await asyncio.wait_for(conn.run(handler), 5)

    assert [p.code for p in handler.got] == [20001, 8224]
    assert handler.disconnected
    # resposta ao 20001 sai com a chave antiga, a seguinte com a nova
    decoder = PacketDecoder(StreamCipher())
    decoder.feed(bytes(transport.sent))
    assert decoder.next_packet() == Packet(20002, b"login")
    decoder.cipher.reset(NEW_KEY)
    assert decoder.next_packet() == Packet(8225, b"next")


async def test_policy_request_on_game_port() -> None:
    transport = FakeTransport([b"<policy-file-request/>\x00"])
    conn = Connection(transport, MessageRegistry.load_default(), conn_id=2)
    handler = EchoRekey(conn, transport)
    await asyncio.wait_for(conn.run(handler), 5)
    assert bytes(transport.sent) == POLICY_XML and not handler.got


async def test_4234_after_rekey_preserves_session_cipher() -> None:
    client = StreamCipher()
    wire = client.encrypt(Packet(20001, b"login").encode())
    client.reset(NEW_KEY)
    wire += client.encrypt(Packet(20008, b"ping").encode())

    transport = FakeTransport([wire])
    conn = Connection(transport, MessageRegistry.load_default(), conn_id=3)

    class H5RekeyHandler:
        async def on_packet(self, packet: Packet) -> None:
            if packet.code == 20001:
                conn.send(Packet(3841, b"ok"))
                conn.rekey(NEW_KEY)
            elif packet.code == 20008:
                conn.send(Packet(4234, b"time"))
                transport.finish()

        async def on_disconnect(self) -> None:
            pass

    await asyncio.wait_for(conn.run(H5RekeyHandler()), 5)
    decoder = PacketDecoder(StreamCipher())
    decoder.feed(bytes(transport.sent))
    assert decoder.next_packet() == Packet(3841, b"ok")
    decoder.cipher.reset(NEW_KEY)
    assert decoder.next_packet() == Packet(4234, b"time")
