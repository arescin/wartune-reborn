"""Testes do portal web integrado, player Ruffle e endpoints de suporte."""

from __future__ import annotations

from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.game.harness import logged_in
from wartune_server.domain.models import Account
from wartune_server.http.app import HttpDeps, build_http_app
from wartune_server.persistence.repositories import SqlAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_portal_home_and_config(tmp_path: Path) -> None:
    async with logged_in(tmp_path, novice=19000) as g:
        client = TestClient(TestServer(g.server.http_app))
        await client.start_server()
        try:
            # 1. GET / (Portal Home)
            resp = await client.get("/")
            assert resp.status == 200
            text = await resp.text()
            assert "Wartune Reborn" in text
            assert g.server.settings.server_name in text

            # 2. GET /config.xml
            resp = await client.get("/config.xml")
            assert resp.status == 200
            xml = await resp.text()
            assert '<LANGUAGE value="zh_cn" />' in xml
            assert f'site="{g.server.settings.site}"' in xml
            assert g.server.services.keys.modulus_b64 in xml

            # 3. GET /play (com emissão automática de ticket)
            resp = await client.get("/play?user=HeroTest")
            assert resp.status == 200
            play_html = await resp.text()
            assert "HeroTest" in play_html
            assert "Loading.swf" in play_html
            assert "RufflePlayer" in play_html

            # 4. POST /api/auth
            resp = await client.post("/api/auth", data={"username": "ApiHero"})
            assert resp.status == 200
            data = await resp.json()
            assert data["ok"] is True
            assert data["username"] == "ApiHero"
            assert len(data["ticket"]) > 10

            # 5. GET /projector (redirecionamento com ticket)
            resp = await client.get("/projector?user=FlashHero", allow_redirects=False)
            assert resp.status == 302
            loc = resp.headers["Location"]
            assert "Loading.swf" in loc
            assert "user=FlashHero" in loc
            assert "key=" in loc

            # 6. GET /cdn/xml/version.xml
            resp = await client.get("/cdn/xml/version.xml")
            assert resp.status == 200
            assert "version" in (await resp.text()).lower()

            # 7. Cadastro e login de jogador (/api/player/register e /api/player/login)
            no_acc = await client.post("/api/player/login", json={"username": "novo_user", "password": "secret"})
            assert no_acc.status == 404

            reg_ok = await client.post("/api/player/register", json={"username": "novo_user", "password": "secret"})
            assert reg_ok.status == 200
            assert (await reg_ok.json())["username"] == "novo_user"

            dup = await client.post("/api/player/register", json={"username": "novo_user", "password": "secret"})
            assert dup.status == 409

            bad_pwd = await client.post("/api/player/login", json={"username": "novo_user", "password": "wrong"})
            assert bad_pwd.status == 401

            login_ok = await client.post("/api/player/login", json={"username": "novo_user", "password": "secret"})
            assert login_ok.status == 200
        finally:
            await client.close()
