"""HTTP do jogo e portal web integrado.

Endpoints do jogo:
* ``crossdomain.xml`` - política de segurança Flash
* ``loginselectlist`` - URLLoader texto; lê ``..Item[0]@ID`` e ``@Active``.
* ``login``/``login2`` - ``LoginQueue``: exige ``@message`` presente, ``@userId != 0`` e ``@value != "false"``.
* ``visualizeregister`` - LoaderManagerII tipo 7 (XML cru): ``@value == "true"`` e ``@type`` 0|3.
* ``updateplayernovice`` - corpo é um inteiro (o ``noviceProcess`` atual).
* ``maillist`` - correio em zlib.
* ``nicknamecheck`` - checagem de apelido.
* ``flashversionservlet`` - retorna "true".
* ``images/{tail}`` - redirecionamento para CDN.

Endpoints do portal e Web:
* ``/`` - Portal Web com status, formulário de login e links de acesso
* ``/play`` - Página com player Ruffle incorporado e socketProxy
* ``/config.xml`` e ``/client-config.php`` - Configuração dinâmica do cliente Flash
* ``/ws`` - Ponte WebSocket para o socketProxy do Ruffle (evita Mixed Content)
* ``/api/auth`` - Emissão de contas e tickets de jogo
* ``/cdn/{tail}`` - Proxy reverso inteligente para assets Flash com cache local
"""

from __future__ import annotations

import hashlib
import hmac
import json
import lzma
import re
import secrets
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from xml.sax.saxutils import quoteattr

import aiohttp
import structlog
from aiohttp import web
from aiohttp.typedefs import Handler
from sqlalchemy import update

from ..config import Settings
from ..domain.errors import DomainError, NotFoundError, ValidationError
from ..domain.models import Account, Mail, MailAnnex, PlayTicket
from ..domain.repositories import UnitOfWork, UnitOfWorkFactory
from ..game import mail as mailbox
from ..game.session import OnlinePlayers
from ..persistence.schema import accounts
from ..security.rsa_keys import LoginKeyPair
from ..services.characters import NAME_TAKEN, CharacterService, RegistrationRequest, character_name
from ..services.clock import Clock
from ..services.login import LoginService
from .admin_api import AdminHttpApi
from .views import render_play_html, render_portal_html

if TYPE_CHECKING:
    from ..game.session import GameContext
    from ..net.servers import ConnectionAcceptor

log = structlog.get_logger(__name__)

CROSSDOMAIN = '<?xml version="1.0"?><cross-domain-policy><allow-access-from domain="*" /></cross-domain-policy>'
TUTORIAL_DONE = 19000  # BaseManager: noviceProcess >= 19000 entra direto no castelo


def deobfuscate_module(data: bytes) -> bytes:
    """Desobfusca módulos SWF e assets da 7Road para SWFs CWS/FWS válidos para Ruffle e Flash."""
    # Remove cabeçalho customizado road7...
    if data.startswith(b"road72b76ed34d25c411d32f432fe47a5dfda") or data.startswith(b"road7"):
        data = data[37:]

    # Já é SWF padrão limpo
    if data.startswith(b"CWS") or data.startswith(b"FWS"):
        return data

    # Se for LZMA (ZWS), converte para CWS padrão (Flash 6+)
    if data.startswith(b"ZWS") and len(data) > 17:
        try:
            version = data[3]
            uncompressed_len = int.from_bytes(data[4:8], "little") - 8
            props = data[12:17]
            raw_data = data[17:]
            d_size = int.from_bytes(props[1:5], "little")
            b0 = props[0]
            pb = b0 // (9 * 5)
            b0 %= (9 * 5)
            lp = b0 // 9
            lc = b0 % 9
            filters = [{"id": lzma.FILTER_LZMA1, "dict_size": d_size, "lc": lc, "lp": lp, "pb": pb}]
            dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters)
            raw_swf = dec.decompress(raw_data)
            return b"CWS" + bytes([version]) + data[4:8] + zlib.compress(raw_swf)
        except Exception:
            return data

    # Módulo transposto 7Road (ex: 2.png, 3.png...)
    if len(data) > 142 and not data.startswith(b"\x89PNG"):
        try:
            out = bytearray(len(data) - 21 + 3)
            out[0:3] = b"CWS"
            chunk1 = len(data) - 21 - 121
            out[124 : 124 + chunk1] = data[21 : 21 + chunk1]
            out[3:124] = data[21 + chunk1 :]
            # Validação via descompressão parcial
            zlib.decompressobj().decompress(out[8:1000])
            return bytes(out)
        except Exception:
            pass

    return data


def xml_result(value: bool, message: str = "", **attrs: object) -> web.Response:
    extra = "".join(f" {k}={quoteattr(str(v))}" for k, v in attrs.items())
    result = f'<Result value="{str(value).lower()}" message={quoteattr(message)}{extra}/>'
    body = f'<?xml version="1.0" encoding="UTF-8"?>{result}'
    return web.Response(text=body, content_type="text/xml", charset="utf-8")


def _int(params: dict[str, str], name: str) -> int:
    try:
        return int(params.get(name, ""))
    except ValueError:
        raise ValidationError(f"parâmetro {name} inválido") from None


async def _params(request: web.Request) -> dict[str, str]:
    params = dict(request.query)
    if request.method == "POST":
        params.update({k: v for k, v in (await request.post()).items() if isinstance(v, str)})
    return params


@dataclass(frozen=True, slots=True)
class HttpDeps:
    settings: Settings
    login: LoginService
    characters: CharacterService
    online: OnlinePlayers = field(default_factory=OnlinePlayers)
    uow: UnitOfWorkFactory | None = None
    keys: LoginKeyPair | None = None
    clock: Clock | None = None
    acceptor: ConnectionAcceptor | None = None
    ctx: GameContext | None = None


def _resolve_case_insensitive(base: Path, parts: list[str]) -> Path | None:
    curr = base
    for part in parts:
        if not curr.is_dir():
            return None
        exact = curr / part
        if exact.exists():
            curr = exact
            continue
        part_lower = part.lower()
        matched = None
        try:
            for entry in curr.iterdir():
                if entry.name.lower() == part_lower:
                    matched = entry
                    break
        except OSError:
            return None
        if matched is None:
            return None
        curr = matched
    return curr if curr.is_file() else None


def find_cdn_file(rel_path: str) -> Path | None:
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p and p != "."]
    if not parts or ".." in parts:
        return None
    for root in (Path("bundled_cdn"), Path("data/cdn")):
        exact = root.joinpath(*parts)
        if exact.is_file():
            return exact
        res = _resolve_case_insensitive(root, parts)
        if res is not None:
            return res
    return None


class GameHttpApi:
    def __init__(self, deps: HttpDeps) -> None:
        self._d = deps

    def routes(self, app: web.Application) -> None:
        r = app.router
        # Portal Web e Ruffle Player
        r.add_get("/", self.portal_home)
        r.add_get("/favicon.ico", self.favicon)
        r.add_get("/play", self.portal_play)
        r.add_get("/projector", self.portal_projector)
        r.add_get("/config.xml", self.client_config)
        r.add_get("/client-config.php", self.client_config)
        r.add_get("/ws", self.ws_bridge)
        r.add_get("/ws/", self.ws_bridge)
        r.add_post("/api/auth", self.api_auth)
        r.add_post("/api/player/register", self.api_player_register)
        r.add_post("/api/player/login", self.api_player_login)
        r.add_get("/cdn/{tail:.+}", self.cdn_proxy)
        r.add_get("/code_md5.dat", self.code_md5)
        r.add_get("/res_md5.dat", self.res_md5)
        r.add_get("/size.xml", self.size_xml)

        # Endpoints Flash 7Road e H5
        r.add_route("*", "/clientsiteinfoservlet", self.client_site_info)
        r.add_route("*", "/order/clientsiteinfoservlet", self.client_site_info)
        r.add_route("*", "/xml/version.json", self.version_json)
        r.add_route("*", "/version.json", self.version_json)
        r.add_get("/api/debug_logs", self.debug_logs)
        r.add_post("/clientlog", self.client_log)
        r.add_get("/crossdomain.xml", self.crossdomain)
        r.add_route("*", "/loginselectlist", self.select_list)
        r.add_post("/login", self.http_login)
        r.add_post("/login2", self.http_login)
        r.add_route("*", "/visualizeregister", self.register)
        r.add_post("/updateplayernovice", self.novice)
        r.add_route("*", "/flashversionservlet", self.plain_true)
        r.add_post("/maillist", self.mail_list)  # EmailManager.getMailList
        r.add_route("*", "/nicknamecheck", self.nickname_check)  # RenameView, antes do 8345
        r.add_post("/questionreplaylist", self.empty_list)  # CustomerServiceManager: respostas do suporte
        r.add_get("/images/{tail:.+}", self.images)  # ShopManager: ícones das ofertas (4238 ``url``)
        if self._d.settings.gm_secret:  # sem segredo a rota nem existe (a porta é pública)
            r.add_post("/gm/kick", self.gm_kick)
            r.add_post("/gm/ban", self.gm_ban)
        AdminHttpApi(self._d).routes(app)

    # -- portal e web player -----------------------------------------------------------
    def _base_url(self, request: web.Request) -> str:
        scheme = request.headers.get("X-Forwarded-Proto") or request.scheme
        host = request.headers.get("X-Forwarded-Host") or request.host
        return f"{scheme}://{host}"

    async def portal_home(self, request: web.Request) -> web.Response:
        """Página inicial com status do servidor e formulário de entrada."""
        suggested = f"Guerreiro_{secrets.token_hex(2)}"
        base_url = self._base_url(request)
        html_content = render_portal_html(
            server_name=self._d.settings.server_name,
            online_count=len(self._d.online),
            public_host=self._d.settings.public_host,
            socket_port=self._d.settings.socket_port,
            suggested_user=suggested,
            base_url=base_url,
        )
        return web.Response(
            text=html_content,
            content_type="text/html",
            charset="utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    async def portal_projector(self, request: web.Request) -> web.Response:
        """Emite o ticket e redireciona (302) para o Loading.swf com todas as flashvars."""
        username = request.query.get("user", "").strip() or f"Player_{secrets.token_hex(2)}"
        ticket_token = secrets.token_hex(16)
        s = self._d.settings
        if self._d.uow is not None:
            now = self._d.clock.now() if self._d.clock else datetime.now(UTC)
            async with self._d.uow() as uow:
                account = await uow.accounts.by_username(username)
                if account is None or account.id is None:
                    account = await uow.accounts.add(
                        Account(username=username, password_hash="auto_projector", created_at=now)
                    )
                    await uow.commit()

                ticket = PlayTicket(
                    token=ticket_token,
                    account_id=account.id,
                    server_id=s.server_id,
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
                await uow.tickets.add(ticket)
                await uow.commit()

        base_url = self._base_url(request)
        target = (
            f"{base_url}/cdn/Loading.swf?user={username}&key={ticket_token}&site={s.site}"
            f"&config={base_url}/config.xml&playfb=0"
        )
        return web.Response(status=302, headers={"Location": target})

    async def portal_play(self, request: web.Request) -> web.Response:
        """Página que embute o Ruffle Web Player com as flashvars e socketProxy configurados."""
        username = request.query.get("user", "").strip() or f"Lord_{secrets.token_hex(2)}"
        ticket_token = secrets.token_hex(16)
        s = self._d.settings

        # Garante a conta e emite o ticket de jogo
        if self._d.uow is not None:
            now = self._d.clock.now() if self._d.clock else datetime.now(UTC)
            async with self._d.uow() as uow:
                account = await uow.accounts.by_username(username)
                if account is None or account.id is None:
                    account = await uow.accounts.add(
                        Account(username=username, password_hash="auto_guest", created_at=now)
                    )
                    await uow.commit()

                ticket = PlayTicket(
                    token=ticket_token,
                    account_id=account.id,
                    server_id=s.server_id,
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
                await uow.tickets.add(ticket)
                await uow.commit()

        base_url = self._base_url(request)
        config_url = f"{base_url}/config.xml"

        html_content = render_play_html(
            username=username,
            ticket=ticket_token,
            site=s.site,
            config_url=config_url,
            public_host=s.public_host,
            socket_port=s.socket_port,
            base_url=base_url,
        )
        return web.Response(
            text=html_content,
            content_type="text/html",
            charset="utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    async def client_config(self, request: web.Request) -> web.Response:
        """Gera o config.xml lido pelo Loading.swf."""
        s = self._d.settings
        base_url = self._base_url(request)
        # O cliente Flash possui a função legada configConvertToHTTPS() que faz
        # string.replace("http", "https") cegamente. Se a URL no XML já contiver "https",
        # ela se torna "httpss://", quebrando as requisições. Por isso, forçamos "http://"
        # no config.xml; o cliente converterá para "https://" quando executado sobre HTTPS.
        config_base_url = re.sub(r"^https://", "http://", base_url)
        modulus = self._d.keys.modulus_b64 if self._d.keys else ""
        exponent = self._d.keys.exponent_b64 if self._d.keys else "AQAB"
        audio_available = any((root / "audio.swf").is_file() for root in (Path("bundled_cdn"), Path("data/cdn")))
        music_available = any((root / "sounds").is_dir() for root in (Path("bundled_cdn"), Path("data/cdn")))
        xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<root>
\t<config>
\t\t<LANGUAGE value="zh_cn" />
\t\t<REQUEST_PATH value="{config_base_url}/" />
\t\t<CastleServicePath value="{config_base_url}/messagebroker/amf" />
\t\t<OuterCityServicePath value="{config_base_url}/messagebroker/amf" />
\t\t<FOWARDSITE siteName="{quoteattr(s.server_name).strip('\"')}" value="{config_base_url}/" />
\t\t<SocktPath value="{s.public_host}" SocketPort="{s.socket_port}" />
\t\t<TEMPLATE_PATH value="{config_base_url}/cdn/xml/" />
\t\t<ResourcePath value="{config_base_url}/cdn/" />
\t\t<FACE_NUM value="20" />
\t\t<VERSION value="1.3.0" />
\t\t<SITES>
\t\t\t<NODE site="{s.site}">
\t\t\t\t<CLIENT_LOGIN_PATH value="{config_base_url}/" />
\t\t\t\t<CLIENT_LOGIN_NAME value="{quoteattr(s.server_name).strip('\"')}" />
\t\t\t\t<SITE value="{config_base_url}/" />
\t\t\t\t<RSAKey site="{s.site}" PublicKeyModulus="{modulus}" publicExponent="{exponent}" />
\t\t\t</NODE>
\t\t</SITES>
\t\t<sounds source="{config_base_url}/cdn/audio.swf">
\t\t\t<sound id="001" cls="Sound001" />
\t\t\t<sound id="002" cls="Sound002" />
\t\t\t<sound id="003" cls="Sound003" />
\t\t\t<sound id="004" cls="Sound004" />
\t\t\t<sound id="005" cls="Sound005" />
\t\t\t<sound id="006" cls="Sound006" />
\t\t\t<sound id="007" cls="Sound007" />
\t\t\t<sound id="008" cls="Sound008" />
\t\t\t<sound id="009" cls="Sound009" />
\t\t\t<sound id="010" cls="Sound010" />
\t\t\t<sound id="011" cls="Sound011" />
\t\t\t<sound id="012" cls="Sound012" />
\t\t\t<sound id="013" cls="Sound013" />
\t\t\t<sound id="014" cls="Sound014" />
\t\t\t<sound id="015" cls="Sound015" />
\t\t\t<sound id="016" cls="Sound016" />
\t\t\t<sound id="018" cls="Sound018" />
\t\t\t<sound id="019" cls="Sound019" />
\t\t\t<sound id="020" cls="Sound020" />
\t\t\t<sound id="021" cls="Sound021" />
\t\t\t<sound id="022" cls="Sound022" />
\t\t\t<sound id="023" cls="Sound023" />
\t\t\t<sound id="024" cls="Sound024" />
\t\t\t<sound id="025" cls="Sound025" />
\t\t\t<sound id="026" cls="Sound026" />
\t\t\t<sound id="027" cls="Sound027" />
\t\t\t<sound id="028" cls="Sound028" />
\t\t\t<sound id="029" cls="Sound029" />
\t\t\t<sound id="030" cls="Sound030" />
\t\t\t<sound id="031" cls="Sound031" />
\t\t\t<sound id="032" cls="Sound032" />
\t\t\t<sound id="033" cls="Sound033" />
\t\t\t<sound id="034" cls="Sound034" />
\t\t\t<sound id="035" cls="Sound035" />
\t\t\t<sound id="036" cls="Sound036" />
\t\t\t<sound id="037" cls="Sound037" />
\t\t\t<sound id="039" cls="Sound039" />
\t\t\t<sound id="040" cls="Sound040" />
\t\t\t<sound id="041" cls="Sound041" />
\t\t\t<sound id="047" cls="Sound047" />
\t\t\t<sound id="048" cls="Sound048" />
\t\t\t<sound id="049" cls="Sound049" />
\t\t\t<sound id="050" cls="Sound050" />
\t\t</sounds>
\t\t<musics root="{config_base_url}/cdn/sounds/">
\t\t\t<music key="battle" filename="WORLDBOSS,BOSS">
\t\t\t\t<battle_map mapid="1" filename="cybattle01,cybattle02,cybattle03"/>
\t\t\t\t<battle_map mapid="2" filename="battle02,battle02"/>
\t\t\t\t<battle_map mapid="3" filename="battle03,battle03"/>
\t\t\t\t<battle_map mapid="4" filename="battle04,battle04"/>
\t\t\t\t<battle_map mapid="5" filename="battle05,battle05"/>
\t\t\t\t<battle_map mapid="6" filename="battle06,battle06"/>
\t\t\t</music>
\t\t\t<music key="castle" filename="innercity" />
\t\t\t<music key="outercity" filename="outercity" />
\t\t\t<music key="campaign_succeed" filename="campaign03" />
\t\t\t<music key="farm" filename="farm" />
\t\t\t<music key="vehicle" filename="bgm3001" />
\t\t\t<music key="space" filename="bgm_space" />
\t\t\t<music key="petland" filename="bgm_pet" />
\t\t</musics>
\t</config>
\t<corssdomainfiles>
\t\t<corssdomainfile value="{config_base_url}/crossdomain.xml" />
\t</corssdomainfiles>
</root>"""
        if not audio_available:
            xml_body = re.sub(r"\n\t\t<sounds source=.*?</sounds>", "", xml_body, flags=re.DOTALL)
        if not music_available:
            xml_body = re.sub(r"\n\t\t<musics root=.*?</musics>", "", xml_body, flags=re.DOTALL)
        return web.Response(
            text=xml_body,
            content_type="text/xml",
            charset="utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Access-Control-Allow-Origin": "*",
            },
        )

    async def ws_bridge(self, request: web.Request) -> web.WebSocketResponse:
        """Ponte WebSocket acessível via WSS seguro pelo Traefik/EasyPanel."""
        if self._d.acceptor is None:
            raise web.HTTPServiceUnavailable(text="Ponte WebSocket indisponível no servidor")
        return await self._d.acceptor.on_websocket(request)

    async def api_auth(self, request: web.Request) -> web.Response:
        """API para criação de conta e geração de token de jogo."""
        params = await _params(request)
        username = params.get("username", "").strip() or f"User_{secrets.token_hex(2)}"
        token = secrets.token_hex(16)
        s = self._d.settings
        if self._d.uow is not None:
            now = self._d.clock.now() if self._d.clock else datetime.now(UTC)
            async with self._d.uow() as uow:
                account = await uow.accounts.by_username(username)
                if account is None or account.id is None:
                    account = await uow.accounts.add(
                        Account(username=username, password_hash="auth_api", created_at=now)
                    )
                    await uow.commit()
                ticket = PlayTicket(
                    token=token,
                    account_id=account.id,
                    server_id=s.server_id,
                    created_at=now,
                    expires_at=now + timedelta(days=1),
                )
                await uow.tickets.add(ticket)
                await uow.commit()

        base_url = self._base_url(request)
        return web.json_response(
            {
                "ok": True,
                "username": username,
                "ticket": token,
                "play_url": f"{base_url}/play?user={username}",
                "server_id": s.server_id,
            }
        )

    @staticmethod
    def _is_md5_hex(value: str) -> bool:
        return len(value) == 32 and all(ch in "0123456789abcdef" for ch in value.lower())

    @staticmethod
    async def _player_json(request: web.Request) -> dict[str, str]:
        try:
            data = await request.json()
        except Exception:
            params = await _params(request)
            data = dict(params)
        if not isinstance(data, dict):
            return {}
        return {
            "username": str(data.get("username", "")).strip(),
            "password": str(data.get("password", "")),
        }

    async def api_player_register(self, request: web.Request) -> web.Response:
        """Cria uma conta de jogador com senha para a tela de login do cliente H5."""
        body = await self._player_json(request)
        username = body.get("username", "")
        password = body.get("password", "")
        if not (3 <= len(username) <= 32) or not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
            return web.json_response(
                {"ok": False, "error": "Usuário deve ter 3 a 32 caracteres (letras, números, _ . -)."},
                status=400,
            )
        if len(password) < 4:
            return web.json_response(
                {"ok": False, "error": "A senha precisa ter pelo menos 4 caracteres."},
                status=400,
            )
        if self._d.uow is None:
            return web.json_response({"ok": False, "error": "Banco indisponível."}, status=503)

        pwd_hash = hashlib.md5(password.encode("utf-8")).hexdigest()
        now = self._d.clock.now() if self._d.clock else datetime.now(UTC)
        async with self._d.uow() as uow:
            existing = await uow.accounts.by_username(username)
            if existing is not None:
                return web.json_response(
                    {"ok": False, "error": "Este usuário já existe. Faça login ou escolha outro nome."},
                    status=409,
                )
            await uow.accounts.add(Account(username=username, password_hash=pwd_hash, created_at=now))
            await uow.commit()
        log.info("conta criada pelo cliente H5", username=username, peer=request.remote)
        return web.json_response({"ok": True, "username": username})

    async def api_player_login(self, request: web.Request) -> web.Response:
        """Valida usuário e senha antes de liberar a entrada no jogo H5."""
        body = await self._player_json(request)
        username = body.get("username", "")
        password = body.get("password", "")
        if not username or not password:
            return web.json_response({"ok": False, "error": "Informe usuário e senha."}, status=400)
        if self._d.uow is None:
            return web.json_response({"ok": False, "error": "Banco indisponível."}, status=503)

        pwd_hash = hashlib.md5(password.encode("utf-8")).hexdigest()
        async with self._d.uow() as uow:
            account = await uow.accounts.by_username(username)
            if account is None or account.id is None:
                return web.json_response(
                    {"ok": False, "error": "Conta não encontrada. Clique em 'Criar Conta' para se cadastrar."},
                    status=404,
                )
            if account.banned:
                return web.json_response({"ok": False, "error": "Esta conta está banida."}, status=403)
            stored = (account.password_hash or "").strip().lower()
            if self._is_md5_hex(stored):
                if not hmac.compare_digest(stored, pwd_hash):
                    return web.json_response({"ok": False, "error": "Usuário ou senha incorretos."}, status=401)
            else:
                # Conta legada criada sem senha real: define a senha no primeiro acesso válido
                if len(password) < 4:
                    return web.json_response(
                        {"ok": False, "error": "Defina uma senha com pelo menos 4 caracteres."},
                        status=400,
                    )
                if self._d.ctx and self._d.ctx.database is not None:
                    async with self._d.ctx.database.engine.begin() as conn:
                        await conn.execute(
                            update(accounts).where(accounts.c.id == account.id).values(password_hash=pwd_hash)
                        )
        log.info("login H5 validado", username=username, peer=request.remote)
        return web.json_response({"ok": True, "username": username})

    async def code_md5(self, request: web.Request) -> web.Response:
        """Entrega o code_md5.dat exigido pelo Md5Versions.as."""
        p = find_cdn_file("code_md5.dat")
        if p and p.is_file():
            return web.FileResponse(p, headers={"Content-Type": "application/octet-stream", "Access-Control-Allow-Origin": "*"})
        return web.Response(status=404, text="code_md5.dat não encontrado", headers={"Access-Control-Allow-Origin": "*"})

    async def res_md5(self, request: web.Request) -> web.Response:
        """Entrega o res_md5.dat exigido pelo Md5Versions.as."""
        p = find_cdn_file("res_md5.dat")
        if p and p.is_file():
            return web.FileResponse(p, headers={"Content-Type": "application/octet-stream", "Access-Control-Allow-Origin": "*"})
        return web.Response(status=404, text="res_md5.dat não encontrado", headers={"Access-Control-Allow-Origin": "*"})

    async def size_xml(self, request: web.Request) -> web.Response:
        """Entrega o size.xml na raiz exigido pelo cliente Flash."""
        p = find_cdn_file("size.xml")
        if p and p.is_file():
            return web.FileResponse(p, headers={"Content-Type": "application/xml", "Access-Control-Allow-Origin": "*"})
        return web.Response(status=404, text="size.xml não encontrado", headers={"Access-Control-Allow-Origin": "*"})

    async def cdn_proxy(self, request: web.Request) -> web.StreamResponse:
        """Proxy reverso de CDN com cache local e desobfuscação inteligente para assets Flash."""
        raw_tail = request.match_info.get("tail", "")
        tail = re.sub(r"/+", "/", raw_tail).lstrip("/")

        # Normaliza ui/en_us/ para ui/zh_cn/ (estrutura de diretório oficial do cliente)
        if tail.startswith("ui/en_us/"):
            tail = "ui/zh_cn/" + tail[len("ui/en_us/") :]

        # Arquivos especiais na raiz ou no cdn
        if tail in ("code_md5.dat", "code_md5.raw"):
            return await self.code_md5(request)
        if tail in ("res_md5.dat", "res_md5.raw"):
            return await self.res_md5(request)

        # XML de versão local
        if tail == "xml/version.xml":
            p = find_cdn_file("xml/version.xml")
            if p and p.is_file():
                return web.FileResponse(p, headers={"Content-Type": "application/xml", "Access-Control-Allow-Origin": "*"})
            xml_data = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                "<root>\n"
                "  <time>2026-11-22</time>\n"
                "  <curContent>\n"
                "    <item><title>Wartune Reborn</title><content>Servidor operacional!</content></item>\n"
                "  </curContent>\n"
                "  <nextContent>\n"
                "    <item><title>Reino do Ceu</title><content>Bem-vindo ao Wartune Reborn!</content></item>\n"
                "  </nextContent>\n"
                "</root>"
            )
            return web.Response(text=xml_data, content_type="application/xml", charset="utf-8", headers={"Access-Control-Allow-Origin": "*"})

        # Templates compilados locais
        if tail == "xml/tempinfos.xml":
            p = find_cdn_file("xml/tempinfos.xml")
            if p and p.is_file():
                return web.FileResponse(p, headers={"Content-Type": "application/octet-stream", "Access-Control-Allow-Origin": "*"})
            tpl_file = self._d.settings.templates_file
            if tpl_file.is_file():
                return web.FileResponse(tpl_file, headers={"Content-Type": "application/octet-stream", "Access-Control-Allow-Origin": "*"})

        # Busca no cache em disco ou nos assets bundled
        found = find_cdn_file(tail)
        if found and found.is_file():
            data = found.read_bytes()
            clean_data = deobfuscate_module(data)
            if clean_data != data and "data/cdn" in str(found):
                try:
                    found.write_bytes(clean_data)
                except OSError:
                    pass
            ct = "application/x-shockwave-flash" if clean_data.startswith((b"CWS", b"FWS")) else ("image/png" if tail.endswith(".png") and not clean_data.startswith(b"CWS") else "application/octet-stream")
            return web.Response(body=clean_data, headers={"Content-Type": ct, "Access-Control-Allow-Origin": "*"})

        # Checa versão sem o hash MD5 (ex: mainloadingii_c1b9b871.swf -> mainloadingii.swf)
        stripped_tail = re.sub(r'_[0-9a-fA-F]{8}(\.[a-zA-Z0-9]+)$', r'\1', tail)
        if stripped_tail != tail:
            found_stripped = find_cdn_file(stripped_tail)
            if found_stripped and found_stripped.is_file():
                data = found_stripped.read_bytes()
                clean_data = deobfuscate_module(data)
                if clean_data != data and "data/cdn" in str(found_stripped):
                    try:
                        found_stripped.write_bytes(clean_data)
                    except OSError:
                        pass
                ct = "application/x-shockwave-flash" if clean_data.startswith((b"CWS", b"FWS")) else ("image/png" if stripped_tail.endswith(".png") and not clean_data.startswith(b"CWS") else "application/octet-stream")
                return web.Response(body=clean_data, headers={"Content-Type": ct, "Access-Control-Allow-Origin": "*"})

        # Busca no CDN oficial upstream: tenta primeiro o CDN Brasil, depois o chinês 7Road
        cache_dir = Path("data/cdn")
        local_file = (cache_dir / tail).resolve()
        try:
            local_file.relative_to(cache_dir.resolve())
        except ValueError:
            return web.Response(status=403, text="Acesso negado")

        candidate_urls = [
            f"https://res1264oas.creaction-network.com/{tail}",
        ]
        if stripped_tail != tail:
            candidate_urls.append(f"https://res1264oas.creaction-network.com/{stripped_tail}")
        candidate_urls.extend([
            f"http://res134-bmclas-sq.7road.net/{tail}",
            f"http://res134-bmclas-sq.7road.net/{stripped_tail}",
        ])

        timeout = aiohttp.ClientTimeout(total=15)
        for upstream_url in candidate_urls:
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(upstream_url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            clean_data = deobfuscate_module(data)
                            try:
                                local_file.parent.mkdir(parents=True, exist_ok=True)
                                local_file.write_bytes(clean_data)
                            except OSError:
                                pass
                            ct = "application/x-shockwave-flash" if tail.endswith(".swf") else resp.headers.get("Content-Type", "application/octet-stream")
                            return web.Response(body=clean_data, content_type=ct)
            except Exception as exc:
                log.warning("falha ao consultar upstream CDN", url=upstream_url, erro=str(exc))

        log.warning("asset ausente na CDN", caminho=tail, tentativas=candidate_urls)
        return web.Response(
            status=404,
            text=f"Asset não encontrado: {tail}",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    async def debug_logs(self, _: web.Request) -> web.Response:
        log_dir = Path(getattr(self._d.settings, "log_dir", "logs"))
        log_file = log_dir / "server.log"
        if not log_file.is_file():
            log_file = Path("logs/server.log")
        if log_file.is_file():
            lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            return web.Response(text="\n".join(lines[-150:]), content_type="text/plain", headers={"Access-Control-Allow-Origin": "*"})
        return web.Response(text=f"Log file not found at {log_file}", status=404, headers={"Access-Control-Allow-Origin": "*"})

    async def favicon(self, _: web.Request) -> web.Response:
        return web.Response(status=204, headers={"Access-Control-Allow-Origin": "*"})

    # -- jogo --------------------------------------------------------------------------
    async def client_site_info(self, request: web.Request) -> web.Response:
        """Endpoint clientsiteinfoservlet para o cliente H5 do Wartune."""
        base_url = self._base_url(request)
        origin = request.headers.get("Origin") or ""
        web_base = origin.rstrip("/") if origin.startswith("http") else base_url.rstrip("/")
        proto = request.headers.get("X-Forwarded-Proto") or request.scheme
        ws_scheme = "wss" if proto == "https" else "ws"
        host = request.headers.get("X-Forwarded-Host") or request.host
        ws_url = f"{ws_scheme}://{host}/ws"
        data = {
            "ret": 0,
            "msg": "ok",
            "curTime": int(datetime.now(UTC).timestamp() * 1000),
            "isWhiteUser": False,
            "platformId": 1,
            "platformName": "America",
            "groups": [
                {
                    "groupId": 1,
                    "groupName": "S1-S100",
                    "order": 1,
                    "sites": [
                        {
                            "siteId": self._d.settings.server_id,
                            "showName": self._d.settings.server_name,
                            "type": 1,
                            "siteName": self._d.settings.site,
                            "loginUrl": ws_url,
                            "webUrl": f"{web_base}/",
                            "mainSite": "",
                            "isOpen": True,
                            "isRepair": False,
                            "order": 1,
                            "openTime": 1600000000,
                            "playinfo": None,
                        }
                    ],
                }
            ],
        }
        compressed = zlib.compress(json.dumps(data).encode("utf-8"))
        return web.Response(
            body=compressed,
            content_type="application/octet-stream",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    async def version_json(self, request: web.Request) -> web.Response:
        return web.json_response({}, headers={"Access-Control-Allow-Origin": "*"})

    async def client_log(self, request: web.Request) -> web.Response:
        """Recebe logs de telemetria e diagnóstico do cliente web H5."""
        try:
            body = await request.json()
            log.info("clientlog", kind=body.get("kind"), msg=body.get("msg"))
        except Exception:
            pass
        return web.json_response({"ok": True}, headers={"Access-Control-Allow-Origin": "*"})

    async def crossdomain(self, _: web.Request) -> web.Response:
        # o SWF vem do Apache (outra porta = outra origem para o Flash)
        return web.Response(text=CROSSDOMAIN, content_type="text/xml")

    async def select_list(self, request: web.Request) -> web.Response:
        params = await _params(request)
        entries = await self._d.login.select_list(params.get("username", ""))
        items = "".join(
            f'<Item ID="{e.character_id}" Active="{str(e.active).lower()}" NickName={quoteattr(e.nickname or "")}/>'
            for e in entries
        )
        body = f'<?xml version="1.0" encoding="UTF-8"?><Result value="true" message="">{items}</Result>'
        return web.Response(text=body, content_type="text/xml", charset="utf-8")

    async def http_login(self, request: web.Request) -> web.Response:
        params = await _params(request)
        try:
            result = await self._d.login.http_login(params.get("p", ""), request.remote or "")
        except DomainError as exc:
            log.info("login HTTP recusado", erro=str(exc), peer=request.remote)
            return xml_result(False, str(exc), userId=0)
        s = self._d.settings
        log.info("login HTTP ok", player=result.user_id, peer=request.remote)
        return xml_result(True, "Login Succeed", userId=result.user_id, Address=s.public_host, Port=s.socket_port)

    async def register(self, request: web.Request) -> web.Response:
        params = await _params(request)
        try:
            character_id = _int(params, "userid")
            self._d.login.session_for_character(params.get("key", ""), character_id)
            req = RegistrationRequest(
                character_id,
                params.get("nickname", ""),
                sex=_int(params, "sex"),
                camp=_int(params, "camp") if params.get("camp") else 1,
                icon=_int(params, "icon"),
            )
            character = await self._d.characters.register(req)
        except DomainError as exc:
            return xml_result(False, str(exc), type=1)
        log.info("personagem criado", player=character.id, nick=character.nickname, job=character.job)
        return xml_result(True, "ok", type=0)

    async def novice(self, request: web.Request) -> web.Response:
        params = await _params(request)
        try:
            character_id = _int(params, "userid")
            self._d.login.session_for_character(params.get("key", ""), character_id)
            if params.get("op") == "1":
                value = _int(params, "noviceprocess")
                if self._d.settings.skip_tutorial:
                    value = max(value, TUTORIAL_DONE)
                await self._d.characters.set_novice_process(character_id, value)
                # a sessão online grava o personagem inteiro (5015, saída...): sem isto, desfaria o valor
                online = self._d.online.get(character_id)
                if online is not None and online.snapshot is not None:
                    online.snapshot.character.novice_process = max(0, value)
            snap = await self._d.characters.snapshot(character_id)
        except DomainError as exc:
            log.info("updateplayernovice recusado", erro=str(exc))
            return web.Response(text="0")
        return web.Response(text=str(snap.character.novice_process))

    def _gm_allowed(self, request: web.Request) -> bool:
        secret = self._d.settings.gm_secret or ""
        if hmac.compare_digest(request.headers.get("X-GM-Secret", "").encode(), secret.encode()):
            return True
        log.warning("rota GM com segredo errado", caminho=request.path, peer=request.remote)
        return False

    async def gm_kick(self, request: web.Request) -> web.Response:
        """Portal (painel GM): derruba o personagem antes de editar o banco; 200 = já pode gravar."""
        if not self._gm_allowed(request):
            return web.json_response({"ok": False, "error": "segredo inválido"}, status=403)
        try:
            character_id = _int(await _params(request), "character_id")
            await self._d.online.kick(character_id)
        except ValidationError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        except TimeoutError:
            return web.json_response({"ok": False, "error": "a sessão não terminou a tempo"}, status=503)
        return web.json_response({"ok": True})

    async def gm_ban(self, request: web.Request) -> web.Response:
        """Portal: ``account_id`` e ``banned`` 0/1. Banir invalida as sessões de login e derruba o
        personagem; o próximo /login e 20001 da conta são recusados."""
        if not self._gm_allowed(request):
            return web.json_response({"ok": False, "error": "segredo inválido"}, status=403)
        try:
            params = await _params(request)
            account_id, banned = _int(params, "account_id"), _int(params, "banned")
            if banned not in (0, 1):
                raise ValidationError("parâmetro banned inválido")
            for character_id in await self._d.login.set_banned(account_id, bool(banned)):
                if banned:
                    await self._d.online.kick(character_id)
        except ValidationError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=400)
        except NotFoundError as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=404)
        except TimeoutError:
            return web.json_response({"ok": False, "error": "a sessão não terminou a tempo"}, status=503)
        log.info("conta banida" if banned else "conta desbanida", conta=account_id)
        return web.json_response({"ok": True})

    async def plain_true(self, _: web.Request) -> web.Response:
        return web.Response(text="true")

    async def mail_list(self, request: web.Request) -> web.Response:
        """Correio do jogador. ``mailId`` "0" = todos, senão ids separados por vírgula (148 novo,
        ``reqType=1`` ao abrir um correio: marca como lido)."""
        params = await _params(request)
        try:
            character_id = _int(params, "userId")
            self._d.login.session_for_character(params.get("key", ""), character_id)
            ids = [int(i) for i in params.get("mailId", "0").split(",") if i.strip()]
        except (DomainError, ValueError) as exc:
            log.info("maillist recusado", erro=str(exc))
            return _zlib('<?xml version="1.0" encoding="UTF-8"?><Result value="false" message=""/>')
        wanted = None if ids in ([], [0]) else ids

        async def load(uow: UnitOfWork) -> tuple[list[Mail], list[MailAnnex], str]:
            mails = await uow.mails.by_receiver(character_id, wanted)
            annexes = await uow.mails.annexes([m.id or 0 for m in mails])
            c = await uow.characters.get(character_id)
            return mails, annexes, (c.nickname or "") if c else ""

        mails, annexes, nick = await self._d.characters.read(load)
        if params.get("reqType") == "1":
            unread = [m for m in mails if m.read_at is None]
            for m in unread:
                m.read_at = datetime.now(UTC)
            await self._d.characters.save(*unread)
        return _zlib(mailbox.list_xml(mails, annexes, nick))

    async def nickname_check(self, request: web.Request) -> web.Response:
        """``@value`` true = nome livre; senão ``@message`` vai para a tela de troca de nome."""
        params = await _params(request)
        try:
            nick = character_name(params.get("nickname", ""))
        except ValidationError as exc:
            return xml_result(False, str(exc))
        taken = await self._d.characters.read(
            lambda uow: uow.characters.nickname_taken(self._d.settings.server_id, nick)
        )
        return xml_result(not taken, NAME_TAKEN if taken else "")

    async def images(self, request: web.Request) -> web.Response:
        """O oficial serve ``images/`` no mesmo host do REQUEST_PATH; aqui o arquivo é do espelho do s134
        (``site_url``). O que faltar lá vira 404 do Apache, que o ``download.php`` (``jobs_404``) baixa."""
        tail = re.sub("/+", "/", request.match_info["tail"]).lstrip("/")  # o 4238 manda shop//726.png
        # retornado (não ``raise``) para o ``allow_any_origin`` pôr o CORS que o Ruffle exige no 302
        return web.Response(
            status=302, headers={"Location": self._d.settings.site_url.rstrip("/") + "/images/" + tail}
        )

    async def empty_list(self, _: web.Request) -> web.Response:
        # o cliente faz ByteArray.uncompress() no corpo: o XML vai em zlib
        # ponytail: respostas do suporte sempre vazias até existir o atendimento
        return _zlib('<?xml version="1.0" encoding="UTF-8"?><Result value="true" message="Success"/>')


def _zlib(xml: str) -> web.Response:
    return web.Response(body=zlib.compress(xml.encode()), content_type="application/octet-stream")


@web.middleware
async def allow_any_origin(request: web.Request, handler: Handler) -> web.StreamResponse:
    """CORS irrestrito para todas as requisições web do H5 e Ruffle."""
    if request.method == "OPTIONS":
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PUT, PATCH, DELETE",
                "Access-Control-Allow-Headers": "*",
            },
        )
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        exc.headers["Access-Control-Allow-Origin"] = "*"
        exc.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, PATCH, DELETE"
        exc.headers["Access-Control-Allow-Headers"] = "*"
        raise
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, PATCH, DELETE"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


def build_http_app(deps: HttpDeps) -> web.Application:
    app = web.Application(middlewares=[allow_any_origin], client_max_size=1 << 20)
    GameHttpApi(deps).routes(app)
    return app
