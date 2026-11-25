"""API HTTP completa de administração (painel GM/Admin separado).

Todas as rotas ``/api/admin/*`` exigem autenticação via token HMAC-SHA256 emitido em
``POST /api/admin/auth/login`` (com ``WARTUNE_ADMIN_PASSWORD`` configurada via ambiente)
ou cabeçalho ``X-GM-Secret`` quando ``WARTUNE_GM_SECRET`` estiver definido.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import structlog
from aiohttp import web
from sqlalchemy import desc, func, select, update

from ..domain import gameday
from ..domain.errors import DomainError, NotFoundError, ValidationError
from ..domain.models import (
    CashLedger,
    ItemLog,
    Mail,
    MailType,
    PlayerSnapshot,
)
from ..game import bag, rewards, rules
from ..game import events as ev
from ..game import mail as mailbox
from ..game.castle import castle_yield
from ..game.events import EventCatalog
from ..game.handlers import events as event_handlers
from ..game.handlers import player as player_handlers
from ..game.handlers import vip as vip_handlers
from ..game.handlers.login_h5 import h5_novice_process
from ..persistence import world_store
from ..persistence.schema import (
    accounts,
    cash_ledger,
    characters,
    consortia_members,
    consortias,
    exp_rate_events,
    game_servers,
    game_settings,
    item_log,
    login_history,
    mail_annexes,
    mails,
    mall_listings,
    purchases,
    scheduled_announcements,
    world_boss_fights,
    world_boss_wounds,
    world_bosses,
)
from ..protocol.messages import wartune_pb2 as pb

if TYPE_CHECKING:
    from ..game.session import GameContext, GameSession
    from .app import HttpDeps

log = structlog.get_logger(__name__)

TOKEN_TTL_SECONDS = 86400  # 24 horas
S_CHAT, S_ALERT, S_ITEMS, S_PLAYER = 83, 111, 115, 3
SPECIAL_ITEMS = (
    {"templateId": -100, "name": "Ouro (Gold)", "masterType": -1, "sonType": -100, "quality": 4},
    {"templateId": -200, "name": "Ametista (MineScore)", "masterType": -1, "sonType": -200, "quality": 4},
    {"templateId": -300, "name": "Daru (Strategy)", "masterType": -1, "sonType": -300, "quality": 3},
    {"templateId": -400, "name": "Diamantes (Balens)", "masterType": -1, "sonType": -400, "quality": 5},
    {
        "templateId": -500,
        "name": "Diamantes Vinculados (Bound Balens)",
        "masterType": -1,
        "sonType": -500,
        "quality": 4,
    },
    {"templateId": -600, "name": "Kyanite (Crystals)", "masterType": -1, "sonType": -600, "quality": 3},
    {"templateId": -700, "name": "Experiência (EXP)", "masterType": -1, "sonType": -700, "quality": 2},
)
AUDIT_TABLES: dict[str, Any] = {
    "cash": cash_ledger,
    "items": item_log,
    "logins": login_history,
    "purchases": purchases,
}


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _err(message: str, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


def _ok(payload: dict[str, Any] | None = None, **extra: Any) -> web.Response:
    data: dict[str, Any] = {"ok": True}
    if payload:
        data.update(payload)
    data.update(extra)
    return web.json_response(data)


async def _json_body(request: web.Request) -> dict[str, Any]:
    try:
        raw = await request.json()
    except Exception:
        raise ValidationError("corpo JSON inválido") from None
    if not isinstance(raw, dict):
        raise ValidationError("JSON precisa ser um objeto")
    return raw


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign_token(username: str, secret: str, ttl: int = TOKEN_TTL_SECONDS) -> tuple[str, int]:
    exp = int(time.time()) + ttl
    payload = _b64u_encode(json.dumps({"sub": username, "exp": exp}, separators=(",", ":")).encode())
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}", exp


def _verify_token(token: str, secret: str) -> dict[str, Any] | None:
    if "." not in token:
        return None
    payload_b64, sig = token.split(".", 1)
    expected = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        data = json.loads(_b64u_decode(payload_b64).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or int(data.get("exp", 0)) < int(time.time()):
        return None
    return data


def _scene_label(s: GameSession) -> str:
    if s.battle is not None:
        return f"batalha ({s.battle.id})"
    if s.campaign is not None:
        return f"campanha #{s.campaign.map_id}"
    if s.space_pos is not None:
        return f"cidade do céu ({s.space_pos[0]},{s.space_pos[1]})"
    if s.outer_army is not None:
        return f"cidade externa #{s.outer_army[0]}"
    return "castelo / home"


def _row_dict(row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in dict(row._mapping).items():
        out[k] = v.isoformat() if isinstance(v, datetime) else v
    return out


class AdminHttpApi:
    """Controladores REST para o painel administrativo."""

    def __init__(self, deps: HttpDeps) -> None:
        self._d = deps
        self._started_at = datetime.now(UTC)

    def routes(self, app: web.Application) -> None:
        r = app.router
        # Autenticação
        r.add_post("/api/admin/auth/login", self._public(self.auth_login))
        r.add_get("/api/admin/auth/me", self._guarded(self.auth_me))
        # Visão geral e logs
        r.add_get("/api/admin/overview", self._guarded(self.overview))
        r.add_get("/api/admin/logs", self._guarded(self.logs))
        r.add_get("/api/admin/audit", self._guarded(self.audit))
        # Sessões online
        r.add_get("/api/admin/online", self._guarded(self.online_list))
        r.add_post("/api/admin/online/{id}/kick", self._guarded(self.online_kick))
        r.add_post("/api/admin/online/{id}/alert", self._guarded(self.online_alert))
        # Contas
        r.add_get("/api/admin/accounts", self._guarded(self.accounts_list))
        r.add_post("/api/admin/accounts/{id}/ban", self._guarded(self.account_ban))
        r.add_post("/api/admin/accounts/{id}/password", self._guarded(self.account_password))
        # Personagens
        r.add_get("/api/admin/characters", self._guarded(self.characters_list))
        r.add_get("/api/admin/characters/{id}", self._guarded(self.character_detail))
        r.add_patch("/api/admin/characters/{id}", self._guarded(self.character_patch))
        r.add_post("/api/admin/characters/{id}/xp", self._guarded(self.character_xp))
        r.add_post("/api/admin/characters/{id}/vip", self._guarded(self.character_vip))
        r.add_post("/api/admin/characters/{id}/tutorial", self._guarded(self.character_tutorial))
        r.add_post("/api/admin/characters/{id}/vice-password", self._guarded(self.character_clear_vice))
        r.add_post("/api/admin/characters/{id}/reset", self._guarded(self.character_reset))
        # Itens do personagem e catálogo
        r.add_post("/api/admin/characters/{id}/items", self._guarded(self.character_give_item))
        r.add_patch("/api/admin/characters/{id}/items/{item_id}", self._guarded(self.character_edit_item))
        r.add_delete("/api/admin/characters/{id}/items/{item_id}", self._guarded(self.character_delete_item))
        r.add_get("/api/admin/templates", self._guarded(self.templates_search))
        # Correio e broadcast
        r.add_get("/api/admin/mail", self._guarded(self.mail_recent))
        r.add_post("/api/admin/mail/send", self._guarded(self.mail_send))
        r.add_post("/api/admin/broadcast", self._guarded(self.broadcast))
        # Anúncios agendados
        r.add_get("/api/admin/announcements", self._guarded(self.announcements_list))
        r.add_post("/api/admin/announcements", self._guarded(self.announcements_create))
        r.add_put("/api/admin/announcements/{id}", self._guarded(self.announcements_update))
        r.add_delete("/api/admin/announcements/{id}", self._guarded(self.announcements_delete))
        # EXP rates e Eventos (data/events.json)
        r.add_get("/api/admin/exp-rates", self._guarded(self.exp_rates_list))
        r.add_post("/api/admin/exp-rates", self._guarded(self.exp_rates_create))
        r.add_delete("/api/admin/exp-rates/{id}", self._guarded(self.exp_rates_delete))
        r.add_get("/api/admin/events", self._guarded(self.events_get))
        r.add_put("/api/admin/events", self._guarded(self.events_put))
        # Configurações do mundo / runtime
        r.add_get("/api/admin/settings", self._guarded(self.settings_get))
        r.add_put("/api/admin/settings/{key}", self._guarded(self.settings_put))
        r.add_patch("/api/admin/server/runtime", self._guarded(self.server_runtime_patch))
        r.add_post("/api/admin/server/wipe-players", self._guarded(self.server_wipe_players))
        # World Boss, Guildas e Leilão
        r.add_get("/api/admin/world-boss", self._guarded(self.world_boss_list))
        r.add_put("/api/admin/world-boss/{campaign_id}", self._guarded(self.world_boss_update))
        r.add_get("/api/admin/guilds", self._guarded(self.guilds_list))
        r.add_patch("/api/admin/guilds/{id}", self._guarded(self.guilds_patch))
        r.add_get("/api/admin/mall", self._guarded(self.mall_list))
        r.add_delete("/api/admin/mall/{id}", self._guarded(self.mall_cancel))

    # -- helpers de contexto e segurança -----------------------------------------------
    def _auth_secret(self) -> str | None:
        s = self._d.settings
        password = getattr(s, "admin_password", None) or getattr(s, "gm_secret", None)
        if not password:
            return None
        return str(getattr(s, "admin_token_secret", None) or password)

    def _admin_credentials(self) -> tuple[str, str] | None:
        s = self._d.settings
        password = getattr(s, "admin_password", None) or getattr(s, "gm_secret", None)
        if not password:
            return None
        username = str(getattr(s, "admin_username", None) or "admin")
        return username, str(password)

    def _authenticate(self, request: web.Request) -> str | None:
        secret = self._auth_secret()
        if not secret:
            return None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            claims = _verify_token(auth[7:].strip(), secret)
            if claims is not None:
                return str(claims.get("sub", "admin"))
        gm_secret = getattr(self._d.settings, "gm_secret", None)
        if gm_secret and hmac.compare_digest(request.headers.get("X-GM-Secret", ""), str(gm_secret)):
            return "gm_secret"
        return None

    def _public(
        self, handler: Callable[[web.Request], Awaitable[web.Response]]
    ) -> Callable[[web.Request], Awaitable[web.Response]]:
        async def wrapper(request: web.Request) -> web.Response:
            if self._auth_secret() is None:
                return _err("Painel admin não configurado no servidor", 503)
            try:
                return await handler(request)
            except DomainError as exc:
                return _err(str(exc), 400)
            except Exception as exc:
                log.exception("erro em endpoint público admin", path=request.path, erro=str(exc))
                return _err("erro interno ao processar autenticação", 500)

        return wrapper

    def _guarded(
        self, handler: Callable[[web.Request, str], Awaitable[web.Response]]
    ) -> Callable[[web.Request], Awaitable[web.Response]]:
        async def wrapper(request: web.Request) -> web.Response:
            if self._auth_secret() is None:
                return _err("Painel admin não configurado no servidor", 503)
            operator = self._authenticate(request)
            if operator is None:
                return _err("não autorizado ou sessão expirada", 401)
            try:
                return await handler(request, operator)
            except NotFoundError as exc:
                return _err(str(exc), 404)
            except ValidationError as exc:
                return _err(str(exc), 400)
            except DomainError as exc:
                return _err(str(exc), 400)
            except ValueError as exc:
                return _err(str(exc), 400)
            except Exception as exc:
                log.exception("erro na API admin", path=request.path, erro=str(exc))
                return _err(f"erro interno: {exc}", 500)

        return wrapper

    def _normalize_game_datetime(self, raw: str) -> str:
        val = raw.strip().replace("T", " ")
        if not val:
            raise ValidationError("data/hora obrigatória no formato YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS")
        if len(val) == 10:
            val = f"{val} 00:00:00"
        elif len(val) == 16:
            val = f"{val}:00"
        try:
            datetime.strptime(val, ev.TIME_FMT)
        except ValueError:
            raise ValidationError("data/hora inválida; use YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS") from None
        return val

    def _ctx(self) -> GameContext:
        ctx = self._d.ctx
        if ctx is None:
            raise ValidationError("GameContext indisponível")
        return ctx

    def _engine(self) -> Any:
        ctx = self._ctx()
        if ctx.database is None:
            raise ValidationError("Database engine indisponível")
        return ctx.database.engine

    def _now(self) -> datetime:
        if self._d.clock is not None:
            return self._d.clock.now()
        return datetime.now(UTC)

    async def _reload_world(self) -> None:
        ctx = self._ctx()
        engine = self._engine()
        ctx.world = await world_store.load(engine)

    async def _load_snap(self, char_id: int) -> tuple[PlayerSnapshot, GameSession | None]:
        session = self._d.online.get(char_id)
        if session is not None and session.snapshot is not None:
            return session.snapshot, session
        return await self._d.characters.snapshot(char_id), None

    def _push_player_sync(self, session: GameSession, *, army_sync: bool = False) -> None:
        player_handlers._player(session)
        castle_yield(session)
        if army_sync:
            player_handlers._army(session)

    # -- autenticação ------------------------------------------------------------------
    async def auth_login(self, request: web.Request) -> web.Response:
        creds = self._admin_credentials()
        secret = self._auth_secret()
        assert creds is not None and secret is not None
        body = await _json_body(request)
        user = str(body.get("username", "")).strip()
        pwd = str(body.get("password", ""))
        ok_user = hmac.compare_digest(user.encode(), creds[0].encode())
        ok_pwd = hmac.compare_digest(pwd.encode(), creds[1].encode())
        if not (ok_user and ok_pwd):
            log.warning("tentativa de login admin inválida", username=user, peer=request.remote)
            return _err("usuário ou senha incorretos", 401)
        token, exp = _sign_token(creds[0], secret)
        log.info("login admin efetuado", username=creds[0], peer=request.remote)
        return _ok({"token": token, "username": creds[0], "expiresAt": exp})

    async def auth_me(self, _: web.Request, operator: str) -> web.Response:
        s = self._d.settings
        return _ok(
            {
                "username": operator,
                "serverId": s.server_id,
                "serverName": s.server_name,
                "publicHost": s.public_host,
                "timezone": s.game_timezone,
            }
        )

    # -- overview, logs e auditoria ----------------------------------------------------
    async def overview(self, _: web.Request, _op: str) -> web.Response:
        ctx, engine, now = self._ctx(), self._engine(), self._now()
        async with engine.connect() as conn:
            total_accounts = int((await conn.execute(select(func.count()).select_from(accounts))).scalar() or 0)
            banned_accounts = int(
                (await conn.execute(select(func.count()).select_from(accounts).where(accounts.c.banned))).scalar() or 0
            )
            active_chars = int(
                (await conn.execute(select(func.count()).select_from(characters).where(characters.c.active))).scalar()
                or 0
            )
            inactive_chars = int(
                (
                    await conn.execute(select(func.count()).select_from(characters).where(~characters.c.active))
                ).scalar()
                or 0
            )
            total_guilds = int((await conn.execute(select(func.count()).select_from(consortias))).scalar() or 0)
            open_mall = int((await conn.execute(select(func.count()).select_from(mall_listings))).scalar() or 0)
            total_mails = int((await conn.execute(select(func.count()).select_from(mails))).scalar() or 0)
            sums = (
                await conn.execute(
                    select(
                        func.coalesce(func.sum(characters.c.gold), 0),
                        func.coalesce(func.sum(characters.c.point), 0),
                        func.coalesce(func.sum(characters.c.gift_token), 0),
                    ).where(characters.c.active)
                )
            ).one()

        sessions = ctx.online.sessions()
        h5_online = sum(1 for s in sessions if s.is_h5)
        def _sqlite_size(url: str) -> int:
            if url.startswith("sqlite") and "///" in url:
                p = Path(url.split("///", 1)[1])
                if p.is_file():
                    return p.stat().st_size
            return 0

        db_size = await asyncio.to_thread(_sqlite_size, str(self._d.settings.database_url))

        return _ok(
            {
                "server": {
                    "id": self._d.settings.server_id,
                    "name": self._d.settings.server_name,
                    "site": self._d.settings.site,
                    "publicHost": self._d.settings.public_host,
                    "timezone": self._d.settings.game_timezone,
                    "skipTutorial": bool(self._d.settings.skip_tutorial),
                    "serverTime": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "uptimeSeconds": int((datetime.now(UTC) - self._started_at).total_seconds()),
                    "dbSizeBytes": db_size,
                },
                "metrics": {
                    "onlineTotal": len(sessions),
                    "onlineH5": h5_online,
                    "onlineFlash": len(sessions) - h5_online,
                    "accountsTotal": total_accounts,
                    "accountsBanned": banned_accounts,
                    "charactersActive": active_chars,
                    "charactersInactive": inactive_chars,
                    "guildsTotal": total_guilds,
                    "mallOpen": open_mall,
                    "mailsTotal": total_mails,
                    "economyGold": int(sums[0] or 0),
                    "economyPoint": int(sums[1] or 0),
                    "economyGiftToken": int(sums[2] or 0),
                    "expRatesActive": len(ev.running_rates(ctx.world, now)),
                    "eventsRunning": len(ctx.events.running(now)),
                    "announcementsTotal": len(ctx.world.announcements),
                },
            }
        )

    async def logs(self, request: web.Request, _op: str) -> web.Response:
        limit = max(10, min(int(request.query.get("limit", "200")), 1000))
        level = request.query.get("level", "").strip().lower()
        q = request.query.get("q", "").strip().lower()
        kind = request.query.get("kind", "server").strip().lower()
        filename = "packets.log" if kind == "packets" else "server.log"

        log_dir = Path(getattr(self._d.settings, "log_dir", "logs"))
        log_file = log_dir / filename
        if not log_file.is_file():
            log_file = Path("logs") / filename
        if not log_file.is_file():
            return _ok({"lines": [], "file": str(log_file)})

        raw_lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()[-2000:]
        out = []
        for line in raw_lines:
            if q and q not in line.lower():
                continue
            if level and f'"level": "{level}"' not in line.lower() and f"[{level}]" not in line.lower():
                continue
            out.append(line)
        return _ok({"lines": out[-limit:], "file": str(log_file)})

    async def audit(self, request: web.Request, _op: str) -> web.Response:
        kind = request.query.get("kind", "cash").strip().lower()
        table = AUDIT_TABLES.get(kind)
        if table is None:
            raise ValidationError("tipo de auditoria inválido")
        limit = max(1, min(int(request.query.get("limit", "100")), 300))
        char_id = request.query.get("character_id", "").strip()
        q = request.query.get("q", "").strip().lower()

        engine = self._engine()
        stmt = select(table).order_by(desc(table.c.id)).limit(limit * 3 if q else limit)
        if char_id.isdigit():
            stmt = stmt.where(table.c.character_id == int(char_id))
        async with engine.connect() as conn:
            rows = [_row_dict(r) for r in await conn.execute(stmt)]
            char_ids = {int(r["character_id"]) for r in rows if r.get("character_id")}
            nicks: dict[int, str] = {}
            if char_ids:
                res = await conn.execute(
                    select(characters.c.id, characters.c.nickname).where(characters.c.id.in_(char_ids))
                )
                nicks = {int(r.id): str(r.nickname or f"#{r.id}") for r in res}
        for row in rows:
            cid = row.get("character_id")
            row["nickname"] = nicks.get(int(cid), "") if cid else ""
        if q:
            rows = [r for r in rows if q in json.dumps(r, ensure_ascii=False).lower()]
        return _ok({"items": rows[:limit]})

    # -- online ------------------------------------------------------------------------
    async def online_list(self, _: web.Request, _op: str) -> web.Response:
        sessions = []
        for s in self._ctx().online.sessions():
            snap = s.snapshot
            if snap is None:
                continue
            c = snap.character
            sessions.append(
                {
                    "id": c.id,
                    "accountId": c.account_id,
                    "username": snap.account.username,
                    "nickname": c.nickname,
                    "grades": c.grades,
                    "job": c.job,
                    "gold": c.gold,
                    "point": c.point,
                    "giftToken": c.gift_token,
                    "strategy": c.strategy,
                    "crystals": c.crystals,
                    "weary": c.weary,
                    "fightingCapacity": c.fighting_capacity,
                    "noviceProcess": c.novice_process,
                    "h5Novice": h5_novice_process(s) if s.is_h5 else "",
                    "client": "H5" if s.is_h5 else "Flash",
                    "peer": s.connection.transport.peer,
                    "scene": _scene_label(s),
                }
            )
        return _ok({"sessions": sessions})

    async def online_kick(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        await self._d.online.kick(char_id)
        log.info("admin kick", character_id=char_id, operator=op)
        return _ok({"characterId": char_id})

    async def online_alert(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        body = await _json_body(request)
        text = str(body.get("text", "")).strip()
        if not text:
            raise ValidationError("mensagem vazia")
        s = self._d.online.get(char_id)
        if s is None:
            raise NotFoundError("jogador não está online")
        player_handlers.alert(s, text)
        if body.get("chat", True):
            s.send(S_CHAT, pb.ChatChannelMsg(channel=int(body.get("channel", 12)), encodeMsg=text))
        log.info("admin alert enviado", character_id=char_id, operator=op)
        return _ok({"characterId": char_id})

    # -- contas ------------------------------------------------------------------------
    async def accounts_list(self, request: web.Request, _op: str) -> web.Response:
        q = request.query.get("q", "").strip()
        banned_filter = request.query.get("banned", "").strip()
        page = max(1, int(request.query.get("page", "1")))
        limit = max(1, min(int(request.query.get("limit", "25")), 100))

        engine = self._engine()
        stmt = select(accounts).order_by(desc(accounts.c.id))
        count_stmt = select(func.count()).select_from(accounts)
        if q:
            cond = accounts.c.username.ilike(f"%{q}%")
            if q.isdigit():
                cond = cond | (accounts.c.id == int(q))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        if banned_filter in ("0", "1", "true", "false"):
            is_ban = banned_filter in ("1", "true")
            stmt = stmt.where(accounts.c.banned == is_ban)
            count_stmt = count_stmt.where(accounts.c.banned == is_ban)

        async with engine.connect() as conn:
            total = int((await conn.execute(count_stmt)).scalar() or 0)
            rows = [_row_dict(r) for r in await conn.execute(stmt.offset((page - 1) * limit).limit(limit))]
            acc_ids = [int(r["id"]) for r in rows]
            chars_by_acc: dict[int, list[dict[str, Any]]] = {}
            if acc_ids:
                c_res = await conn.execute(
                    select(
                        characters.c.id,
                        characters.c.account_id,
                        characters.c.nickname,
                        characters.c.grades,
                        characters.c.active,
                        characters.c.server_id,
                    ).where(characters.c.account_id.in_(acc_ids))
                )
                for cr in c_res:
                    chars_by_acc.setdefault(int(cr.account_id), []).append(
                        {
                            "id": cr.id,
                            "nickname": cr.nickname,
                            "grades": cr.grades,
                            "active": cr.active,
                            "serverId": cr.server_id,
                            "online": self._d.online.get(int(cr.id)) is not None,
                        }
                    )
        for row in rows:
            row.pop("password_hash", None)
            row["characters"] = chars_by_acc.get(int(row["id"]), [])
        return _ok({"items": rows, "total": total, "page": page, "limit": limit})

    async def account_ban(self, request: web.Request, op: str) -> web.Response:
        acc_id = int(request.match_info["id"])
        body = await _json_body(request)
        banned = bool(body.get("banned", True))
        char_ids = await self._d.login.set_banned(acc_id, banned)
        if banned:
            for cid in char_ids:
                await self._d.online.kick(cid)
        log.info("admin ban", account_id=acc_id, banned=banned, operator=op)
        return _ok({"accountId": acc_id, "banned": banned, "kicked": char_ids if banned else []})

    async def account_password(self, request: web.Request, op: str) -> web.Response:
        acc_id = int(request.match_info["id"])
        body = await _json_body(request)
        new_pwd = str(body.get("password", "")).strip()
        if len(new_pwd) < 4:
            raise ValidationError("senha precisa de pelo menos 4 caracteres")
        pwd_hash = hashlib.md5(new_pwd.encode("utf-8")).hexdigest()
        async with self._engine().begin() as conn:
            res = await conn.execute(
                update(accounts).where(accounts.c.id == acc_id).values(password_hash=pwd_hash)
            )
            if not res.rowcount:
                raise NotFoundError("conta não encontrada")
        log.info("admin alterou senha da conta", account_id=acc_id, operator=op)
        return _ok({"accountId": acc_id})

    # -- personagens -------------------------------------------------------------------
    async def characters_list(self, request: web.Request, _op: str) -> web.Response:
        q = request.query.get("q", "").strip()
        active_only = request.query.get("active", "1") != "0"
        online_only = request.query.get("online", "") in ("1", "true")
        sort_by = request.query.get("sort", "id")
        page = max(1, int(request.query.get("page", "1")))
        limit = max(1, min(int(request.query.get("limit", "25")), 100))

        sort_map = {
            "id": desc(characters.c.id),
            "grades": desc(characters.c.grades),
            "power": desc(characters.c.fighting_capacity),
            "point": desc(characters.c.point),
            "gold": desc(characters.c.gold),
        }
        order_col = sort_map.get(sort_by, desc(characters.c.id))

        j = characters.join(accounts, characters.c.account_id == accounts.c.id)
        stmt = (
            select(
                characters.c.id,
                characters.c.account_id,
                accounts.c.username,
                accounts.c.banned,
                characters.c.nickname,
                characters.c.job,
                characters.c.sex,
                characters.c.active,
                characters.c.grades,
                characters.c.gp,
                characters.c.gold,
                characters.c.point,
                characters.c.gift_token,
                characters.c.strategy,
                characters.c.crystals,
                characters.c.fighting_capacity,
                characters.c.novice_process,
                characters.c.last_login_at,
                characters.c.created_at,
            )
            .select_from(j)
            .order_by(order_col)
        )
        count_stmt = select(func.count()).select_from(j)

        conds = []
        if active_only:
            conds.append(characters.c.active)
        if online_only:
            online_ids = [s.player_id for s in self._ctx().online.sessions()]
            if not online_ids:
                return _ok({"items": [], "total": 0, "page": page, "limit": limit})
            conds.append(characters.c.id.in_(online_ids))
        if q:
            like = f"%{q}%"
            q_cond = characters.c.nickname.ilike(like) | accounts.c.username.ilike(like)
            if q.isdigit():
                q_cond = q_cond | (characters.c.id == int(q))
            conds.append(q_cond)

        for cond in conds:
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        async with self._engine().connect() as conn:
            total = int((await conn.execute(count_stmt)).scalar() or 0)
            rows = [_row_dict(r) for r in await conn.execute(stmt.offset((page - 1) * limit).limit(limit))]

        for row in rows:
            sess = self._d.online.get(int(row["id"]))
            row["online"] = sess is not None
            row["client"] = ("H5" if sess.is_h5 else "Flash") if sess else None
        return _ok({"items": rows, "total": total, "page": page, "limit": limit})

    async def character_detail(self, request: web.Request, _op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        snap, sess = await self._load_snap(char_id)
        ctx, now = self._ctx(), self._now()
        c = snap.character
        tpl = ctx.templates
        leader = snap.leader
        stats = rules.leader_stats(snap, tpl, now) if leader is not None else None

        items_out = []
        for it in snap.items:
            row = tpl.get("ItemTempInfos", it.template_id) or {}
            items_out.append(
                {
                    "id": it.id,
                    "templateId": it.template_id,
                    "name": row.get("TemplateName", f"Item #{it.template_id}"),
                    "bagType": it.bag_type,
                    "pos": it.pos,
                    "count": it.count,
                    "strengthenGrade": it.strengthen_grade,
                    "isBinds": it.is_binds,
                    "isLocked": it.is_locked,
                    "quality": int(row.get("Profile") or 0),
                }
            )

        vip_st = ev.peek(snap, "vip")
        vip_type_st = ev.peek(snap, vip_handlers.VIP_TYPE)
        h5_st = ev.peek(snap, "h5_novice")
        amethyst_st = ev.peek(snap, rewards.AMETHYST_KEY)
        guild_info = ctx.guilds.of(char_id)

        async with self._engine().connect() as conn:
            recent_cash = [
                _row_dict(r)
                for r in await conn.execute(
                    select(cash_ledger)
                    .where(cash_ledger.c.character_id == char_id)
                    .order_by(desc(cash_ledger.c.id))
                    .limit(30)
                )
            ]
            recent_items = [
                _row_dict(r)
                for r in await conn.execute(
                    select(item_log).where(item_log.c.character_id == char_id).order_by(desc(item_log.c.id)).limit(30)
                )
            ]
            recent_logins = [
                _row_dict(r)
                for r in await conn.execute(
                    select(login_history)
                    .where(login_history.c.character_id == char_id)
                    .order_by(desc(login_history.c.id))
                    .limit(20)
                )
            ]

        return _ok(
            {
                "online": sess is not None,
                "scene": _scene_label(sess) if sess else None,
                "client": ("H5" if sess.is_h5 else "Flash") if sess else None,
                "account": {
                    "id": snap.account.id,
                    "username": snap.account.username,
                    "banned": snap.account.banned,
                    "createdAt": _iso(snap.account.created_at),
                    "lastLoginAt": _iso(snap.account.last_login_at),
                },
                "character": {
                    "id": c.id,
                    "nickname": c.nickname,
                    "job": c.job,
                    "sex": c.sex,
                    "camp": c.camp,
                    "active": c.active,
                    "grades": c.grades,
                    "gp": c.gp,
                    "totalGp": c.total_gp,
                    "gold": c.gold,
                    "point": c.point,
                    "giftToken": c.gift_token,
                    "strategy": c.strategy,
                    "crystals": c.crystals,
                    "amethyst": amethyst_st.value if amethyst_st else 0,
                    "weary": c.weary,
                    "wearyLimit": c.weary_limit,
                    "repute": c.repute,
                    "geste": c.geste,
                    "charm": c.charm,
                    "noviceProcess": c.novice_process,
                    "h5Novice": h5_st.text if h5_st else "",
                    "hasVicePassword": bool(c.vice_password),
                    "fightingCapacity": stats.fighting_capacity if stats else c.fighting_capacity,
                    "spaceX": c.space_x,
                    "spaceY": c.space_y,
                    "bagCount": c.bag_count,
                    "createdAt": _iso(c.created_at),
                    "lastLoginAt": _iso(c.last_login_at),
                },
                "vip": {
                    "active": vip_handlers.is_vip(snap, now),
                    "grade": vip_handlers.vip_grade(sess or SimpleNamespace(ctx=ctx), snap),
                    "vipGp": vip_st.value if vip_st else 0,
                    "expiresAt": vip_st.text if vip_st else "",
                    "vipType": vip_type_st.value if vip_type_st else 0,
                },
                "leader": (
                    {
                        "id": leader.id,
                        "templateId": leader.template_id,
                        "grades": leader.grades,
                        "power": leader.power,
                        "agility": leader.agility,
                        "intellect": leader.intellect,
                        "captain": leader.captain,
                        "physique": leader.physique,
                        "skillPoint": leader.skill_point,
                        "remainPoint": leader.remain_point,
                        "stats": asdict(stats) if stats else None,
                    }
                    if leader
                    else None
                ),
                "castle": (
                    {
                        "name": snap.castle.name,
                        "grade": snap.castle.grade,
                        "mapId": snap.castle.map_id,
                        "posX": snap.castle.pos_x,
                        "posY": snap.castle.pos_y,
                        "energy": snap.castle.energy,
                        "farmGrade": snap.castle.farm_grade,
                        "landGrade": snap.castle.land_grade,
                    }
                    if snap.castle
                    else None
                ),
                "guild": (
                    {
                        "id": guild_info[0].id,
                        "name": guild_info[0].name,
                        "dutyId": guild_info[1].duty_id,
                        "levels": guild_info[0].levels,
                    }
                    if guild_info
                    else None
                ),
                "items": items_out,
                "questsCount": len(snap.quests),
                "buildingsCount": len(snap.buildings),
                "petsCount": len(snap.pets),
                "audit": {"cash": recent_cash, "items": recent_items, "logins": recent_logins},
            }
        )

    async def character_patch(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        body = await _json_body(request)
        snap, sess = await self._load_snap(char_id)
        ctx, now = self._ctx(), self._now()
        c = snap.character

        old_point, old_gift = c.point, c.gift_token
        old_grade = c.grades
        army_changed = False
        extra_entities: list[Any] = []

        if "nickname" in body and body["nickname"] is not None:
            c.nickname = str(body["nickname"]).strip()
            if snap.leader is not None:
                snap.leader.nickname = c.nickname
                extra_entities.append(snap.leader)

        int_fields = (
            ("gold", "gold", 0),
            ("point", "point", 0),
            ("giftToken", "gift_token", 0),
            ("strategy", "strategy", 0),
            ("crystals", "crystals", 0),
            ("weary", "weary", 0),
            ("wearyLimit", "weary_limit", 1),
            ("repute", "repute", 0),
            ("geste", "geste", 0),
            ("charm", "charm", 0),
            ("noviceProcess", "novice_process", 0),
            ("spaceX", "space_x", 0),
            ("spaceY", "space_y", 0),
            ("bagCount", "bag_count", 0),
        )
        for json_key, attr, min_val in int_fields:
            if json_key in body and body[json_key] is not None:
                setattr(c, attr, min(2_000_000_000, max(min_val, int(body[json_key]))))

        if "h5Novice" in body and body["h5Novice"] is not None:
            st = ev.state(snap, "h5_novice", now)
            st.text, st.updated_at = str(body["h5Novice"]).strip(), now
            extra_entities.append(st)

        if "grades" in body and body["grades"] is not None:
            target = max(1, min(80, int(body["grades"])))
            if target != c.grades:
                steps = rules.grade_steps(ctx.templates)
                need = next((n for g, n in steps if g == target), 0)
                c.grades, c.gp, c.total_gp = target, 0, need
                if snap.leader is not None:
                    tpl = ctx.templates.hero(snap.leader.template_id)
                    growth = rules.GROWTH[rules.job_type(c.job)]
                    snap.leader.grades = target
                    snap.leader.hp = 0
                    for attr, per_lvl in growth.items():
                        base_val = getattr(tpl, attr)
                        setattr(snap.leader, attr, base_val + per_lvl * (target - 1))
                        setattr(snap.leader, f"{attr}_point", per_lvl * (target - 1))
                    rules.refresh_skill_point(snap.leader, ctx.templates)
                    rules.top_up_army(snap, ctx.templates)
                    extra_entities.append(snap.leader)
                    extra_entities.extend(snap.pawns)
                army_changed = True

        if c.point != old_point or c.gift_token != old_gift:
            extra_entities.append(
                CashLedger(
                    char_id,
                    c.point - old_point,
                    c.gift_token - old_gift,
                    c.point,
                    c.gift_token,
                    "gm",
                    "admin_patch",
                    now,
                    gm=op,
                )
            )

        await ctx.characters.save(c, *extra_entities)
        if sess is not None:
            self._push_player_sync(sess, army_sync=army_changed)
            if c.grades > old_grade:
                await player_handlers.push_level(sess, old_grade)
        log.info("admin editou personagem", character_id=char_id, operator=op)
        return _ok({"characterId": char_id, "grades": c.grades, "point": c.point, "gold": c.gold})

    async def character_xp(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        body = await _json_body(request)
        amount = int(body.get("amount", 0))
        if amount <= 0:
            raise ValidationError("quantidade de EXP deve ser positiva")
        snap, sess = await self._load_snap(char_id)
        ctx = self._ctx()
        before = snap.character.grades
        gained_lvl = rules.add_gp(snap, ctx.templates, amount)
        await ctx.characters.save(*rewards.owners(snap))
        if sess is not None:
            await player_handlers.granted(
                sess, [(rewards.EXP, amount)], [], rewards.text(ctx.templates, [(rewards.EXP, amount)]), chat=True
            )
        log.info("admin concedeu EXP", character_id=char_id, exp=amount, gained_levels=gained_lvl, operator=op)
        return _ok({"characterId": char_id, "before": before, "grades": snap.character.grades, "gp": snap.character.gp})

    async def character_vip(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        body = await _json_body(request)
        action = str(body.get("action", "grant"))
        snap, sess = await self._load_snap(char_id)
        ctx, now = self._ctx(), self._now()

        vip_st = ev.state(snap, "vip", now)
        type_st = ev.state(snap, vip_handlers.VIP_TYPE, now)
        mark_st = ev.state(snap, vip_handlers.VIP_GP_DAY, now)

        if action == "remove":
            vip_st.text = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            vip_st.updated_at = now
            type_st.value, type_st.updated_at = 0, now
            mark_st.text, mark_st.updated_at = "", now
            if "vipGp" in body and body["vipGp"] is not None:
                vip_st.value = max(0, int(body["vipGp"]))
        else:
            days = max(0, int(body.get("days", 31)))
            vip_type = int(body.get("vipType", 1))
            if days > 0:
                current_end = (ev.parse_time(vip_st.text) if vip_st.text else None) or now
                start = max(now, current_end)
                end = start + timedelta(days=days)
                vip_st.text = end.strftime("%Y-%m-%d %H:%M:%S")
                last = (gameday.game_day(now) - timedelta(days=1)).isoformat()
                mark_st.text = f"{last}|{vip_st.text}"
            if "vipGp" in body and body["vipGp"] is not None:
                vip_st.value = max(0, int(body["vipGp"]))
            elif vip_st.value == 0 and days > 0:
                vip_st.value = 100  # garante nível mínimo VIP 1 ao conceder pelo painel
            vip_st.updated_at = now
            mark_st.updated_at = now
            type_st.value, type_st.updated_at = vip_type, now

        await ctx.characters.save(vip_st, type_st, mark_st)
        if sess is not None:
            vip_handlers.vip_changed(sess)
            self._push_player_sync(sess)
        log.info("admin alterou VIP", character_id=char_id, action=action, operator=op)
        return _ok({"characterId": char_id, "vipGp": vip_st.value, "expiresAt": vip_st.text, "vipType": type_st.value})

    async def character_tutorial(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        body = await _json_body(request)
        mode = str(body.get("mode", "skip"))
        snap, sess = await self._load_snap(char_id)
        ctx, now = self._ctx(), self._now()
        st = ev.state(snap, "h5_novice", now)
        if mode == "skip":
            snap.character.novice_process = max(snap.character.novice_process, 19000)
            st.text = "_5_10_70_150_200"
        elif mode == "reset":
            snap.character.novice_process = 0
            st.text = ""
        else:
            snap.character.novice_process = max(0, int(body.get("noviceProcess", 0)))
            if "h5Novice" in body:
                st.text = str(body["h5Novice"])
        st.updated_at = now
        await ctx.characters.save(snap.character, st)
        if sess is not None:
            self._push_player_sync(sess)
        log.info("admin tutorial", character_id=char_id, mode=mode, operator=op)
        return _ok({"characterId": char_id, "noviceProcess": snap.character.novice_process, "h5Novice": st.text})

    async def character_clear_vice(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        snap, sess = await self._load_snap(char_id)
        snap.character.vice_password = ""
        snap.character.vice_reset_at = None
        await self._d.characters.save(snap.character)
        if sess is not None:
            sess.vice_confirmed = False
            self._push_player_sync(sess)
        log.info("admin removeu senha secundaria", character_id=char_id, operator=op)
        return _ok({"characterId": char_id})

    async def character_reset(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        body = await _json_body(request)
        confirm = str(body.get("confirmNickname", "")).strip()
        snap, _ = await self._load_snap(char_id)
        if (snap.character.nickname or "") != confirm:
            raise ValidationError("confirmação de apelido não confere")
        await self._d.online.kick(char_id)
        async with self._engine().begin() as conn:
            await conn.execute(characters.delete().where(characters.c.id == char_id))
        log.warning("admin resetou/excluiu personagem", character_id=char_id, nickname=confirm, operator=op)
        return _ok({"deletedCharacterId": char_id})

    # -- itens e catálogo XML ----------------------------------------------------------
    async def character_give_item(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        body = await _json_body(request)
        template_id = int(body.get("templateId", 0))
        count = max(1, int(body.get("count", 1)))
        strengthen = max(0, min(15, int(body.get("strengthenGrade", 0))))
        is_binds = bool(body.get("isBinds", True))
        via_mail = bool(body.get("viaMail", False))

        snap, sess = await self._load_snap(char_id)
        ctx, now = self._ctx(), self._now()
        drops = [(template_id, count)]

        if not via_mail and rewards.can_grant(snap, ctx.templates, drops, now):
            new_items, msg_text = rewards.grant(snap, ctx.templates, drops)
            logs = []
            for item in new_items:
                if strengthen > 0:
                    item.strengthen_grade = strengthen
                item.is_binds = is_binds
                logs.append(ItemLog(char_id, item.template_id, item.count, "gm_give", op, now))
            if template_id in (-400, -500):
                c = snap.character
                dp = count if template_id == -400 else 0
                dg = count if template_id == -500 else 0
                logs.append(CashLedger(char_id, dp, dg, c.point, c.gift_token, "gm", "admin_item", now, gm=op))
            await ctx.characters.save(*rewards.owners(snap), *new_items, *logs)
            if sess is not None:
                await player_handlers.granted(sess, drops, new_items, msg_text, chat=True)
            log.info(
                "admin entregou item na mochila", character_id=char_id, template_id=template_id, count=count, op=op
            )
            return _ok({"delivery": "bag", "count": count, "templateId": template_id})

        if template_id <= 0 and template_id not in (-100, -300, -400, -500, -600, -700, -200):
            raise ValidationError("template de item inválido")
        await mailbox.send_system_mail(
            ctx,
            char_id,
            str(body.get("mailTitle") or "Presente da Administração"),
            str(body.get("mailContents") or "Item enviado pelo painel de administração."),
            goods=[(template_id, count)],
        )
        log.info("admin entregou item por correio", character_id=char_id, template_id=template_id, count=count, op=op)
        return _ok({"delivery": "mail", "count": count, "templateId": template_id})

    async def character_edit_item(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        item_id = int(request.match_info["item_id"])
        body = await _json_body(request)
        snap, sess = await self._load_snap(char_id)
        item = next((i for i in snap.items if i.id == item_id), None)
        if item is None:
            raise NotFoundError("item não encontrado no personagem")
        if "count" in body and body["count"] is not None:
            item.count = max(1, int(body["count"]))
        if "strengthenGrade" in body and body["strengthenGrade"] is not None:
            item.strengthen_grade = max(0, min(15, int(body["strengthenGrade"])))
        if "isBinds" in body:
            item.is_binds = bool(body["isBinds"])
        if "isLocked" in body:
            item.is_locked = bool(body["isLocked"])
        await self._d.characters.save(item)
        if sess is not None:
            sess.send(S_ITEMS, bag.moved([item], char_id))
        log.info("admin editou item", character_id=char_id, item_id=item_id, operator=op)
        return _ok({"itemId": item_id})

    async def character_delete_item(self, request: web.Request, op: str) -> web.Response:
        char_id = int(request.match_info["id"])
        item_id = int(request.match_info["item_id"])
        snap, sess = await self._load_snap(char_id)
        item = next((i for i in snap.items if i.id == item_id), None)
        if item is None:
            raise NotFoundError("item não encontrado no personagem")
        snap.items.remove(item)
        await self._d.characters.save(
            ItemLog(char_id, item.template_id, -item.count, "gm_del", op, self._now()),
            delete=(item,),
        )
        if sess is not None:
            item.count = 0
            sess.send(S_ITEMS, bag.moved([], char_id, empty=[item]))
        log.info("admin removeu item", character_id=char_id, item_id=item_id, operator=op)
        return _ok({"deletedItemId": item_id})

    async def templates_search(self, request: web.Request, _op: str) -> web.Response:
        tpl = self._ctx().templates
        category = request.query.get("category", "ItemTempInfos").strip() or "ItemTempInfos"
        q = request.query.get("q", "").strip().lower()
        master_type = request.query.get("master_type", "").strip()
        page = max(1, int(request.query.get("page", "1")))
        limit = max(1, min(int(request.query.get("limit", "50")), 100))

        rows: list[Mapping[str, Any]] = []
        if category == "ItemTempInfos" and not master_type:
            for sp in SPECIAL_ITEMS:
                if not q or q in sp["name"].lower() or q == str(sp["templateId"]):
                    rows.append(
                        {
                            "TemplateId": str(sp["templateId"]),
                            "TemplateName": sp["name"],
                            "MasterType": str(sp["masterType"]),
                            "SonType": str(sp["sonType"]),
                            "Profile": str(sp["quality"]),
                        }
                    )

        for r in tpl.rows(category):
            if master_type and r.get("MasterType", "") != master_type:
                continue
            if q:
                tid = r.get("TemplateId", r.get("Id", ""))
                name = r.get("TemplateName", r.get("QuestName", r.get("BuildingName", r.get("CampaignName", ""))))
                if q not in tid.lower() and q not in name.lower():
                    continue
            rows.append(r)

        total = len(rows)
        slice_rows = [dict(r) for r in rows[(page - 1) * limit : page * limit]]
        return _ok(
            {
                "category": category,
                "categories": tpl.categories,
                "items": slice_rows,
                "total": total,
                "page": page,
                "limit": limit,
            }
        )

    # -- correio e broadcast -----------------------------------------------------------
    async def mail_recent(self, request: web.Request, _op: str) -> web.Response:
        limit = max(1, min(int(request.query.get("limit", "50")), 200))
        engine = self._engine()
        async with engine.connect() as conn:
            mail_rows = [
                _row_dict(r)
                for r in await conn.execute(select(mails).order_by(desc(mails.c.id)).limit(limit))
            ]
            m_ids = [int(r["id"]) for r in mail_rows]
            rec_ids = {int(r["receiver_id"]) for r in mail_rows}
            annex_map: dict[int, list[dict[str, Any]]] = {}
            nicks: dict[int, str] = {}
            if m_ids:
                for ar in await conn.execute(select(mail_annexes).where(mail_annexes.c.mail_id.in_(m_ids))):
                    annex_map.setdefault(int(ar.mail_id), []).append(_row_dict(ar))
            if rec_ids:
                for cr in await conn.execute(
                    select(characters.c.id, characters.c.nickname).where(characters.c.id.in_(rec_ids))
                ):
                    nicks[int(cr.id)] = str(cr.nickname or f"#{cr.id}")
        for m in mail_rows:
            m["receiverNickname"] = nicks.get(int(m["receiver_id"]), "")
            m["annexes"] = annex_map.get(int(m["id"]), [])
        return _ok({"items": mail_rows})

    async def mail_send(self, request: web.Request, op: str) -> web.Response:
        body = await _json_body(request)
        target = str(body.get("target", "character"))  # character | online | all
        title = str(body.get("title", "")).strip() or "Mensagem da Administração"
        contents = str(body.get("contents", "")).strip()
        raw_annexes = body.get("annexes") or []
        if not contents and not raw_annexes:
            raise ValidationError("informe um conteúdo ou ao menos 1 anexo")
        if len(raw_annexes) > mailbox.MAX_ANNEXES:
            raise ValidationError(f"no máximo {mailbox.MAX_ANNEXES} anexos por correio")

        goods: list[tuple[int, int]] = []
        for entry in raw_annexes:
            tid = int(entry["templateId"])
            cnt = max(1, int(entry.get("count", 1)))
            goods.append((tid, cnt))

        ctx, now = self._ctx(), self._now()
        recipient_ids: list[int] = []
        if target == "online":
            recipient_ids = [s.player_id for s in ctx.online.sessions()]
        elif target == "all":
            async with self._engine().connect() as conn:
                res = await conn.execute(select(characters.c.id).where(characters.c.active))
                recipient_ids = [int(r.id) for r in res]
        else:
            raw_ids = body.get("characterIds") or (
                [int(body["characterId"])] if body.get("characterId") is not None else []
            )
            recipient_ids = [int(x) for x in raw_ids if int(x) > 0]

        if not recipient_ids:
            raise ValidationError("nenhum destinatário válido encontrado")

        for cid in recipient_ids:
            mail = Mail(cid, now, title[:64], contents, mail_type=MailType.SYSTEM, send_type=mailbox.SYSTEM_SENDER)
            await mailbox.deliver(ctx.characters, ctx.online, mail, goods)

        log.info("admin enviou correio", target=target, recipients=len(recipient_ids), annexes=len(goods), operator=op)
        return _ok({"sentCount": len(recipient_ids), "goodsCount": len(goods)})

    async def broadcast(self, request: web.Request, op: str) -> web.Response:
        body = await _json_body(request)
        text = str(body.get("text", "")).strip()
        if not text:
            raise ValidationError("texto do anúncio não pode ser vazio")
        mode = str(body.get("mode", "both"))  # chat | alert | both
        channel = int(body.get("channel", 12))
        sessions = self._ctx().online.sessions()
        for s in sessions:
            if mode in ("chat", "both"):
                s.send(S_CHAT, pb.ChatChannelMsg(channel=channel, encodeMsg=text))
            if mode in ("alert", "both"):
                player_handlers.alert(s, text)
        log.info("admin broadcast", mode=mode, channel=channel, online=len(sessions), operator=op)
        return _ok({"delivered": len(sessions)})

    # -- anúncios agendados ------------------------------------------------------------
    async def announcements_list(self, _: web.Request, _op: str) -> web.Response:
        async with self._engine().connect() as conn:
            q = select(scheduled_announcements).order_by(scheduled_announcements.c.id)
            rows = [_row_dict(r) for r in await conn.execute(q)]
        return _ok({"items": rows})

    async def announcements_create(self, request: web.Request, op: str) -> web.Response:
        body = await _json_body(request)
        values = {
            "name": str(body.get("name", "aviso")).strip()[:64],
            "times": str(body.get("times", "12:00")).strip(),
            "weekdays": str(body.get("weekdays", "")).strip(),
            "channel": int(body.get("channel", 12)),
            "user_type": int(body.get("user_type", 1)),
            "is_center_tip": bool(body.get("is_center_tip", True)),
            "text": str(body.get("text", "")).strip(),
            "active": bool(body.get("active", True)),
            "source": f"admin:{op}",
        }
        if not values["text"] or not values["times"]:
            raise ValidationError("texto e horários são obrigatórios")
        async with self._engine().begin() as conn:
            res = await conn.execute(scheduled_announcements.insert().values(**values))
            new_id = int(res.inserted_primary_key[0])
        await self._reload_world()
        return _ok({"id": new_id})

    async def announcements_update(self, request: web.Request, op: str) -> web.Response:
        ann_id = int(request.match_info["id"])
        body = await _json_body(request)
        values: dict[str, Any] = {}
        for k in ("name", "times", "weekdays", "text"):
            if k in body:
                values[k] = str(body[k]).strip()
        for k in ("channel", "user_type"):
            if k in body:
                values[k] = int(body[k])
        for k in ("is_center_tip", "active"):
            if k in body:
                values[k] = bool(body[k])
        if not values:
            raise ValidationError("nenhum campo para atualizar")
        async with self._engine().begin() as conn:
            res = await conn.execute(
                update(scheduled_announcements).where(scheduled_announcements.c.id == ann_id).values(**values)
            )
            if not res.rowcount:
                raise NotFoundError("anúncio não encontrado")
        await self._reload_world()
        log.info("admin atualizou anuncio", id=ann_id, operator=op)
        return _ok({"id": ann_id})

    async def announcements_delete(self, request: web.Request, op: str) -> web.Response:
        ann_id = int(request.match_info["id"])
        async with self._engine().begin() as conn:
            res = await conn.execute(scheduled_announcements.delete().where(scheduled_announcements.c.id == ann_id))
            if not res.rowcount:
                raise NotFoundError("anúncio não encontrado")
        await self._reload_world()
        log.info("admin removeu anuncio", id=ann_id, operator=op)
        return _ok({"deletedId": ann_id})

    # -- EXP rates e events.json -------------------------------------------------------
    async def exp_rates_list(self, _: web.Request, _op: str) -> web.Response:
        async with self._engine().connect() as conn:
            q = select(exp_rate_events).order_by(desc(exp_rate_events.c.id))
            rows = [_row_dict(r) for r in await conn.execute(q)]
        return _ok({"items": rows})

    async def exp_rates_create(self, request: web.Request, op: str) -> web.Response:
        body = await _json_body(request)
        rate = int(body.get("rate", 100))
        begin_day = self._normalize_game_datetime(str(body.get("begin_day", "")))
        end_day = self._normalize_game_datetime(str(body.get("end_day", "")))
        if rate <= 0:
            raise ValidationError("taxa (>0), begin_day e end_day são obrigatórios")
        values = {
            "rate": rate,
            "begin_day": begin_day,
            "end_day": end_day,
            "begin_time": int(body.get("begin_time", 0)),
            "end_time": int(body.get("end_time", 86399)),
            "buffer_type": int(body.get("buffer_type", 0)),
            "source": f"admin:{op}",
        }
        async with self._engine().begin() as conn:
            res = await conn.execute(exp_rate_events.insert().values(**values))
            new_id = int(res.inserted_primary_key[0])
        await self._reload_world()
        for s in self._ctx().online.sessions():
            event_handlers.send_rate(s)
        log.info("admin criou evento EXP", id=new_id, rate=rate, operator=op)
        return _ok({"id": new_id})

    async def exp_rates_delete(self, request: web.Request, op: str) -> web.Response:
        rate_id = int(request.match_info["id"])
        async with self._engine().begin() as conn:
            res = await conn.execute(exp_rate_events.delete().where(exp_rate_events.c.id == rate_id))
            if not res.rowcount:
                raise NotFoundError("evento de EXP não encontrado")
        await self._reload_world()
        for s in self._ctx().online.sessions():
            event_handlers.send_rate(s)
        log.info("admin removeu evento EXP", id=rate_id, operator=op)
        return _ok({"deletedId": rate_id})

    async def events_get(self, _: web.Request, _op: str) -> web.Response:
        ctx, now = self._ctx(), self._now()
        path = Path(self._d.settings.events_file)
        def _read_events(p: Path, stamp: int) -> dict[str, Any]:
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
            return {"dataStamp": stamp, "actives": []}

        raw = await asyncio.to_thread(_read_events, path, ctx.events.data_stamp)
        running_ids = [a.active_id for a in ctx.events.running(now)]
        return _ok({"file": str(path), "data": raw, "runningIds": running_ids})

    async def events_put(self, request: web.Request, op: str) -> web.Response:
        body = await _json_body(request)
        payload = body.get("data", body)
        if not isinstance(payload, dict) or not isinstance(payload.get("actives"), list):
            raise ValidationError("payload deve conter dataStamp e lista actives")
        ctx = self._ctx()
        payload["dataStamp"] = max(int(payload.get("dataStamp", 1)), ctx.events.data_stamp + 1)

        path = Path(self._d.settings.events_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp.json")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            catalog = EventCatalog.load(tmp)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            raise ValidationError(f"catálogo de eventos inválido: {exc}") from None
        os.replace(tmp, path)
        ctx.events = catalog
        log.info("admin atualizou events.json", data_stamp=catalog.data_stamp, total=len(catalog.actives), operator=op)
        return _ok({"dataStamp": catalog.data_stamp, "total": len(catalog.actives)})

    # -- configurações do mundo e runtime ----------------------------------------------
    async def settings_get(self, _: web.Request, _op: str) -> web.Response:
        async with self._engine().connect() as conn:
            gs_rows = [_row_dict(r) for r in await conn.execute(select(game_settings).order_by(game_settings.c.key))]
            servers = [_row_dict(r) for r in await conn.execute(select(game_servers).order_by(game_servers.c.id))]
        for srv in servers:
            srv.pop("rsa_modulus", None)
        s = self._d.settings
        return _ok(
            {
                "gameSettings": gs_rows,
                "servers": servers,
                "runtime": {
                    "serverId": s.server_id,
                    "serverName": s.server_name,
                    "publicHost": s.public_host,
                    "site": s.site,
                    "timezone": s.game_timezone,
                    "skipTutorial": bool(s.skip_tutorial),
                    "idleTimeoutSeconds": s.idle_timeout_seconds,
                    "socketSessionTtlSeconds": s.socket_session_ttl_seconds,
                },
            }
        )

    async def settings_put(self, request: web.Request, op: str) -> web.Response:
        key = request.match_info["key"].strip()
        if not key or len(key) > 64:
            raise ValidationError("chave de configuração inválida")
        body = await _json_body(request)
        val = body.get("value")
        if isinstance(val, str):
            json.loads(val)  # valida JSON
            val_str = val
        else:
            val_str = json.dumps(val, ensure_ascii=False)

        async with self._engine().begin() as conn:
            existing = await conn.execute(select(game_settings.c.key).where(game_settings.c.key == key))
            if existing.first() is not None:
                await conn.execute(update(game_settings).where(game_settings.c.key == key).values(value=val_str))
            else:
                await conn.execute(
                    game_settings.insert().values(key=key, value=val_str, source=f"admin:{op}")
                )
        await self._reload_world()
        log.info("admin atualizou game_settings", key=key, operator=op)
        return _ok({"key": key})

    async def server_runtime_patch(self, request: web.Request, op: str) -> web.Response:
        body = await _json_body(request)
        s = self._d.settings
        if "skipTutorial" in body:
            val = bool(body["skipTutorial"])
            s.skip_tutorial = val
        if "serverName" in body and str(body["serverName"]).strip():
            new_name = str(body["serverName"]).strip()[:64]
            s.server_name = new_name
            async with self._engine().begin() as conn:
                await conn.execute(
                    update(game_servers).where(game_servers.c.id == s.server_id).values(name=new_name)
                )
        log.info("admin alterou runtime do servidor", operator=op, skip_tutorial=s.skip_tutorial, name=s.server_name)
        return _ok({"skipTutorial": bool(s.skip_tutorial), "serverName": s.server_name})

    async def server_wipe_players(self, request: web.Request, op: str) -> web.Response:
        body = await _json_body(request)
        if str(body.get("confirm", "")) != "WIPE_PLAYERS":
            raise ValidationError("confirmação inválida; envie confirm='WIPE_PLAYERS'")
        ctx = self._ctx()
        for sess in list(ctx.online.sessions()):
            await ctx.online.kick(sess.player_id)

        async with self._engine().begin() as conn:
            del_chars = int((await conn.execute(characters.delete())).rowcount or 0)
            del_accs = int((await conn.execute(accounts.delete())).rowcount or 0)
            await conn.execute(consortias.delete())
            await conn.execute(mall_listings.delete())
            await conn.execute(mails.delete())
            await conn.execute(world_boss_fights.delete())
            await conn.execute(cash_ledger.delete())
            await conn.execute(item_log.delete())
            await conn.execute(login_history.delete())
            await conn.execute(purchases.delete())

        # Limpa caches em memória de guildas e chefes
        ctx.guilds.guilds.clear()
        ctx.guilds.members.clear()
        ctx.guilds.invites.clear()
        ctx.guilds.events.clear()
        ctx.guilds.box.clear()
        ctx.guilds.profiles.clear()
        ctx.guilds.logout_at.clear()
        ctx.guilds.reserved.clear()
        ctx.bosses.pools.clear()

        log.warning("admin limpou todas as contas e personagens", accounts=del_accs, characters=del_chars, operator=op)
        return _ok({"deletedAccounts": del_accs, "deletedCharacters": del_chars})

    # -- World Boss, Guildas e Leilão --------------------------------------------------
    async def world_boss_list(self, _: web.Request, _op: str) -> web.Response:
        ctx = self._ctx()
        async with self._engine().connect() as conn:
            q = select(world_bosses).order_by(world_bosses.c.campaign_id)
            bosses = [_row_dict(r) for r in await conn.execute(q)]
            fights = [
                _row_dict(r)
                for r in await conn.execute(select(world_boss_fights).order_by(desc(world_boss_fights.c.id)).limit(15))
            ]
            f_ids = [int(f["id"]) for f in fights]
            top_wounds: dict[int, list[dict[str, Any]]] = {}
            if f_ids:
                w_stmt = (
                    select(world_boss_wounds)
                    .where(world_boss_wounds.c.fight_id.in_(f_ids))
                    .order_by(desc(world_boss_wounds.c.wound))
                )
                for wr in await conn.execute(w_stmt):
                    lst = top_wounds.setdefault(int(wr.fight_id), [])
                    if len(lst) < 5:
                        lst.append(_row_dict(wr))
        for f in fights:
            f["topWounds"] = top_wounds.get(int(f["id"]), [])
        pools = [
            {
                "campaignId": cid,
                "totalHp": p.fight.total_hp,
                "hp": p.hp,
                "settled": p.fight.settled,
                "playersCount": len(p.wounds),
            }
            for cid, p in ctx.bosses.pools.items()
        ]
        return _ok({"bosses": bosses, "recentFights": fights, "livePools": pools})

    async def world_boss_update(self, request: web.Request, op: str) -> web.Response:
        cid = int(request.match_info["campaign_id"])
        body = await _json_body(request)
        allowed = (
            "base_hp",
            "min_hp",
            "fast_seconds",
            "grow_pct",
            "shrink_pct",
            "kill_turn",
            "revive_seconds",
            "damage_per_gold",
            "battle_cap",
            "last_hit_gold",
            "last_hit_daru",
            "fight_capacity",
        )
        values = {k: int(body[k]) for k in allowed if k in body and body[k] is not None}
        if not values:
            raise ValidationError("nenhum campo válido informado")
        async with self._engine().begin() as conn:
            res = await conn.execute(update(world_bosses).where(world_bosses.c.campaign_id == cid).values(**values))
            if not res.rowcount:
                raise NotFoundError("World Boss não encontrado")
        await self._reload_world()
        log.info("admin atualizou World Boss", campaign_id=cid, operator=op)
        return _ok({"campaignId": cid})

    async def guilds_list(self, _: web.Request, _op: str) -> web.Response:
        async with self._engine().connect() as conn:
            g_rows = [_row_dict(r) for r in await conn.execute(select(consortias).order_by(desc(consortias.c.id)))]
            m_counts = {
                int(r.consortia_id): int(r[1])
                for r in await conn.execute(
                    select(consortia_members.c.consortia_id, func.count())
                    .group_by(consortia_members.c.consortia_id)
                )
            }
        for g in g_rows:
            g["memberCount"] = m_counts.get(int(g["id"]), 0)
        return _ok({"items": g_rows})

    async def guilds_patch(self, request: web.Request, op: str) -> web.Response:
        gid = int(request.match_info["id"])
        body = await _json_body(request)
        values: dict[str, Any] = {}
        for k in ("placard", "description", "group_placard"):
            if k in body and body[k] is not None:
                values[k] = str(body[k])[:255]
        for k in ("levels", "offer", "total_offer"):
            if k in body and body[k] is not None:
                values[k] = max(0, int(body[k]))
        if not values:
            raise ValidationError("nenhum campo para atualizar")
        async with self._engine().begin() as conn:
            res = await conn.execute(update(consortias).where(consortias.c.id == gid).values(**values))
            if not res.rowcount:
                raise NotFoundError("guilda não encontrada")
        # Atualiza também cache em memória de Guilds
        guild_obj = self._ctx().guilds.guilds.get(gid)
        if guild_obj is not None:
            for k, v in values.items():
                setattr(guild_obj, k, v)
        log.info("admin atualizou guilda", guild_id=gid, operator=op)
        return _ok({"id": gid})

    async def mall_list(self, _: web.Request, _op: str) -> web.Response:
        tpl = self._ctx().templates
        async with self._engine().connect() as conn:
            rows = [_row_dict(r) for r in await conn.execute(select(mall_listings).order_by(desc(mall_listings.c.id)))]
        return _ok({"items": rows, "totalTemplates": len(tpl.rows("ItemTempInfos"))})

    async def mall_cancel(self, request: web.Request, op: str) -> web.Response:
        listing_id = int(request.match_info["id"])
        async with self._engine().begin() as conn:
            res = await conn.execute(mall_listings.delete().where(mall_listings.c.id == listing_id))
            if not res.rowcount:
                raise NotFoundError("lote do leilão não encontrado")
        log.info("admin removeu lote do leilao", listing_id=listing_id, operator=op)
        return _ok({"deletedId": listing_id})
