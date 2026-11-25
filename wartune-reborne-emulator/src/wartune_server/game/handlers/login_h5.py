"""Handlers para o protocolo de login do cliente H5 / Web (LayaAir).

Sequência do cliente H5:
1. 28678 (0x7006) L_CREATE_LOGIN: handshake inicial e identificação da conta
   -> Responde 3846 (0x0F06) U_L_CREATE_LOGIN_RSP com result=0 (SUCCEED)
2. 28672 (0x7000) L_GET_PLAYER_LIST: consulta de personagens
   -> Responde 3843 (0x0F03) U_L_GET_PLAYER_LIST com lista de SimpleUserInfo
3. 28674 (0x7002) L_PREPARE_LOGIN: preparação de conexão ao gateway
   -> Responde 3844 (0x0F04) U_L_PREPARE_LOGIN com result=True e gateIp/port
4. 28676 (0x7004) L_REGISTER_ROLE: criação de personagem caso não possua
   -> Responde 3845 (0x0F05) U_L_REGISTER_ROLE_RSP com value=True e dados do personagem
5. 28680 (0x7008) L_SYNC_TIME: sincronização periódica de relógio e heartbeat
   -> Responde 4234 (0x108A) U_C_SYNCHRONIZED_TIME
6. 20001 (0x4E21) G_LOGIN_GATEWAY: entrada final no jogo (atendido por login.py)
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ...domain.models import Account, Character
from ...protocol import Packet
from ...services.characters import RegistrationRequest
from ...services.login import PendingLogin
from ..router import router

if TYPE_CHECKING:
    from ..session import GameSession

# Opcodes de login H5
L_GET_PLAYER_LIST = 28672    # 0x7000
L_PREPARE_LOGIN = 28674      # 0x7002
L_REGISTER_ROLE = 28676      # 0x7004
L_CREATE_LOGIN = 28678       # 0x7006
L_SYNC_TIME = 28680          # 0x7008

U_L_GET_PLAYER_LIST = 3843   # 0x0F03
U_L_PREPARE_LOGIN = 3844     # 0x0F04
U_L_REGISTER_ROLE_RSP = 3845 # 0x0F05
U_L_CREATE_LOGIN_RSP = 3846  # 0x0F06
U_C_SYNCHRONIZED_TIME = 4234 # 0x108A


# -- Helpers de codificação e decodificação protobuf Wire Format --
def encode_varint(val: int) -> bytes:
    bits = val & 0x7FFFFFFFFFFFFFFF
    out = bytearray()
    while True:
        b = bits & 0x7F
        bits >>= 7
        if bits:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def encode_field_varint(tag: int, val: int) -> bytes:
    return encode_varint((tag << 3) | 0) + encode_varint(val)


def encode_field_string(tag: int, s: str) -> bytes:
    raw = s.encode("utf-8")
    return encode_varint((tag << 3) | 2) + encode_varint(len(raw)) + raw


def encode_field_bytes(tag: int, raw: bytes) -> bytes:
    return encode_varint((tag << 3) | 2) + encode_varint(len(raw)) + raw


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    shift = 0
    val = 0
    while True:
        v = data[pos]
        pos += 1
        val |= (v & 0x7F) << shift
        if not (v & 0x80):
            return val, pos
        shift += 7


def decode_protobuf(data: bytes) -> dict[int, list[Any]]:
    """Decodifica um payload protobuf em mapa tag -> valores."""
    pos = 0
    length = len(data)
    fields: dict[int, list[Any]] = {}

    while pos < length:
        key, pos = _read_varint(data, pos)
        tag = key >> 3
        wire_type = key & 7

        if wire_type == 0:  # varint
            val, pos = _read_varint(data, pos)
            fields.setdefault(tag, []).append(val)
        elif wire_type == 2:  # length-delimited (string / bytes / submessage)
            field_len, pos = _read_varint(data, pos)
            field_data = data[pos : pos + field_len]
            pos += field_len
            fields.setdefault(tag, []).append(field_data)
        elif wire_type == 1:  # 64-bit
            fields.setdefault(tag, []).append(data[pos : pos + 8])
            pos += 8
        elif wire_type == 5:  # 32-bit
            fields.setdefault(tag, []).append(data[pos : pos + 4])
            pos += 4
        else:
            break

    return fields


def _server_id(s: GameSession) -> int:
    if getattr(s.ctx, "settings", None) and hasattr(s.ctx.settings, "server_id"):
        return int(s.ctx.settings.server_id)
    return getattr(s.ctx.login, "_server_id", 1)


def _site(s: GameSession) -> str:
    if getattr(s.ctx, "settings", None) and hasattr(s.ctx.settings, "site"):
        return str(s.ctx.settings.site)
    return "local_0001"


def _websocket_port(s: GameSession) -> int:
    if getattr(s.ctx, "settings", None) and hasattr(s.ctx.settings, "websocket_port"):
        return int(s.ctx.settings.websocket_port)
    return 5001


def _get_gate_ip(s: GameSession) -> str:
    host = ""
    if getattr(s.ctx, "settings", None) and hasattr(s.ctx.settings, "public_host"):
        host = s.ctx.settings.public_host
    if not host or host == "0.0.0.0":
        host = "bots-wartune.thnsdu.easypanel.host"
    if host.startswith("ws://") or host.startswith("wss://"):
        return host
    if host in ("127.0.0.1", "localhost"):
        return f"ws://{host}:{_websocket_port(s)}/ws"
    return f"wss://{host}/ws"


@router.on(L_CREATE_LOGIN)
async def handle_create_login(s: GameSession, _: Any) -> None:
    raw_body = s.packet.body if s.packet else b""
    fields = decode_protobuf(raw_body)
    username = fields.get(1, [b""])[0]
    username_str = username.decode("utf-8", errors="ignore") if isinstance(username, bytes) else str(username)
    site = fields.get(3, [b""])[0]
    site_str = site.decode("utf-8", errors="ignore") if isinstance(site, bytes) else str(site)

    if not username_str:
        username_str = f"Guest_{secrets.token_hex(3)}"

    # Garante que a conta existe no banco
    now = s.ctx.clock.now() if s.ctx.clock else datetime.now(UTC)
    async def get_or_create_account(uow: Any) -> Account:
        acc = await uow.accounts.by_username(username_str)
        if acc is None:
            acc = await uow.accounts.add(Account(username=username_str, password_hash="h5_login", created_at=now))
        return acc

    await s.ctx.characters.write(get_or_create_account)

    # Resposta: userName (tag 1), site (tag 2), result=0 (tag 3, SUCCEED)
    rsp_body = (
        encode_field_string(1, username_str)
        + encode_field_string(2, site_str or _site(s))
        + encode_field_varint(3, 0)
    )
    s.connection.send(Packet(U_L_CREATE_LOGIN_RSP, rsp_body, 0))
    s.log.info("H5 L_CREATE_LOGIN atendido", username=username_str)


@router.on(L_GET_PLAYER_LIST)
async def handle_get_player_list(s: GameSession, _: Any) -> None:
    raw_body = s.packet.body if s.packet else b""
    fields = decode_protobuf(raw_body)
    username = fields.get(1, [b""])[0]
    username_str = username.decode("utf-8", errors="ignore") if isinstance(username, bytes) else str(username)
    site = fields.get(3, [b""])[0]
    site_str = site.decode("utf-8", errors="ignore") if isinstance(site, bytes) else str(site)

    sid = _server_id(s)
    async def get_characters(uow: Any) -> list[Character]:
        acc = await uow.accounts.by_username(username_str)
        if acc is None or acc.id is None:
            return []
        c = await uow.characters.by_account(acc.id, sid)
        if c and c.active:
            return [c]
        return []

    characters: list[Character] = await s.ctx.characters.read(get_characters)

    rsp_body = bytearray()
    for c in characters:
        info = (
            encode_field_varint(1, c.id or 0)
            + encode_field_string(2, username_str)
            + encode_field_string(3, c.nickname or "")
            + encode_field_varint(4, getattr(c, "grades", 1) or 1)
            + encode_field_varint(5, 0)  # repute
            + encode_field_varint(6, getattr(c, "sex", 1) or 1)
            + encode_field_varint(7, 0)  # rename
            + encode_field_varint(8, 1)  # active
            + encode_field_string(9, site_str or _site(s))
            + encode_field_varint(10, 0) # isOnline
        )
        rsp_body += encode_field_bytes(1, info)

    rsp_body += encode_field_string(2, username_str)
    rsp_body += encode_field_string(3, site_str or _site(s))
    rsp_body += encode_field_varint(4, 0)  # loginState = 0 (OK)

    s.connection.send(Packet(U_L_GET_PLAYER_LIST, bytes(rsp_body), 0))
    s.log.info("H5 L_GET_PLAYER_LIST atendido", username=username_str, chars=len(characters))


@router.on(L_PREPARE_LOGIN)
async def handle_prepare_login(s: GameSession, _: Any) -> None:
    raw_body = s.packet.body if s.packet else b""
    fields = decode_protobuf(raw_body)
    username = fields.get(1, [b""])[0]
    username_str = username.decode("utf-8", errors="ignore") if isinstance(username, bytes) else str(username)
    password_val = fields.get(3, [b""])[0]
    password_str = (
        password_val.decode("utf-8", errors="ignore") if isinstance(password_val, bytes) else str(password_val)
    )
    site = fields.get(4, [b""])[0]
    site_str = site.decode("utf-8", errors="ignore") if isinstance(site, bytes) else str(site)

    now = s.ctx.clock.now() if s.ctx.clock else datetime.now(UTC)
    sid = _server_id(s)

    async def find_character(uow: Any) -> tuple[int, int, bool]:
        acc = await uow.accounts.by_username(username_str)
        if acc is None or acc.id is None:
            return 0, 0, False
        c = await uow.characters.by_account(acc.id, sid)
        if c and c.id:
            return acc.id, c.id, bool(c.active)
        return acc.id, 0, False

    acc_id, found_char_id, is_active = await s.ctx.characters.read(find_character)
    if not acc_id or not found_char_id:
        async def ensure_character(uow: Any) -> tuple[int, int, bool]:
            acc = await uow.accounts.by_username(username_str)
            if acc is None:
                acc = await uow.accounts.add(Account(username=username_str, password_hash="h5_prep", created_at=now))
            assert acc.id is not None
            c = await uow.characters.by_account(acc.id, sid)
            if c is None:
                c = await uow.characters.add(Character(acc.id, sid, now))
            assert c.id is not None
            return acc.id, c.id, bool(c.active)

        acc_id, found_char_id, is_active = await s.ctx.characters.write(ensure_character)

    gate_ip = _get_gate_ip(s)

    # Registra sessão de login para ser validada no socket_login (20001) inclusive antes da criação do personagem
    md5_key = hashlib.md5(password_str.encode("utf-8")).hexdigest()
    s.ctx.login._sessions.put(PendingLogin(md5_key, acc_id, username_str, sid, found_char_id, now))
    if password_str:
        s.ctx.login._sessions.put(PendingLogin(password_str, acc_id, username_str, sid, found_char_id, now))

    msg_str = "succeed" if is_active else "Login Succeed No Visualize"

    rsp_body = (
        encode_field_string(1, username_str)
        + encode_field_string(2, site_str or _site(s))
        + encode_field_varint(3, 1)  # result = True
        + encode_field_string(4, msg_str)
        + encode_field_varint(5, found_char_id)
        + encode_field_string(6, gate_ip)
        + encode_field_varint(7, _websocket_port(s))
        + encode_field_varint(8, 1)  # todayFirstLogin = True
    )
    s.connection.send(Packet(U_L_PREPARE_LOGIN, rsp_body, 0))
    s.log.info(
        "H5 L_PREPARE_LOGIN atendido", username=username_str, user_id=found_char_id, status=msg_str, gate=gate_ip
    )


@router.on(L_REGISTER_ROLE)
async def handle_register_role(s: GameSession, _: Any) -> None:
    raw_body = s.packet.body if s.packet else b""
    fields = decode_protobuf(raw_body)
    username = fields.get(2, [b""])[0]
    username_str = username.decode("utf-8", errors="ignore") if isinstance(username, bytes) else str(username)
    nickname = fields.get(3, [b""])[0]
    nickname_str = nickname.decode("utf-8", errors="ignore") if isinstance(nickname, bytes) else str(nickname)
    sex = fields.get(4, [1])[0]
    camp = fields.get(5, [1])[0]
    icon = fields.get(6, [1])[0]
    site = fields.get(7, [b""])[0]
    site_str = site.decode("utf-8", errors="ignore") if isinstance(site, bytes) else str(site)
    md5_pass = fields.get(8, [b""])[0]
    md5_pass_str = md5_pass.decode("utf-8", errors="ignore") if isinstance(md5_pass, bytes) else str(md5_pass)

    now = s.ctx.clock.now() if s.ctx.clock else datetime.now(UTC)
    sid = _server_id(s)

    async def get_or_create_char(uow: Any) -> tuple[int, int, bool]:
        acc = await uow.accounts.by_username(username_str)
        if acc is None:
            acc = await uow.accounts.add(Account(username=username_str, password_hash="h5_reg", created_at=now))
        assert acc.id is not None
        c = await uow.characters.by_account(acc.id, sid)
        if c is None:
            c = await uow.characters.add(Character(acc.id, sid, now))
        assert c.id is not None
        return acc.id, c.id, bool(c.active)

    acc_id, char_id, was_active = await s.ctx.characters.write(get_or_create_char)

    req = RegistrationRequest(
        character_id=char_id,
        nickname=nickname_str or f"Player_{secrets.token_hex(2)}",
        sex=sex,
        camp=camp,
        icon=icon or 1,
    )
    gate_ip = _get_gate_ip(s)
    if not was_active:
        try:
            created_char = await s.ctx.characters.register(req)
            char_id = created_char.id or char_id
        except Exception as exc:
            s.log.error("falha ao registrar personagem H5", erro=str(exc))
            err_body = (
                encode_field_string(1, username_str)
                + encode_field_string(2, site_str or _site(s))
                + encode_field_varint(3, 0)  # value = False
                + encode_field_varint(4, 1)  # type = 1 (erro)
                + encode_field_string(5, str(exc))
                + encode_field_string(6, gate_ip)
                + encode_field_varint(7, _websocket_port(s))
                + encode_field_varint(8, char_id)
            )
            s.connection.send(Packet(U_L_REGISTER_ROLE_RSP, err_body, 0))
            return

    # Registra a sessão de login com o md5Password
    if md5_pass_str:
        s.ctx.login._sessions.put(PendingLogin(md5_pass_str, acc_id, username_str, sid, char_id, now))

    rsp_body = (
        encode_field_string(1, username_str)
        + encode_field_string(2, site_str or _site(s))
        + encode_field_varint(3, 1)  # value = True
        + encode_field_varint(4, 0)  # type = 0 (OK)
        + encode_field_string(5, "ok")
        + encode_field_string(6, gate_ip)
        + encode_field_varint(7, _websocket_port(s))
        + encode_field_varint(8, char_id)
    )
    s.connection.send(Packet(U_L_REGISTER_ROLE_RSP, rsp_body, 0))
    s.log.info("H5 L_REGISTER_ROLE atendido", username=username_str, char_id=char_id, gate=gate_ip)


@router.on(L_SYNC_TIME)
async def handle_sync_time(s: GameSession, _: Any) -> None:
    now = s.ctx.clock.now() if s.ctx.clock else datetime.now(UTC)
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    millis = int(now.timestamp() * 1000)
    # SynchronizedTimeMsg: sysCurtime (tag 1, string), sysMillisecond (tag 2, int64)
    rsp_body = encode_field_string(1, time_str) + encode_field_varint(2, millis)
    s.connection.send(Packet(U_C_SYNCHRONIZED_TIME, rsp_body, 0))


def h5_novice_process(s: GameSession) -> str:
    """Monta a string ``newNoviceProcess`` (tag 136 do PlayerMsg no H5, separada por ``_``)."""
    from .. import events as ev

    snap = s.snapshot
    if snap is None:
        return ""
    st = ev.peek(snap, "h5_novice")
    nodes = [part for part in (st.text if st else "").split("_") if part]
    skip = bool(getattr(getattr(s.ctx, "settings", None), "skip_tutorial", False))
    if skip or snap.character.novice_process >= 19000:
        for req_node in ("5", "10", "70", "150", "200"):
            if req_node not in nodes:
                nodes.append(req_node)
    return "_" + "_".join(nodes) if nodes else ""


def encode_h5_message(s: GameSession, code: int, message: Any) -> bytes:
    """Adapta mensagens cujo layout protobuf difere entre o cliente Flash e o H5."""
    if code == 3:
        from ...protocol.messages import wartune_pb2 as pb

        # Tags 1..87 coincidem entre Flash e H5; a partir da 88 há divergências (ex.: tag 136 no Flash é int32)
        h5_msg = pb.PlayerMsg()
        h5_msg.CopyFrom(message)
        for field in h5_msg.DESCRIPTOR.fields:
            if field.number > 87:
                h5_msg.ClearField(field.name)
        raw = h5_msg.SerializeToString()
        if message.HasField("hasVicePassword"):
            raw += encode_field_varint(88, message.hasVicePassword)
        if message.HasField("isDuringToResetTime"):
            raw += encode_field_varint(89, message.isDuringToResetTime)
        if message.HasField("terraTempleCount"):
            raw += encode_field_varint(126, message.terraTempleCount)
        if message.HasField("terraTempleMaxCount"):
            raw += encode_field_varint(127, message.terraTempleMaxCount)
        if message.HasField("lastFreeSkillLearnTime"):
            raw += encode_field_string(130, message.lastFreeSkillLearnTime)
        if message.HasField("guardWarCount"):
            raw += encode_field_varint(143, message.guardWarCount)
        if message.HasField("guardWarMaxCount"):
            raw += encode_field_varint(144, message.guardWarMaxCount)
        new_novice = h5_novice_process(s)
        if new_novice:
            raw += encode_field_string(136, new_novice)
        return raw
    if code == 4247:
        # No H5, RateUpdateReqMsg carrega os campos de taxa diretamente sem repeated rateInfo
        rates = getattr(message, "rateInfo", None) or ()
        active = next((r for r in rates if getattr(r, "rate", 0) > 0), None)
        if active is None:
            return b""
        return (
            encode_field_varint(1, active.rate)
            + encode_field_varint(2, active.beginTime)
            + encode_field_varint(3, active.endTime)
            + encode_field_string(4, active.beginDay)
            + encode_field_string(5, active.endDay)
            + encode_field_varint(6, active.bufferType)
        )
    if code == 4912:
        # No H5, RecoverInfosMsg usa openState, freeGp, freeGold, otherGp e otherGold (tags 1..5 int32)
        rows = getattr(message, "recoverInfos", None) or ()
        if not rows:
            return b""
        free_gp = sum(getattr(r, "goldReward", 0) for r in rows if getattr(r, "masterType", 0) == 1)
        free_gold = sum(getattr(r, "goldReward", 0) for r in rows if getattr(r, "masterType", 0) == 2)
        other_gp = sum(getattr(r, "itemReward", 0) for r in rows if getattr(r, "masterType", 0) == 1)
        other_gold = sum(getattr(r, "itemReward", 0) for r in rows if getattr(r, "masterType", 0) == 2)
        return (
            encode_field_varint(1, 1)
            + encode_field_varint(2, free_gp)
            + encode_field_varint(3, free_gold)
            + encode_field_varint(4, other_gp)
            + encode_field_varint(5, other_gold)
        )
    return message.SerializeToString()


DEFAULT_H5_SYSTEM_IDS = (101, 102, 103, 104, 107, 121, 122, 124, 125, 127, 128, 129, 135, 136, 139, 155, 163, 183)


def send_h5_system_open(s: GameSession) -> None:
    """Envia ``537 U_C_SYSTEMOPEN_ALLREADY`` (``SystemOpenHashOpenList``) para liberar ícones/mochila no H5."""
    if not getattr(s, "is_h5", False):
        return
    sys_ids = getattr(s.ctx.templates, "h5_system_open", ()) or DEFAULT_H5_SYSTEM_IDS
    packed = b"".join(encode_varint(sid) for sid in sys_ids)
    body = b"\x0a" + encode_varint(len(packed)) + packed
    s.connection.send(Packet(537, body, s.connection.client_id))
