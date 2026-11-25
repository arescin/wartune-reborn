"""Views HTML para o portal do jogo e o player Ruffle."""

from __future__ import annotations

import html


def render_portal_html(
    server_name: str,
    online_count: int,
    public_host: str,
    socket_port: int,
    suggested_user: str,
    base_url: str,
) -> str:
    s_name = html.escape(server_name)
    s_user = html.escape(suggested_user)
    s_host = html.escape(public_host)
    s_base = html.escape(base_url)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wartune Reborn / Legend Online - Servidor Oficial</title>
  <style>
    :root {{
      --bg: #0b0e14;
      --card-bg: #151922;
      --card-border: #262c3a;
      --gold: #d4af37;
      --gold-hover: #f3c74d;
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --accent: #3b82f6;
      --green: #10b981;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: radial-gradient(circle at 50% 0%, #1e2638 0%, var(--bg) 75%);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2rem 1rem;
    }}
    .container {{
      max-width: 860px;
      width: 100%;
    }}
    header {{
      text-align: center;
      margin-bottom: 2.5rem;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: var(--green);
      padding: 0.35rem 0.85rem;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 1rem;
    }}
    .badge-dot {{
      width: 8px;
      height: 8px;
      background: var(--green);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--green);
    }}
    h1 {{
      font-size: 2.4rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #fff 30%, var(--gold) 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 0.5rem;
    }}
    p.subtitle {{
      color: var(--text-muted);
      font-size: 1.05rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 1.5rem;
      margin-bottom: 2rem;
    }}
    @media (max-width: 768px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 1.75rem;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
    }}
    .card-title {{
      font-size: 1.25rem;
      font-weight: 700;
      margin-bottom: 1.25rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      color: #fff;
    }}
    .form-group {{
      margin-bottom: 1.25rem;
    }}
    label {{
      display: block;
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-muted);
      margin-bottom: 0.4rem;
    }}
    input[type="text"] {{
      width: 100%;
      background: #0d1017;
      border: 1px solid #333c4e;
      border-radius: 8px;
      padding: 0.75rem 1rem;
      font-size: 1rem;
      color: #fff;
      outline: none;
      transition: border-color 0.2s;
    }}
    input[type="text"]:focus {{
      border-color: var(--gold);
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      padding: 0.85rem 1.25rem;
      border-radius: 8px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s;
      border: none;
    }}
    .btn-primary {{
      background: linear-gradient(135deg, var(--gold) 0%, #b8860b 100%);
      color: #0b0e14;
      box-shadow: 0 4px 15px rgba(212, 175, 55, 0.35);
    }}
    .btn-primary:hover {{
      background: linear-gradient(135deg, var(--gold-hover) 0%, var(--gold) 100%);
      box-shadow: 0 6px 20px rgba(212, 175, 55, 0.5);
      transform: translateY(-1px);
    }}
    .btn-secondary {{
      background: #202736;
      color: var(--text);
      margin-top: 0.75rem;
    }}
    .btn-secondary:hover {{
      background: #2b3548;
    }}
    .info-list {{
      list-style: none;
    }}
    .info-item {{
      display: flex;
      justify-content: space-between;
      padding: 0.7rem 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
      font-size: 0.9rem;
    }}
    .info-item:last-child {{
      border-bottom: none;
    }}
    .info-label {{
      color: var(--text-muted);
    }}
    .info-val {{
      font-weight: 600;
      color: #fff;
    }}
    .projector-box {{
      background: #0d1118;
      border: 1px solid #283142;
      border-radius: 10px;
      padding: 1.25rem;
      margin-top: 1.25rem;
    }}
    .projector-box h4 {{
      font-size: 0.95rem;
      color: var(--gold);
      margin-bottom: 0.5rem;
    }}
    .projector-box p {{
      font-size: 0.85rem;
      color: var(--text-muted);
      line-height: 1.5;
      margin-bottom: 0.75rem;
    }}
    .url-copy-box {{
      display: flex;
      gap: 0.5rem;
    }}
    .copy-btn {{
      padding: 0.5rem 0.85rem;
      background: #263143;
      color: #fff;
      border: 1px solid #3d4d68;
      border-radius: 6px;
      font-size: 0.85rem;
      cursor: pointer;
      white-space: nowrap;
    }}
    .copy-btn:hover {{
      background: #344259;
    }}
    footer {{
      margin-top: 2rem;
      text-align: center;
      font-size: 0.85rem;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="badge">
        <span class="badge-dot"></span>
        Servidor Operacional • {s_name}
      </div>
      <h1>Wartune Reborn</h1>
      <p class="subtitle">Legend Online Flash Emulator • Versão 1.3.0 Completa</p>
    </header>

    <div class="grid">
      <!-- Card Login / Entrar -->
      <div class="card">
        <div class="card-title">⚔️ Entrar no Jogo</div>
        <form action="/play" method="GET">
          <div class="form-group">
            <label for="username">Nome da sua Conta:</label>
            <input type="text" id="username" name="user" value="{s_user}" required autocomplete="off" maxlength="24">
          </div>
          <button type="submit" class="btn btn-primary">
            🚀 Jogar Agora no Navegador (Web)
          </button>
        </form>

        <button type="button" class="btn btn-secondary" onclick="randomGuest()">
          🎲 Gerar Conta Convidado Aleatória
        </button>

        <!-- Seção Flash Projector Desktop -->
        <div class="projector-box">
          <h4>⚡ Jogar via Adobe Flash Projector (Desktop)</h4>
          <p>Para jogar com aceleração 100% nativa sem emulador no navegador:</p>
          <div class="url-copy-box">
            <input type="text" id="projUrl" readonly value="{s_base}/projector?user={s_user}">
            <button class="copy-btn" onclick="copyProjectorUrl()">Copiar</button>
          </div>
          <p style="margin-top: 0.6rem; margin-bottom: 0;">
            <a href="https://archive.org/download/flashplayer_32_sa/flashplayer_32_sa.exe" target="_blank" style="color: var(--accent); text-decoration: underline;">
              Baixar Adobe Flash Player 32 Standalone (.exe)
            </a>
          </p>
        </div>
      </div>

      <!-- Card Status do Servidor -->
      <div class="card">
        <div class="card-title">📡 Status do Sistema</div>
        <ul class="info-list">
          <li class="info-item">
            <span class="info-label">Servidor</span>
            <span class="info-val">{s_name}</span>
          </li>
          <li class="info-item">
            <span class="info-label">Jogadores Conectados</span>
            <span class="info-val">{online_count} online</span>
          </li>
          <li class="info-item">
            <span class="info-label">Host de Conexão</span>
            <span class="info-val">{s_host}:{socket_port}</span>
          </li>
          <li class="info-item">
            <span class="info-label">Ponte WebSocket</span>
            <span class="info-val" style="color: var(--green);">wss:// Ativo</span>
          </li>
          <li class="info-item">
            <span class="info-label">Proxy CDN de Assets</span>
            <span class="info-val" style="color: var(--green);">Online (7Road)</span>
          </li>
          <li class="info-item">
            <span class="info-label">Banco de Dados</span>
            <span class="info-val">SQLite Async (Alembic)</span>
          </li>
          <li class="info-item">
            <span class="info-label">Templates XML</span>
            <span class="info-val">68.800+ nós (Ativo)</span>
          </li>
        </ul>
      </div>
    </div>

    <footer>
      Wartune Reborn • Emulador Open Source Python 3.12+ • Servidor Ativo
    </footer>
  </div>

  <script>
    function randomGuest() {{
      const prefixes = ["Lord", "Mage", "Knight", "Hunter", "Titan", "Shadow"];
      const rand = prefixes[Math.floor(Math.random() * prefixes.length)] + "_" + Math.floor(1000 + Math.random() * 9000);
      document.getElementById("username").value = rand;
      updateProjectorUrl(rand);
    }}

    function updateProjectorUrl(user) {{
      const baseUrl = window.location.origin;
      document.getElementById("projUrl").value = baseUrl + "/projector?user=" + encodeURIComponent(user);
    }}

    document.getElementById("username").addEventListener("input", (e) => {{
      updateProjectorUrl(e.target.value);
    }});

    function copyProjectorUrl() {{
      const el = document.getElementById("projUrl");
      el.select();
      navigator.clipboard.writeText(el.value);
      alert("Link copiado para a área de transferência!");
    }}
  </script>
</body>
</html>
"""


def render_play_html(
    username: str,
    ticket: str,
    site: str,
    config_url: str,
    public_host: str,
    socket_port: int,
    base_url: str,
) -> str:
    s_user = html.escape(username)
    s_ticket = html.escape(ticket)
    s_site = html.escape(site)
    s_config = html.escape(config_url)
    s_host = html.escape(public_host)
    s_base = html.escape(base_url)

    # Link direto para o Flash Projector
    direct_swf_url = f"{s_base}/projector?user={s_user}"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wartune Reborn - Jogando como {s_user}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #000;
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    #app {{
      display: flex;
      flex-direction: column;
      width: 100vw;
      height: 100vh;
    }}
    header {{
      height: 48px;
      background: #0f131a;
      border-bottom: 1px solid #232a38;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 1.25rem;
      z-index: 100;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-weight: 700;
      font-size: 0.95rem;
      color: #d4af37;
    }}
    .user-info {{
      font-size: 0.85rem;
      color: #94a3b8;
    }}
    .user-info b {{
      color: #fff;
    }}
    .actions {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .btn {{
      padding: 0.4rem 0.8rem;
      border-radius: 6px;
      font-size: 0.8rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      border: 1px solid #334155;
      background: #1e293b;
      color: #e2e8f0;
      transition: all 0.2s;
    }}
    .btn:hover {{
      background: #334155;
      color: #fff;
    }}
    .btn-gold {{
      background: #b8860b;
      border-color: #d4af37;
      color: #fff;
    }}
    .btn-gold:hover {{
      background: #d4af37;
    }}
    #game-wrapper {{
      flex: 1;
      width: 100%;
      height: calc(100vh - 48px);
      position: relative;
      background: #000;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    #flash-container {{
      width: 100%;
      height: 100%;
    }}
    #loading-overlay {{
      position: absolute;
      inset: 0;
      background: #0a0d14;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 1.25rem;
      z-index: 50;
      transition: opacity 0.5s ease;
    }}
    .spinner {{
      width: 48px;
      height: 48px;
      border: 4px solid #1e293b;
      border-top-color: #d4af37;
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }}
    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}
    .loading-text {{
      font-size: 1.1rem;
      color: #e2e8f0;
    }}
    .loading-sub {{
      font-size: 0.85rem;
      color: #64748b;
    }}
  </style>
  <!-- Ruffle Oficial WebAssembly Flash Player -->
  <script src="https://unpkg.com/@ruffle-rs/ruffle"></script>
</head>
<body>
  <div id="app">
    <header>
      <div class="brand">
        ⚔️ Wartune Reborn
      </div>
      <div class="user-info">
        Jogador: <b>{s_user}</b> &nbsp;|&nbsp; Servidor: <b>S1 - Local</b>
      </div>
      <div class="actions">
        <button class="btn" onclick="toggleFullscreen()">⛶ Tela Cheia</button>
        <button class="btn" onclick="copyProjectorLink()">📋 Link Flash Projector</button>
        <a href="/" class="btn">🔙 Sair / Portal</a>
      </div>
    </header>

    <div id="game-wrapper">
      <div id="loading-overlay">
        <div class="spinner"></div>
        <div class="loading-text">Iniciando o mundo de Wartune...</div>
        <div class="loading-sub">Carregando emulador Flash Ruffle e conectando ao servidor de jogo</div>
      </div>
      <div id="flash-container"></div>
    </div>
  </div>

  <input type="hidden" id="projector-link-val" value="{direct_swf_url}">

  <script>
    function toggleFullscreen() {{
      const elem = document.getElementById("game-wrapper");
      if (!document.fullscreenElement) {{
        elem.requestFullscreen().catch(err => alert("Erro ao entrar em tela cheia: " + err.message));
      }} else {{
        document.exitFullscreen();
      }}
    }}

    function copyProjectorLink() {{
      const link = document.getElementById("projector-link-val").value;
      navigator.clipboard.writeText(link);
      alert("Link direto para o Flash Player Projector copiado!\\n\\nAbra o Adobe Flash Player Standalone -> Arquivo -> Abrir e cole a URL.");
    }}

    // Limpa o SharedObject apenas com ?reset=1; ele guarda o estado do tutorial.
    if (new URLSearchParams(location.search).has("reset")) {{
      try {{
        localStorage.clear();
        sessionStorage.clear();
        if (window.indexedDB) {{
          indexedDB.deleteDatabase("ruffle");
        }}
      }} catch(e) {{}}
    }}

    // Configuração do Ruffle com SocketProxy para direcionar o tráfego TCP do Flash para WebSocket
    window.RufflePlayer = window.RufflePlayer || {{}};
    window.RufflePlayer.config = {{
      letterbox: "on",
      autoplay: "on",
      unmuteOverlay: "hidden",
      splashScreen: false,
      maxExecutionDuration: 0,
      socketProxy: [
        {{
          host: location.hostname,
          port: {socket_port},
          proxyUrl: (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws"
        }},
        {{
          host: location.hostname,
          port: 843,
          proxyUrl: (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws"
        }},
        {{
          host: "{s_host}",
          port: {socket_port},
          proxyUrl: (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws"
        }},
        {{
          host: "{s_host}",
          port: 843,
          proxyUrl: (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws"
        }},
        {{
          host: "127.0.0.1",
          port: {socket_port},
          proxyUrl: (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws"
        }},
        {{
          host: "127.0.0.1",
          port: 843,
          proxyUrl: (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws"
        }},
        {{
          host: "localhost",
          port: {socket_port},
          proxyUrl: (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws"
        }},
        {{
          host: "localhost",
          port: 843,
          proxyUrl: (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws"
        }}
      ]
    }};

    window.addEventListener("DOMContentLoaded", () => {{
      const container = document.getElementById("flash-container");
      const overlay = document.getElementById("loading-overlay");

      try {{
        const ruffle = window.RufflePlayer.newest();
        const player = ruffle.createPlayer();
        player.style.width = "100%";
        player.style.height = "100%";
        container.appendChild(player);

        const cacheBuster = "v=" + Date.now();
        const configUrl = "{s_config}" + (("{s_config}".indexOf("?") >= 0) ? "&" : "?") + cacheBuster;
        player.load({{
          url: "/cdn/Loading.swf?" + cacheBuster,
          base: "/cdn/",
          allowScriptAccess: true,
          parameters: {{
            user: "{s_user}",
            key: "{s_ticket}",
            site: "{s_site}",
            config: configUrl,
            http: location.protocol,
            playfb: "0"
          }}
        }}).then(() => {{
          setTimeout(() => {{
            overlay.style.opacity = "0";
            setTimeout(() => overlay.remove(), 500);
          }}, 800);
        }}).catch(err => {{
          console.error("Falha ao inicializar o Ruffle:", err);
          overlay.innerHTML = `
            <div style="color: #ef4444; font-size: 1.2rem; font-weight: bold; margin-bottom: 0.5rem;">Erro ao inicializar o player Flash</div>
            <div style="color: #94a3b8; font-size: 0.9rem; max-width: 500px; text-align: center;">${{err.message || err}}</div>
            <a href="/" class="btn" style="margin-top: 1.5rem;">Voltar ao Portal</a>
          `;
        }});
      }} catch (e) {{
        console.error("Ruffle não carregado:", e);
        overlay.innerHTML = `
          <div style="color: #ef4444; font-size: 1.2rem; font-weight: bold; margin-bottom: 0.5rem;">Falha no carregador Ruffle</div>
          <div style="color: #94a3b8; font-size: 0.9rem;">Verifique sua conexão à internet e tente recarregar.</div>
        `;
      }}
    }});
  </script>
</body>
</html>
"""
