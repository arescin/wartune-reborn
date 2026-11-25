"""Testes de integração da API HTTP de administração (/api/admin/*)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from tests.game.harness import logged_in


@pytest.mark.asyncio
async def test_admin_auth_guards_and_cors(tmp_path: Path) -> None:
    async with logged_in(tmp_path, novice=19000) as g:
        g.server.settings.admin_password = None
        g.server.settings.gm_secret = None
        client = TestClient(TestServer(g.server.http_app))
        await client.start_server()
        try:
            # Sem senha configurada, painel retorna 503
            resp = await client.post("/api/admin/auth/login", json={"username": "admin", "password": "x"})
            assert resp.status == 503
            resp = await client.get("/api/admin/overview")
            assert resp.status == 503

            # Configura credenciais
            g.server.settings.admin_username = "admin"
            g.server.settings.admin_password = "test_admin_password"
            g.server.settings.admin_token_secret = "test_token_secret"
            g.server.settings.gm_secret = "test_gm_secret"

            # CORS preflight inclui PATCH
            opt = await client.options("/api/admin/characters/1")
            assert opt.status == 204
            assert "PATCH" in opt.headers.get("Access-Control-Allow-Methods", "")

            # Sem token -> 401
            resp = await client.get("/api/admin/overview")
            assert resp.status == 401

            # Senha errada -> 401
            bad = await client.post("/api/admin/auth/login", json={"username": "admin", "password": "wrong"})
            assert bad.status == 401

            # Login válido -> token Bearer
            ok = await client.post(
                "/api/admin/auth/login",
                json={"username": "admin", "password": "test_admin_password"},
            )
            assert ok.status == 200
            data = await ok.json()
            assert data["username"] == "admin"
            token = data["token"]

            me = await client.get("/api/admin/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me.status == 200
            assert (await me.json())["username"] == "admin"

            # Fallback X-GM-Secret
            gm_ov = await client.get("/api/admin/overview", headers={"X-GM-Secret": "test_gm_secret"})
            assert gm_ov.status == 200
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_admin_full_control_flow(tmp_path: Path) -> None:
    async with logged_in(tmp_path, novice=0) as g:
        # Copia events.json para tmp_path para não alterar fixture do repositório
        events_copy = tmp_path / "events.json"
        shutil.copy2(g.server.settings.events_file, events_copy)
        g.server.settings.events_file = events_copy

        g.server.settings.admin_username = "admin"
        g.server.settings.admin_password = "test_admin_password"
        g.server.settings.admin_token_secret = "test_token_secret"

        extra = await g.join("alvo2")
        client = TestClient(TestServer(g.server.http_app))
        await client.start_server()
        try:
            login_resp = await client.post(
                "/api/admin/auth/login",
                json={"username": "admin", "password": "test_admin_password"},
            )
            token = (await login_resp.json())["token"]
            hdr = {"Authorization": f"Bearer {token}"}

            # 1. Overview & online
            ov = await (await client.get("/api/admin/overview", headers=hdr)).json()
            assert ov["metrics"]["onlineTotal"] >= 2
            assert ov["metrics"]["charactersActive"] >= 2

            online = await (await client.get("/api/admin/online", headers=hdr)).json()
            assert any(item["id"] == g.user_id for item in online["sessions"])

            # Alert individual online
            r_alert = await client.post(f"/api/admin/online/{g.user_id}/alert", json={"text": "Aviso GM"}, headers=hdr)
            assert r_alert.status == 200
            pkts = await g.idle(0.1)
            assert any(p.code == 111 for p in pkts)

            # 2. Contas: listar, trocar senha e banir/desbanir extra
            accs = await (await client.get("/api/admin/accounts", headers=hdr)).json()
            extra_acc = next(a for a in accs["items"] if a["username"] == "alvo2")
            acc_id = extra_acc["id"]
            assert (await client.post(f"/api/admin/accounts/{acc_id}/password", json={"password": "newpass123"}, headers=hdr)).status == 200
            ban = await client.post(f"/api/admin/accounts/{acc_id}/ban", json={"banned": True}, headers=hdr)
            assert ban.status == 200
            assert (await ban.json())["banned"] is True
            unban = await client.post(f"/api/admin/accounts/{acc_id}/ban", json={"banned": False}, headers=hdr)
            assert unban.status == 200
            assert (await unban.json())["banned"] is False

            # 3. Personagens: lista, detail, patch, xp, vip, tutorial, vice
            chars = await (await client.get("/api/admin/characters", headers=hdr)).json()
            assert chars["total"] >= 2

            det_resp = await client.get(f"/api/admin/characters/{g.user_id}", headers=hdr)
            assert det_resp.status == 200
            det = await det_resp.json()
            assert det["character"]["id"] == g.user_id

            patch_resp = await client.patch(
                f"/api/admin/characters/{g.user_id}",
                json={
                    "gold": 50000,
                    "point": 1200,
                    "giftToken": 300,
                    "grades": 15,
                    "noviceProcess": 19000,
                    "h5Novice": "_5_10",
                },
                headers=hdr,
            )
            assert patch_resp.status == 200
            patched = await patch_resp.json()
            assert patched["grades"] == 15
            assert patched["point"] == 1200
            assert patched["gold"] == 50000

            xp_resp = await client.post(f"/api/admin/characters/{g.user_id}/xp", json={"amount": 2500}, headers=hdr)
            assert xp_resp.status == 200

            vip_resp = await client.post(
                f"/api/admin/characters/{g.user_id}/vip",
                json={"action": "grant", "days": 30, "vipGp": 500, "vipType": 1},
                headers=hdr,
            )
            assert vip_resp.status == 200
            assert (await vip_resp.json())["vipGp"] == 500

            # Confirma detail após VIP (offline para extra e online para g)
            det2 = await (await client.get(f"/api/admin/characters/{g.user_id}", headers=hdr)).json()
            assert det2["vip"]["active"] is True
            assert det2["vip"]["grade"] >= 1

            tut_resp = await client.post(f"/api/admin/characters/{g.user_id}/tutorial", json={"mode": "skip"}, headers=hdr)
            assert tut_resp.status == 200
            assert (await tut_resp.json())["noviceProcess"] >= 19000

            vice_resp = await client.post(f"/api/admin/characters/{g.user_id}/vice-password", headers=hdr)
            assert vice_resp.status == 200

            # 4. Catálogo XML e Itens do personagem
            tpl_resp = await (await client.get("/api/admin/templates?q=", headers=hdr)).json()
            assert len(tpl_resp["items"]) > 0
            real_tpl = next(
                (it for it in tpl_resp["items"] if int(it.get("TemplateId") or it.get("Id") or 0) > 0),
                None,
            )
            assert real_tpl is not None
            real_tid = int(real_tpl.get("TemplateId") or real_tpl["Id"])

            give = await client.post(
                f"/api/admin/characters/{g.user_id}/items",
                json={"templateId": real_tid, "count": 2, "strengthenGrade": 3, "isBinds": True},
                headers=hdr,
            )
            assert give.status == 200

            det_items = await (await client.get(f"/api/admin/characters/{g.user_id}", headers=hdr)).json()
            created_item = next((i for i in det_items["items"] if i["templateId"] == real_tid), None)
            assert created_item is not None
            item_id = created_item["id"]

            ed_item = await client.patch(
                f"/api/admin/characters/{g.user_id}/items/{item_id}",
                json={"count": 4, "strengthenGrade": 5},
                headers=hdr,
            )
            assert ed_item.status == 200

            del_item = await client.delete(f"/api/admin/characters/{g.user_id}/items/{item_id}", headers=hdr)
            assert del_item.status == 200

            # Entrega moeda -400 via correio (força viaMail)
            give_mail = await client.post(
                f"/api/admin/characters/{g.user_id}/items",
                json={"templateId": -400, "count": 100, "viaMail": True},
                headers=hdr,
            )
            assert give_mail.status == 200
            assert (await give_mail.json())["delivery"] == "mail"

            # 5. Correio GM & Broadcast
            mail_res = await client.post(
                "/api/admin/mail/send",
                json={
                    "target": "character",
                    "characterId": g.user_id,
                    "title": "Recompensa",
                    "contents": "Teste admin",
                    "annexes": [{"templateId": -100, "count": 500}],
                },
                headers=hdr,
            )
            assert mail_res.status == 200
            assert (await mail_res.json())["sentCount"] == 1
            recent_mail = await (await client.get("/api/admin/mail", headers=hdr)).json()
            assert len(recent_mail["items"]) >= 1

            bc = await client.post("/api/admin/broadcast", json={"text": "Manutenção", "mode": "both"}, headers=hdr)
            assert bc.status == 200
            assert (await bc.json())["delivered"] >= 1
            bc_pkts = await g.idle(0.1)
            assert any(p.code == 83 for p in bc_pkts)
            assert any(p.code == 111 for p in bc_pkts)

            # 6. Anúncios agendados CRUD
            ann_cr = await client.post(
                "/api/admin/announcements",
                json={"name": "aviso1", "times": "12:00,18:00", "text": "Olá"},
                headers=hdr,
            )
            assert ann_cr.status == 200
            ann_id = (await ann_cr.json())["id"]
            assert len((await (await client.get("/api/admin/announcements", headers=hdr)).json())["items"]) >= 1
            assert (await client.put(f"/api/admin/announcements/{ann_id}", json={"active": False}, headers=hdr)).status == 200
            assert (await client.delete(f"/api/admin/announcements/{ann_id}", headers=hdr)).status == 200

            # 7. EXP rates CRUD + Events JSON
            exp_cr = await client.post(
                "/api/admin/exp-rates",
                json={"rate": 200, "begin_day": "2026-01-01", "end_day": "2026-12-31"},
                headers=hdr,
            )
            assert exp_cr.status == 200
            exp_id = (await exp_cr.json())["id"]
            assert len((await (await client.get("/api/admin/exp-rates", headers=hdr)).json())["items"]) >= 1
            assert (await client.delete(f"/api/admin/exp-rates/{exp_id}", headers=hdr)).status == 200

            ev_get = await (await client.get("/api/admin/events", headers=hdr)).json()
            assert "data" in ev_get
            ev_put = await client.put("/api/admin/events", json={"data": ev_get["data"]}, headers=hdr)
            assert ev_put.status == 200

            # 8. Configurações & runtime skipTutorial dinâmico
            assert (await client.put("/api/admin/settings/test_key", json={"value": {"enabled": True}}, headers=hdr)).status == 200
            st_get = await (await client.get("/api/admin/settings", headers=hdr)).json()
            assert any(row["key"] == "test_key" for row in st_get["gameSettings"])

            rt_patch = await client.patch(
                "/api/admin/server/runtime",
                json={"skipTutorial": True, "serverName": "S1 - Editado"},
                headers=hdr,
            )
            assert rt_patch.status == 200
            assert (await rt_patch.json())["skipTutorial"] is True

            # updateplayernovice passa a aplicar TUTORIAL_DONE em runtime sem reiniciar
            nov_res = await (
                await g.http.post(
                    "/updateplayernovice",
                    data={"userid": str(g.user_id), "key": g.key, "op": "1", "noviceprocess": "5"},
                )
            ).text()
            assert int(nov_res) >= 19000

            # 9. World Boss, Guildas, Leilão, Auditoria e Logs
            wb = await client.get("/api/admin/world-boss", headers=hdr)
            assert wb.status == 200
            assert (await client.get("/api/admin/guilds", headers=hdr)).status == 200
            assert (await client.get("/api/admin/mall", headers=hdr)).status == 200

            audit_cash = await (await client.get("/api/admin/audit?kind=cash", headers=hdr)).json()
            assert len(audit_cash["items"]) >= 1  # criado pelo admin_patch de balens

            logs_resp = await client.get("/api/admin/logs?kind=server&limit=50", headers=hdr)
            assert logs_resp.status == 200

            # 10. Kick online + detail offline após kick + reset de personagem descartável
            assert (await client.post(f"/api/admin/online/{extra.user_id}/kick", headers=hdr)).status == 200
            offline_det = await client.get(f"/api/admin/characters/{extra.user_id}", headers=hdr)
            assert offline_det.status == 200

            rst = await client.post(
                f"/api/admin/characters/{extra.user_id}/reset",
                json={"confirmNickname": "Alvo2"},
                headers=hdr,
            )
            assert rst.status == 200

            # 11. Wipe global exige confirmação exata e limpa contas + personagens
            bad_wipe = await client.post("/api/admin/server/wipe-players", json={"confirm": "no"}, headers=hdr)
            assert bad_wipe.status == 400
            ok_wipe = await client.post(
                "/api/admin/server/wipe-players",
                json={"confirm": "WIPE_PLAYERS"},
                headers=hdr,
            )
            assert ok_wipe.status == 200
            ov_after = await (await client.get("/api/admin/overview", headers=hdr)).json()
            assert ov_after["metrics"]["accountsTotal"] == 0
            assert ov_after["metrics"]["charactersActive"] == 0
        finally:
            await client.close()
