<?php
declare(strict_types=1);
require_once __DIR__ . '/src/bootstrap.php';
require_once __DIR__ . '/src/Admin.php';
require_once __DIR__ . '/src/AdminApi.php';

$me = current_account();
if (!$me) {
    redirect('index.php');
}

$allowedGmUsers = array_unique(array_merge(
    ['admin', 'arescin', 'arescinbr', 'root'],
    array_map('strtolower', $CONFIG['gm_users'] ?? [])
));

if (!in_array(strtolower($me['username']), $allowedGmUsers, true)) {
    http_response_code(403);
    echo '<!DOCTYPE html><html lang="pt-BR" class="dark"><head><meta charset="UTF-8"><title>Acesso Restrito</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-slate-950 text-slate-200 flex items-center justify-center min-h-screen"><div class="bg-slate-900 border border-red-500/30 p-8 rounded-2xl max-w-md text-center shadow-2xl"><h1 class="text-2xl font-bold text-red-400 mb-2">Acesso Negado</h1><p class="text-slate-400 mb-6">Esta área é exclusiva para Administradores e Game Masters (GM).</p><a href="index.php" class="inline-block px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition">Voltar ao Portal</a></div></body></html>';
    exit;
}

if (isset($_GET['api'])) {
    header('Content-Type: application/json; charset=utf-8');
    try {
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            csrf_check();
        }
        $api = new AdminApi(db(), (string)($CONFIG['gm_secret'] ?? ''), $me['username'], $CONFIG);
        $res = $api->handle((string)$_GET['api']);
        echo json_encode(['ok' => true, 'data' => $res], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    } catch (\Throwable $e) {
        http_response_code(400);
        echo json_encode(['ok' => false, 'error' => $e->getMessage()], JSON_UNESCAPED_UNICODE);
    }
    exit;
}

$csrfToken = csrf_token();
?>
<!DOCTYPE html>
<html lang="pt-BR" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wartune Reborn — Painel de Controle Administrativo</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
                        mono: ['"JetBrains Mono"', 'monospace'],
                    },
                    colors: {
                        brand: {
                            50: '#eff6ff',
                            500: '#3b82f6',
                            600: '#2563eb',
                            700: '#1d4ed8',
                        },
                        dark: {
                            bg: '#0a0d14',
                            card: '#111726',
                            border: '#1e293b',
                            input: '#0d131f'
                        }
                    }
                }
            }
        }
    </script>
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        .glass-panel { background: rgba(17, 23, 38, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.07); }
        .glass-card { background: rgba(15, 21, 34, 0.6); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.05); }
        .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scroll::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
        .custom-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 9999px; }
        .custom-scroll::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.25); }
    </style>
</head>
<body class="bg-dark-bg text-slate-200 antialiased min-h-screen flex flex-col selection:bg-blue-600 selection:text-white">

    <!-- TOAST CONTAINER -->
    <div id="toast-container" class="fixed top-5 right-5 z-50 flex flex-col gap-2 pointer-events-none"></div>

    <!-- MAIN APP WRAPPER -->
    <div class="flex flex-1 min-h-screen overflow-hidden">
        <!-- SIDEBAR -->
        <aside class="w-64 glass-panel flex flex-col border-r border-slate-800 shrink-0 z-30 transition-all duration-300">
            <!-- Logo Header -->
            <div class="h-16 flex items-center gap-3 px-6 border-b border-slate-800/80 bg-slate-900/40">
                <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20 text-white font-bold">
                    <i data-lucide="shield" class="w-5 h-5"></i>
                </div>
                <div>
                    <h1 class="font-bold text-sm tracking-wide text-white">WARTUNE REBORN</h1>
                    <p class="text-xs text-blue-400 font-medium tracking-wider uppercase">Master Control</p>
                </div>
            </div>

            <!-- Navigation Links -->
            <nav class="flex-1 p-4 space-y-1.5 overflow-y-auto custom-scroll">
                <button onclick="switchTab('dashboard')" id="nav-dashboard" class="nav-item w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition text-white bg-blue-600 shadow-md shadow-blue-600/20">
                    <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
                    <span>Dashboard</span>
                </button>
                <button onclick="switchTab('players')" id="nav-players" class="nav-item w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition text-slate-400 hover:text-white hover:bg-slate-800/60">
                    <i data-lucide="users" class="w-4 h-4"></i>
                    <span>Jogadores & Contas</span>
                </button>
                <button onclick="switchTab('mail')" id="nav-mail" class="nav-item w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition text-slate-400 hover:text-white hover:bg-slate-800/60">
                    <i data-lucide="mail" class="w-4 h-4"></i>
                    <span>Correio & Envio de Itens</span>
                </button>
                <button onclick="switchTab('recharge')" id="nav-recharge" class="nav-item w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition text-slate-400 hover:text-white hover:bg-slate-800/60">
                    <i data-lucide="gem" class="w-4 h-4"></i>
                    <span>Recarga de Diamantes</span>
                </button>
                <button onclick="switchTab('logs')" id="nav-logs" class="nav-item w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition text-slate-400 hover:text-white hover:bg-slate-800/60">
                    <i data-lucide="scroll-text" class="w-4 h-4"></i>
                    <span>Logs & Auditoria</span>
                </button>
            </nav>

            <!-- User Footer -->
            <div class="p-4 border-t border-slate-800/80 bg-slate-900/30 flex items-center justify-between">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-blue-400 uppercase">
                        <?= htmlspecialchars(substr($me['username'], 0, 2)) ?>
                    </div>
                    <div class="min-w-0 truncate">
                        <p class="text-xs font-semibold text-white truncate"><?= htmlspecialchars($me['username']) ?></p>
                        <p class="text-[10px] text-emerald-400 font-mono">GM AUTORIZADO</p>
                    </div>
                </div>
                <a href="index.php" title="Voltar ao Portal" class="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition">
                    <i data-lucide="log-out" class="w-4 h-4"></i>
                </a>
            </div>
        </aside>

        <!-- CONTENT AREA -->
        <main class="flex-1 flex flex-col min-h-screen overflow-y-auto custom-scroll">
            <!-- Topbar Header -->
            <header class="h-16 glass-panel border-b border-slate-800/80 px-8 flex items-center justify-between shrink-0 sticky top-0 z-20">
                <div class="flex items-center gap-4">
                    <h2 id="page-title" class="text-lg font-bold text-white">Visão Geral do Servidor</h2>
                    <span id="server-status-pill" class="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        Online
                    </span>
                </div>
                <div class="flex items-center gap-3">
                    <button onclick="refreshCurrentTab()" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 text-xs font-medium border border-slate-700 transition">
                        <i data-lucide="refresh-cw" class="w-3.5 h-3.5" id="refresh-icon"></i>
                        <span>Atualizar</span>
                    </button>
                    <a href="play.php" target="_blank" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20 transition">
                        <i data-lucide="gamepad-2" class="w-3.5 h-3.5"></i>
                        <span>Abrir Jogo</span>
                    </a>
                </div>
            </header>

            <!-- Tab Content Container -->
            <div class="p-8 max-w-7xl w-full mx-auto space-y-6 flex-1">
                
                <!-- TAB: DASHBOARD -->
                <div id="tab-dashboard" class="tab-content space-y-6">
                    <!-- Metric Cards Grid -->
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <div class="glass-card p-5 rounded-2xl relative overflow-hidden">
                            <div class="flex justify-between items-start">
                                <div>
                                    <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Contas Criadas</p>
                                    <h3 id="stat-accounts" class="text-2xl font-bold text-white mt-1">--</h3>
                                </div>
                                <div class="p-2.5 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                    <i data-lucide="user-check" class="w-5 h-5"></i>
                                </div>
                            </div>
                            <div class="mt-3 text-xs text-slate-500 flex items-center gap-1.5">
                                <span>Cadastros totais no banco</span>
                            </div>
                        </div>

                        <div class="glass-card p-5 rounded-2xl relative overflow-hidden">
                            <div class="flex justify-between items-start">
                                <div>
                                    <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Personagens Ativos</p>
                                    <h3 id="stat-chars" class="text-2xl font-bold text-white mt-1">--</h3>
                                </div>
                                <div class="p-2.5 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
                                    <i data-lucide="swords" class="w-5 h-5"></i>
                                </div>
                            </div>
                            <div class="mt-3 text-xs text-slate-500 flex items-center gap-1.5">
                                <span>Heróis criados nos servidores</span>
                            </div>
                        </div>

                        <div class="glass-card p-5 rounded-2xl relative overflow-hidden">
                            <div class="flex justify-between items-start">
                                <div>
                                    <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Diamantes Circulando</p>
                                    <h3 id="stat-diamonds" class="text-2xl font-bold text-amber-400 mt-1">--</h3>
                                </div>
                                <div class="p-2.5 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                    <i data-lucide="gem" class="w-5 h-5"></i>
                                </div>
                            </div>
                            <div class="mt-3 text-xs text-slate-500 flex items-center gap-1.5">
                                <span>Soma nas carteiras dos jogadores</span>
                            </div>
                        </div>

                        <div class="glass-card p-5 rounded-2xl relative overflow-hidden">
                            <div class="flex justify-between items-start">
                                <div>
                                    <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Recarregado</p>
                                    <h3 id="stat-recharge" class="text-2xl font-bold text-emerald-400 mt-1">--</h3>
                                </div>
                                <div class="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                    <i data-lucide="trending-up" class="w-5 h-5"></i>
                                </div>
                            </div>
                            <div class="mt-3 text-xs text-slate-500 flex items-center gap-1.5">
                                <span>Diamantes injetados via ledger</span>
                            </div>
                        </div>
                    </div>

                    <!-- Services & Economy Grid -->
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <!-- Status dos Serviços -->
                        <div class="glass-panel p-6 rounded-2xl space-y-4">
                            <h4 class="text-sm font-bold text-white flex items-center gap-2">
                                <i data-lucide="server" class="w-4 h-4 text-blue-400"></i>
                                Monitoramento de Serviços
                            </h4>
                            <div class="space-y-3" id="server-ports-list">
                                <div class="p-3 bg-slate-900/50 rounded-xl border border-slate-800 flex items-center justify-between">
                                    <span class="text-xs font-medium text-slate-300">Game Server (Python)</span>
                                    <span class="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">Porta 5000</span>
                                </div>
                                <div class="p-3 bg-slate-900/50 rounded-xl border border-slate-800 flex items-center justify-between">
                                    <span class="text-xs font-medium text-slate-300">Database (PostgreSQL)</span>
                                    <span class="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">Porta 5432</span>
                                </div>
                                <div class="p-3 bg-slate-900/50 rounded-xl border border-slate-800 flex items-center justify-between">
                                    <span class="text-xs font-medium text-slate-300">Portal & Web Server</span>
                                    <span class="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">Apache/PHP 8.2</span>
                                </div>
                            </div>
                        </div>

                        <!-- Recursos em Circulação -->
                        <div class="glass-panel p-6 rounded-2xl space-y-4 lg:col-span-2">
                            <h4 class="text-sm font-bold text-white flex items-center gap-2">
                                <i data-lucide="coins" class="w-4 h-4 text-amber-400"></i>
                                Economia Global em Circulação
                            </h4>
                            <div class="grid grid-cols-2 sm:grid-cols-3 gap-4 pt-1">
                                <div class="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80">
                                    <p class="text-xs text-slate-400">Ouro Acumulado</p>
                                    <p id="stat-gold" class="text-lg font-bold text-amber-300 mt-1 font-mono">--</p>
                                </div>
                                <div class="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80">
                                    <p class="text-xs text-slate-400">Diamantes Vinculados</p>
                                    <p id="stat-gift" class="text-lg font-bold text-cyan-300 mt-1 font-mono">--</p>
                                </div>
                                <div class="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80">
                                    <p class="text-xs text-slate-400">Cristais de Alma / Estratégia</p>
                                    <p id="stat-strategy" class="text-lg font-bold text-purple-300 mt-1 font-mono">--</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Jogadores Recentes -->
                    <div class="glass-panel rounded-2xl overflow-hidden">
                        <div class="p-5 border-b border-slate-800 flex items-center justify-between">
                            <h4 class="text-sm font-bold text-white flex items-center gap-2">
                                <i data-lucide="activity" class="w-4 h-4 text-blue-400"></i>
                                Últimos Personagens Ativos / Criados
                            </h4>
                            <button onclick="switchTab('players')" class="text-xs text-blue-400 hover:text-blue-300 font-medium transition">
                                Ver todos os jogadores &rarr;
                            </button>
                        </div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-xs">
                                <thead class="bg-slate-900/60 text-slate-400 uppercase font-semibold border-b border-slate-800">
                                    <tr>
                                        <th class="p-3.5 pl-6">Personagem</th>
                                        <th class="p-3.5">Conta</th>
                                        <th class="p-3.5">Nível</th>
                                        <th class="p-3.5">Classe</th>
                                        <th class="p-3.5">Ouro</th>
                                        <th class="p-3.5">Diamantes</th>
                                        <th class="p-3.5 pr-6 text-right">Ações</th>
                                    </tr>
                                </thead>
                                <tbody id="dashboard-recent-chars" class="divide-y divide-slate-800/50 text-slate-300">
                                    <tr><td colspan="7" class="p-6 text-center text-slate-500">Carregando dados...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- TAB: PLAYERS & ACCOUNTS -->
                <div id="tab-players" class="tab-content hidden space-y-6">
                    <!-- Barra de Pesquisa e Filtros -->
                    <div class="glass-panel p-4 rounded-2xl flex flex-col md:flex-row gap-4 items-center justify-between">
                        <div class="relative flex-1 w-full">
                            <i data-lucide="search" class="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"></i>
                            <input type="text" id="player-search-input" placeholder="Buscar por Nickname, ID do Personagem ou Login da Conta..." 
                                class="w-full pl-10 pr-4 py-2 bg-slate-900/80 border border-slate-700/80 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition"
                                onkeyup="handlePlayerSearch(event)">
                        </div>
                        <button onclick="searchPlayers()" class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition shrink-0 shadow-md shadow-blue-600/20">
                            Pesquisar
                        </button>
                    </div>

                    <!-- Resultados da Busca -->
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6" id="search-results-section">
                        <!-- Coluna Personagens -->
                        <div class="glass-panel rounded-2xl overflow-hidden flex flex-col">
                            <div class="p-4 border-b border-slate-800 bg-slate-900/40 font-bold text-sm text-white flex items-center gap-2">
                                <i data-lucide="shield" class="w-4 h-4 text-purple-400"></i>
                                Personagens Encontrados
                            </div>
                            <div class="p-4 flex-1 overflow-y-auto max-h-[500px] custom-scroll space-y-3" id="char-search-list">
                                <p class="text-xs text-slate-500 text-center py-6">Digite um termo acima para pesquisar.</p>
                            </div>
                        </div>

                        <!-- Coluna Contas -->
                        <div class="glass-panel rounded-2xl overflow-hidden flex flex-col">
                            <div class="p-4 border-b border-slate-800 bg-slate-900/40 font-bold text-sm text-white flex items-center gap-2">
                                <i data-lucide="user" class="w-4 h-4 text-blue-400"></i>
                                Contas Encontradas
                            </div>
                            <div class="p-4 flex-1 overflow-y-auto max-h-[500px] custom-scroll space-y-3" id="account-search-list">
                                <p class="text-xs text-slate-500 text-center py-6">Digite um termo acima para pesquisar.</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- TAB: MAIL & ITEMS SENDING -->
                <div id="tab-mail" class="tab-content hidden space-y-6">
                    <div class="glass-panel p-6 rounded-2xl">
                        <div class="border-b border-slate-800 pb-4 mb-6">
                            <h3 class="text-base font-bold text-white flex items-center gap-2">
                                <i data-lucide="send" class="w-5 h-5 text-blue-400"></i>
                                Envio de Correio, Recompensas e Itens
                            </h3>
                            <p class="text-xs text-slate-400 mt-1">
                                Envie itens do catálogo oficial, Ouro e Diamantes diretamente para a caixa postal de um jogador específico ou para <strong class="text-amber-400">todos os jogadores ativos do servidor</strong>.
                            </p>
                        </div>

                        <form id="form-send-mail" onsubmit="submitSendMail(event)" class="space-y-6">
                            <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrfToken) ?>">

                            <!-- Destinatário -->
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div>
                                    <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Tipo de Destinatário</label>
                                    <div class="flex gap-4">
                                        <label class="flex items-center gap-2.5 p-3 rounded-xl bg-slate-900/60 border border-slate-700/80 cursor-pointer flex-1 hover:border-slate-600 transition">
                                            <input type="radio" name="target_type" value="single" checked onchange="toggleTargetType(this.value)" class="text-blue-600 focus:ring-0">
                                            <span class="text-xs font-medium text-white">Jogador Específico</span>
                                        </label>
                                        <label class="flex items-center gap-2.5 p-3 rounded-xl bg-slate-900/60 border border-slate-700/80 cursor-pointer flex-1 hover:border-slate-600 transition">
                                            <input type="radio" name="target_type" value="all" onchange="toggleTargetType(this.value)" class="text-blue-600 focus:ring-0">
                                            <span class="text-xs font-medium text-amber-400 font-bold">Broadcast (Todos)</span>
                                        </label>
                                    </div>
                                </div>

                                <div id="container-char-target">
                                    <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Personagem Destinatário (ID ou Nick)</label>
                                    <input type="text" name="receiver" id="mail-receiver-input" placeholder="Ex: 10001 ou ShadowHero" 
                                        class="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/80 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500 transition">
                                </div>
                            </div>

                            <!-- Mensagem -->
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div>
                                    <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Título da Mensagem</label>
                                    <input type="text" name="title" required value="Recompensa do Sistema GM" 
                                        class="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/80 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500 transition">
                                </div>
                                <div>
                                    <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Nome do Remetente</label>
                                    <input type="text" name="sender_nick" value="Sistema GM" 
                                        class="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/80 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500 transition">
                                </div>
                            </div>

                            <div>
                                <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Conteúdo do Correio</label>
                                <textarea name="contents" rows="3" required class="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/80 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500 transition">Olá herói! Você recebeu uma bonificação especial da administração de Wartune Reborn. Aproveite!</textarea>
                            </div>

                            <!-- Moedas em Anexo -->
                            <div class="border-t border-slate-800 pt-5">
                                <h4 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                                    <i data-lucide="coins" class="w-4 h-4 text-amber-400"></i>
                                    Moedas em Anexo (Opcional)
                                </h4>
                                <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                    <div>
                                        <label class="text-xs text-slate-400 mb-1 block">Ouro</label>
                                        <input type="number" name="gold" min="0" max="2000000000" value="0" class="w-full px-3 py-2 bg-slate-900/80 border border-slate-700 rounded-lg text-sm font-mono text-amber-300 focus:outline-none focus:border-blue-500">
                                    </div>
                                    <div>
                                        <label class="text-xs text-slate-400 mb-1 block">Diamantes</label>
                                        <input type="number" name="diamonds" min="0" max="2000000000" value="0" class="w-full px-3 py-2 bg-slate-900/80 border border-slate-700 rounded-lg text-sm font-mono text-cyan-300 focus:outline-none focus:border-blue-500">
                                    </div>
                                    <div>
                                        <label class="text-xs text-slate-400 mb-1 block">Diamantes Vinculados</label>
                                        <input type="number" name="bound_diamonds" min="0" max="2000000000" value="0" class="w-full px-3 py-2 bg-slate-900/80 border border-slate-700 rounded-lg text-sm font-mono text-purple-300 focus:outline-none focus:border-blue-500">
                                    </div>
                                </div>
                            </div>

                            <!-- Itens em Anexo com Autocomplete -->
                            <div class="border-t border-slate-800 pt-5">
                                <div class="flex justify-between items-center mb-3">
                                    <h4 class="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                                        <i data-lucide="package" class="w-4 h-4 text-indigo-400"></i>
                                        Itens em Anexo (Máximo 4 slots)
                                    </h4>
                                    <button type="button" onclick="addMailItemSlot()" class="text-xs text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-1 transition">
                                        <i data-lucide="plus-circle" class="w-3.5 h-3.5"></i> Adicionar Slot
                                    </button>
                                </div>
                                <div id="mail-items-container" class="space-y-3">
                                    <!-- Slots adicionados via JS -->
                                </div>
                            </div>

                            <div class="pt-4 flex justify-end">
                                <button type="submit" class="px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-bold text-sm shadow-lg shadow-blue-600/30 transition flex items-center gap-2">
                                    <i data-lucide="send" class="w-4 h-4"></i>
                                    <span>Confirmar e Enviar Correio</span>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- TAB: RECHARGE -->
                <div id="tab-recharge" class="tab-content hidden space-y-6">
                    <div class="glass-panel p-6 rounded-2xl max-w-2xl mx-auto">
                        <div class="border-b border-slate-800 pb-4 mb-6">
                            <h3 class="text-base font-bold text-white flex items-center gap-2">
                                <i data-lucide="gem" class="w-5 h-5 text-amber-400"></i>
                                Recarga Manual de Diamantes
                            </h3>
                            <p class="text-xs text-slate-400 mt-1">
                                Injeta créditos diretamente na tabela <code class="text-cyan-400">cash_ledger</code> e notifica o Game Server via socket GM.
                            </p>
                        </div>

                        <form id="form-recharge" onsubmit="submitRecharge(event)" class="space-y-5">
                            <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrfToken) ?>">
                            <div>
                                <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">ID do Personagem Alvo</label>
                                <input type="number" name="character_id" id="recharge-char-id" required placeholder="Ex: 10001" 
                                    class="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/80 rounded-xl text-sm font-mono text-white focus:outline-none focus:border-blue-500 transition">
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Quantidade de Diamantes</label>
                                <input type="number" name="amount" required min="1" max="2000000000" value="1000" 
                                    class="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/80 rounded-xl text-sm font-mono text-amber-300 focus:outline-none focus:border-blue-500 transition">
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Referência / Motivo do Crédito</label>
                                <input type="text" name="ref" value="Painel GM Manual" 
                                    class="w-full px-4 py-2.5 bg-slate-900/80 border border-slate-700/80 rounded-xl text-sm text-white focus:outline-none focus:border-blue-500 transition">
                            </div>
                            <div class="pt-3">
                                <button type="submit" class="w-full py-3 bg-amber-600 hover:bg-amber-500 text-white rounded-xl font-bold text-sm shadow-lg shadow-amber-600/30 transition flex items-center justify-center gap-2">
                                    <i data-lucide="credit-card" class="w-4 h-4"></i>
                                    <span>Efetuar Crédito de Diamantes</span>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- TAB: LOGS -->
                <div id="tab-logs" class="tab-content hidden space-y-6">
                    <div class="glass-panel rounded-2xl overflow-hidden">
                        <div class="p-5 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <div class="flex items-center gap-3">
                                <button onclick="loadLogs('login')" id="btn-log-login" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 text-white transition">Logins Recentes</button>
                                <button onclick="loadLogs('recharge')" id="btn-log-recharge" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition">Histórico Recargas</button>
                                <button onclick="loadLogs('items')" id="btn-log-items" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition">Itens / Ações</button>
                            </div>
                            <span class="text-xs text-slate-500 font-mono" id="logs-count-info">Mostrando registros mais recentes</span>
                        </div>
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-xs">
                                <thead class="bg-slate-900/60 text-slate-400 uppercase font-semibold border-b border-slate-800" id="logs-table-head">
                                    <!-- Dynamic header -->
                                </thead>
                                <tbody id="logs-table-body" class="divide-y divide-slate-800/50 text-slate-300 font-mono">
                                    <tr><td class="p-6 text-center text-slate-500">Carregando registros...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

            </div>
        </main>
    </div>

    <!-- MODAL DETALHES DO PERSONAGEM -->
    <div id="char-modal" class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm hidden flex items-center justify-center p-4 overflow-y-auto">
        <div class="glass-panel bg-slate-900 border border-slate-700/80 w-full max-w-4xl rounded-2xl overflow-hidden shadow-2xl my-8">
            <div class="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white">
                        <i data-lucide="user" class="w-4 h-4"></i>
                    </div>
                    <div>
                        <h3 id="modal-char-name" class="text-base font-bold text-white">Detalhes do Herói</h3>
                        <p id="modal-char-sub" class="text-xs text-slate-400">ID: -- | Conta: --</p>
                    </div>
                </div>
                <button onclick="closeCharModal()" class="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition">
                    <i data-lucide="x" class="w-5 h-5"></i>
                </button>
            </div>

            <div class="p-6 space-y-6 max-h-[75vh] overflow-y-auto custom-scroll">
                <!-- Ações Rápidas de GM -->
                <div class="flex flex-wrap items-center gap-3 p-3.5 bg-slate-950/60 rounded-xl border border-slate-800">
                    <button onclick="quickKickChar()" class="px-3 py-1.5 bg-amber-600/20 hover:bg-amber-600/30 text-amber-400 border border-amber-600/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition">
                        <i data-lucide="user-x" class="w-3.5 h-3.5"></i> Desconectar (Kick)
                    </button>
                    <button onclick="quickAddVipModal()" class="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/30 text-purple-400 border border-purple-600/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition">
                        <i data-lucide="crown" class="w-3.5 h-3.5"></i> Conceder VIP
                    </button>
                    <button onclick="quickMailChar()" class="px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-600/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition">
                        <i data-lucide="send" class="w-3.5 h-3.5"></i> Enviar Item/Correio
                    </button>
                    <button onclick="quickDeleteChar()" class="px-3 py-1.5 bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-600/40 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ml-auto">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Excluir Personagem
                    </button>
                </div>

                <!-- Formulário de Edição de Atributos -->
                <form id="form-edit-char" onsubmit="saveCharEdit(event)" class="space-y-4">
                    <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrfToken) ?>">
                    <input type="hidden" name="character_id" id="edit-char-id">

                    <h4 class="text-xs font-bold text-slate-300 uppercase tracking-wider">Atributos Principais</h4>
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        <div>
                            <label class="text-xs text-slate-400 mb-1 block">Nível (Grade)</label>
                            <input type="number" name="grades" id="edit-grades" min="1" max="100" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm font-mono text-white focus:outline-none focus:border-blue-500">
                        </div>
                        <div>
                            <label class="text-xs text-slate-400 mb-1 block">Ouro</label>
                            <input type="number" name="gold" id="edit-gold" min="0" max="2000000000" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm font-mono text-amber-300 focus:outline-none focus:border-blue-500">
                        </div>
                        <div>
                            <label class="text-xs text-slate-400 mb-1 block">Diamantes</label>
                            <input type="number" name="point" id="edit-point" min="0" max="2000000000" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm font-mono text-cyan-300 focus:outline-none focus:border-blue-500">
                        </div>
                        <div>
                            <label class="text-xs text-slate-400 mb-1 block">Diamantes Vinc.</label>
                            <input type="number" name="gift_token" id="edit-gift" min="0" max="2000000000" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm font-mono text-purple-300 focus:outline-none focus:border-blue-500">
                        </div>
                    </div>

                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                        <div>
                            <label class="text-xs text-slate-400 mb-1 block">Cristais de Alma</label>
                            <input type="number" name="strategy" id="edit-strategy" min="0" max="2000000000" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm font-mono text-white focus:outline-none focus:border-blue-500">
                        </div>
                        <div>
                            <label class="text-xs text-slate-400 mb-1 block">Kyanite (Crystals)</label>
                            <input type="number" name="crystal" id="edit-crystal" min="0" max="2000000000" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm font-mono text-white focus:outline-none focus:border-blue-500">
                        </div>
                        <div>
                            <label class="text-xs text-slate-400 mb-1 block">Experiência</label>
                            <input type="number" name="gp" id="edit-gp" min="0" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm font-mono text-white focus:outline-none focus:border-blue-500">
                        </div>
                        <div>
                            <label class="text-xs text-slate-400 mb-1 block">Poder (Fight Capacity)</label>
                            <input type="number" name="fight_capacity" id="edit-fc" min="0" class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-sm font-mono text-rose-300 focus:outline-none focus:border-blue-500">
                        </div>
                    </div>

                    <div class="flex justify-end pt-2">
                        <button type="submit" class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-md shadow-blue-600/30">
                            <i data-lucide="save" class="w-3.5 h-3.5"></i> Salvar Alterações
                        </button>
                    </div>
                </form>

                <!-- Inventário Atual -->
                <div class="border-t border-slate-800 pt-5">
                    <h4 class="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <i data-lucide="backpack" class="w-4 h-4 text-emerald-400"></i>
                        Mochila & Equipamentos (<span id="modal-items-count">0</span> itens)
                    </h4>
                    <div id="modal-char-inventory" class="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2.5 max-h-56 overflow-y-auto custom-scroll p-1">
                        <!-- Itens carregados via JS -->
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- JAVASCRIPT LOGIC -->
    <script>
        const CSRF_TOKEN = '<?= htmlspecialchars($csrfToken) ?>';
        let currentTab = 'dashboard';
        let currentCharModalData = null;
        let mailSlotCount = 0;

        function renderIcons() {
            lucide.createIcons();
        }

        function showToast(message, type = 'success') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            const isSuccess = type === 'success';
            toast.className = `p-4 rounded-xl border flex items-center gap-3 shadow-2xl transition-all duration-300 pointer-events-auto transform translate-y-2 opacity-0 ` +
                (isSuccess ? 'bg-slate-900 border-emerald-500/40 text-emerald-300' : 'bg-slate-900 border-rose-500/40 text-rose-300');
            toast.innerHTML = `
                <i data-lucide="${isSuccess ? 'check-circle' : 'alert-circle'}" class="w-5 h-5 shrink-0"></i>
                <span class="text-xs font-semibold text-slate-200">${message}</span>
            `;
            container.appendChild(toast);
            lucide.createIcons();
            setTimeout(() => {
                toast.classList.remove('translate-y-2', 'opacity-0');
            }, 10);
            setTimeout(() => {
                toast.classList.add('opacity-0', 'translate-x-full');
                setTimeout(() => toast.remove(), 300);
            }, 4000);
        }

        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.nav-item').forEach(el => {
                el.classList.remove('text-white', 'bg-blue-600', 'shadow-md', 'shadow-blue-600/20');
                el.classList.add('text-slate-400');
            });

            const activeNav = document.getElementById('nav-' + tab);
            if (activeNav) {
                activeNav.classList.remove('text-slate-400');
                activeNav.classList.add('text-white', 'bg-blue-600', 'shadow-md', 'shadow-blue-600/20');
            }

            const targetTab = document.getElementById('tab-' + tab);
            if (targetTab) targetTab.classList.remove('hidden');

            const titleMap = {
                dashboard: 'Visão Geral do Servidor',
                players: 'Gestão de Jogadores & Contas',
                mail: 'Correio & Envio de Itens (Broadcast)',
                recharge: 'Recarga Manual de Diamantes',
                logs: 'Logs do Sistema & Auditoria'
            };
            document.getElementById('page-title').innerText = titleMap[tab] || 'Painel GM';

            refreshCurrentTab();
            renderIcons();
        }

        function refreshCurrentTab() {
            const spin = document.getElementById('refresh-icon');
            if (spin) spin.classList.add('animate-spin');

            if (currentTab === 'dashboard') {
                loadDashboard();
            } else if (currentTab === 'logs') {
                loadLogs('login');
            }

            setTimeout(() => {
                if (spin) spin.classList.remove('animate-spin');
            }, 600);
        }

        // Load Dashboard
        async function loadDashboard() {
            try {
                const res = await fetch('admin.php?api=dashboard');
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                const d = json.data;

                document.getElementById('stat-accounts').innerText = Number(d.accounts_count).toLocaleString('pt-BR');
                document.getElementById('stat-chars').innerText = Number(d.characters_count).toLocaleString('pt-BR');
                document.getElementById('stat-diamonds').innerText = Number(d.totals.total_point || 0).toLocaleString('pt-BR');
                document.getElementById('stat-recharge').innerText = Number(d.total_recharge || 0).toLocaleString('pt-BR');
                
                document.getElementById('stat-gold').innerText = Number(d.totals.total_gold || 0).toLocaleString('pt-BR');
                document.getElementById('stat-gift').innerText = Number(d.totals.total_gift || 0).toLocaleString('pt-BR');
                document.getElementById('stat-strategy').innerText = Number(d.totals.total_strategy || 0).toLocaleString('pt-BR');

                // Render recent characters
                const tbody = document.getElementById('dashboard-recent-chars');
                if (d.recent_characters && d.recent_characters.length > 0) {
                    tbody.innerHTML = d.recent_characters.map(c => `
                        <tr class="hover:bg-slate-800/40 transition cursor-pointer" onclick="openCharModal(${c.id})">
                            <td class="p-3.5 pl-6 font-semibold text-white flex items-center gap-2">
                                <div class="w-6 h-6 rounded bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] text-blue-400 font-bold">
                                    ${c.job || 'H'}
                                </div>
                                <span>${c.nickname}</span>
                                <span class="text-[10px] text-slate-500 font-mono">#${c.id}</span>
                            </td>
                            <td class="p-3.5 text-slate-400">${c.account_name}</td>
                            <td class="p-3.5 font-mono text-emerald-400 font-bold">Nv. ${c.grades}</td>
                            <td class="p-3.5 text-slate-300">${getCareerName(c.job)}</td>
                            <td class="p-3.5 font-mono text-amber-300">${Number(c.gold).toLocaleString('pt-BR')}</td>
                            <td class="p-3.5 font-mono text-cyan-300 font-bold">${Number(c.point).toLocaleString('pt-BR')}</td>
                            <td class="p-3.5 pr-6 text-right">
                                <button class="p-1.5 hover:bg-slate-700 rounded-lg text-blue-400 transition">
                                    <i data-lucide="chevron-right" class="w-4 h-4"></i>
                                </button>
                            </td>
                        </tr>
                    `).join('');
                } else {
                    tbody.innerHTML = '<tr><td colspan="7" class="p-6 text-center text-slate-500">Nenhum personagem registrado ainda.</td></tr>';
                }
                renderIcons();
            } catch (err) {
                console.error(err);
                showToast('Falha ao carregar dashboard: ' + err.message, 'error');
            }
        }

        function getCareerName(j) {
            const map = { 1: 'Guerreiro', 2: 'Mago', 3: 'Arqueiro' };
            return map[j] || 'Guerreiro';
        }

        // Search Players
        function handlePlayerSearch(e) {
            if (e.key === 'Enter') searchPlayers();
        }

        async function searchPlayers() {
            const q = document.getElementById('player-search-input').value.trim();
            if (!q) return;

            try {
                const res = await fetch('admin.php?api=search&q=' + encodeURIComponent(q));
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                const d = json.data;

                // Render characters
                const charList = document.getElementById('char-search-list');
                if (d.characters && d.characters.length > 0) {
                    charList.innerHTML = d.characters.map(c => `
                        <div onclick="openCharModal(${c.id})" class="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-blue-500/50 hover:bg-slate-800/50 transition cursor-pointer flex items-center justify-between">
                            <div class="flex items-center gap-3">
                                <div class="w-9 h-9 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center font-bold text-xs">
                                    ${c.job || 'H'}
                                </div>
                                <div>
                                    <h5 class="text-sm font-bold text-white flex items-center gap-2">
                                        ${c.nickname}
                                        <span class="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded font-mono">Nv. ${c.grades}</span>
                                    </h5>
                                    <p class="text-xs text-slate-400">ID: ${c.id} | Conta: ${c.account_name}</p>
                                </div>
                            </div>
                            <div class="text-right">
                                <p class="text-xs font-mono text-cyan-300 font-bold">${Number(c.point).toLocaleString()} 💎</p>
                                <p class="text-[10px] text-slate-500 font-mono">Poder: ${Number(c.fighting_capacity || 0).toLocaleString()}</p>
                            </div>
                        </div>
                    `).join('');
                } else {
                    charList.innerHTML = '<p class="text-xs text-slate-500 text-center py-6">Nenhum personagem correspondente.</p>';
                }

                // Render accounts
                const accList = document.getElementById('account-search-list');
                if (d.accounts && d.accounts.length > 0) {
                    accList.innerHTML = d.accounts.map(a => `
                        <div class="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
                            <div class="flex items-center gap-3">
                                <div class="w-9 h-9 rounded-lg bg-slate-800 text-slate-300 flex items-center justify-center font-bold text-xs">
                                    #${a.id}
                                </div>
                                <div>
                                    <h5 class="text-sm font-bold text-white flex items-center gap-2">
                                        ${a.username}
                                        ${a.is_banned ? '<span class="text-[10px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded">BANIDO</span>' : ''}
                                    </h5>
                                    <p class="text-xs text-slate-500 font-mono">Criado em ${a.created_at || '--'}</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2">
                                <button onclick="toggleAccountBan(${a.id}, ${a.is_banned ? 0 : 1})" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold ${a.is_banned ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30' : 'bg-red-600/20 text-red-400 border border-red-500/30'} transition">
                                    ${a.is_banned ? 'Desbanir' : 'Banir'}
                                </button>
                            </div>
                        </div>
                    `).join('');
                } else {
                    accList.innerHTML = '<p class="text-xs text-slate-500 text-center py-6">Nenhuma conta correspondente.</p>';
                }
                renderIcons();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        // Open Character Detail Modal
        async function openCharModal(charId) {
            try {
                const res = await fetch('admin.php?api=character&id=' + charId);
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                const c = json.data.character;
                currentCharModalData = json.data;

                document.getElementById('modal-char-name').innerText = c.nickname + ' (Nv. ' + c.grades + ')';
                document.getElementById('modal-char-sub').innerText = `ID: ${c.id} | Conta: ${c.account_name} (#${c.account_id}) | VIP Nv: ${json.data.vip.grade || 0}`;
                document.getElementById('edit-char-id').value = c.id;

                document.getElementById('edit-grades').value = c.grades;
                document.getElementById('edit-gold').value = c.gold;
                document.getElementById('edit-point').value = c.point;
                document.getElementById('edit-gift').value = c.gift_token;
                document.getElementById('edit-strategy').value = c.strategy;
                document.getElementById('edit-crystal').value = c.crystals || 0;
                document.getElementById('edit-gp').value = c.gp;
                document.getElementById('edit-fc').value = c.fighting_capacity || 0;

                // Inventory
                const inv = json.data.inventory || [];
                document.getElementById('modal-items-count').innerText = inv.length;
                const invContainer = document.getElementById('modal-char-inventory');
                if (inv.length > 0) {
                    invContainer.innerHTML = inv.map(i => `
                        <div class="p-2 rounded-lg bg-slate-950 border border-slate-800 flex items-center gap-2" title="${i.name} (Qtd: ${i.count})">
                            <img src="https://wartune-cdn.thnsdu.easypanel.host/icon/${i.icon}.png" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'24\\' height=\\'24\\'><rect width=\\'24\\' height=\\'24\\' fill=\\'%23334155\\'/></svg>'" class="w-8 h-8 rounded border border-slate-700 object-contain shrink-0">
                            <div class="min-w-0 truncate">
                                <p class="text-xs font-semibold text-slate-200 truncate">${i.name}</p>
                                <p class="text-[10px] text-slate-400 font-mono">x${i.count}</p>
                            </div>
                        </div>
                    `).join('');
                } else {
                    invContainer.innerHTML = '<p class="text-xs text-slate-500 col-span-full py-4 text-center">Mochila vazia.</p>';
                }

                document.getElementById('char-modal').classList.remove('hidden');
                renderIcons();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        function closeCharModal() {
            document.getElementById('char-modal').classList.add('hidden');
            currentCharModalData = null;
        }

        // Save Character Edit
        async function saveCharEdit(e) {
            e.preventDefault();
            const form = document.getElementById('form-edit-char');
            const data = new FormData(form);

            try {
                const res = await fetch('admin.php?api=character_edit', { method: 'POST', body: data });
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                showToast('Personagem salvo com sucesso!');
                closeCharModal();
                refreshCurrentTab();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        // Quick GM Actions
        async function quickKickChar() {
            if (!currentCharModalData) return;
            const cid = currentCharModalData.character.id;
            if (!confirm(`Deseja derrubar a conexão do jogador #${cid} imediatamente?`)) return;

            const fd = new FormData();
            fd.append('character_id', cid);
            fd.append('csrf_token', CSRF_TOKEN);

            try {
                const res = await fetch('admin.php?api=character_kick', { method: 'POST', body: fd });
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                showToast('Comando de desconexão enviado com sucesso!');
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        async function quickAddVipModal() {
            if (!currentCharModalData) return;
            const days = prompt('Quantos dias de VIP deseja conceder?', '30');
            if (!days || isNaN(days)) return;
            const grade = prompt('Qual nível de VIP (1 a 10)?', '10');
            if (!grade || isNaN(grade)) return;

            const fd = new FormData();
            fd.append('character_id', currentCharModalData.character.id);
            fd.append('days', days);
            fd.append('grade', grade);
            fd.append('csrf_token', CSRF_TOKEN);

            try {
                const res = await fetch('admin.php?api=character_vip', { method: 'POST', body: fd });
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                showToast(`VIP concedido por ${days} dias (Nível ${grade})!`);
                closeCharModal();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        function quickMailChar() {
            if (!currentCharModalData) return;
            const cid = currentCharModalData.character.id;
            closeCharModal();
            switchTab('mail');
            document.getElementById('mail-receiver-input').value = cid;
        }

        async function quickDeleteChar() {
            if (!currentCharModalData) return;
            const c = currentCharModalData.character;
            const confirmNick = prompt(`ATENÇÃO: Operação irreversível!\nDigite o nickname exato [${c.nickname}] para confirmar a exclusão:`);
            if (confirmNick !== c.nickname) {
                showToast('Confirmação inválida. Exclusão cancelada.', 'error');
                return;
            }

            const fd = new FormData();
            fd.append('character_id', c.id);
            fd.append('confirm', confirmNick);
            fd.append('csrf_token', CSRF_TOKEN);

            try {
                const res = await fetch('admin.php?api=character_reset', { method: 'POST', body: fd });
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                showToast('Personagem apagado permanentemente!');
                closeCharModal();
                refreshCurrentTab();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        async function toggleAccountBan(accId, banned) {
            const fd = new FormData();
            fd.append('account_id', accId);
            fd.append('banned', banned ? '1' : '0');
            fd.append('csrf_token', CSRF_TOKEN);

            try {
                const res = await fetch('admin.php?api=account_ban', { method: 'POST', body: fd });
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                showToast(banned ? 'Conta banida!' : 'Conta desbanida!');
                searchPlayers();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        // Mail & Items logic
        function toggleTargetType(val) {
            const targetContainer = document.getElementById('container-char-target');
            if (val === 'all') {
                targetContainer.classList.add('opacity-40', 'pointer-events-none');
            } else {
                targetContainer.classList.remove('opacity-40', 'pointer-events-none');
            }
        }

        function addMailItemSlot() {
            if (mailSlotCount >= 4) {
                showToast('Máximo de 4 slots de itens por envio atingido.', 'error');
                return;
            }
            mailSlotCount++;
            const id = mailSlotCount;
            const container = document.getElementById('mail-items-container');

            const slotEl = document.createElement('div');
            slotEl.id = 'mail-slot-' + id;
            slotEl.className = 'p-3 bg-slate-900/60 border border-slate-700/80 rounded-xl relative space-y-2';
            slotEl.innerHTML = `
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold text-slate-400 uppercase">Slot #${id}</span>
                    <button type="button" onclick="removeMailItemSlot(${id})" class="text-slate-500 hover:text-red-400 text-xs transition">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                    </button>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div class="sm:col-span-2 relative">
                        <input type="text" placeholder="Buscar item (ex: Poção, Caixa, Fragmento...)" 
                            id="search-slot-${id}" autocomplete="off"
                            oninput="handleItemAutocomplete(${id}, this.value)"
                            class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs text-white focus:outline-none focus:border-blue-500">
                        <input type="hidden" name="items[${id}][template_id]" id="template-slot-${id}">
                        <!-- Dropdown de Autocomplete -->
                        <div id="dropdown-slot-${id}" class="absolute left-0 right-0 top-full mt-1 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-30 max-h-48 overflow-y-auto hidden custom-scroll divide-y divide-slate-800"></div>
                    </div>
                    <div>
                        <input type="number" name="items[${id}][count]" value="1" min="1" max="99999" 
                            class="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-xs font-mono text-white focus:outline-none focus:border-blue-500" placeholder="Qtd">
                    </div>
                </div>
                <div id="preview-slot-${id}" class="text-[11px] text-slate-400 flex items-center gap-2 hidden pt-1">
                    <img id="icon-slot-${id}" class="w-6 h-6 rounded border border-slate-700 object-contain">
                    <span id="name-slot-${id}" class="font-medium text-emerald-300"></span>
                </div>
            `;
            container.appendChild(slotEl);
            renderIcons();
        }

        function removeMailItemSlot(id) {
            const el = document.getElementById('mail-slot-' + id);
            if (el) el.remove();
            mailSlotCount--;
        }

        let debounceTimers = {};
        function handleItemAutocomplete(slotId, query) {
            clearTimeout(debounceTimers[slotId]);
            const dropdown = document.getElementById('dropdown-slot-' + slotId);
            if (!query || query.length < 2) {
                dropdown.classList.add('hidden');
                return;
            }

            debounceTimers[slotId] = setTimeout(async () => {
                try {
                    const res = await fetch('admin.php?api=search_items&q=' + encodeURIComponent(query));
                    const json = await res.json();
                    if (!json.ok) return;

                    const items = json.data;
                    if (items.length === 0) {
                        dropdown.innerHTML = '<div class="p-3 text-xs text-slate-500 text-center">Nenhum item encontrado.</div>';
                    } else {
                        dropdown.innerHTML = items.map(it => `
                            <div class="p-2 hover:bg-slate-800 cursor-pointer flex items-center gap-2.5 transition"
                                onclick="selectMailItem(${slotId}, ${it.id}, '${escapeJs(it.name)}', '${it.icon}')">
                                <img src="https://wartune-cdn.thnsdu.easypanel.host/icon/${it.icon}.png" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'20\\' height=\\'20\\'><rect width=\\'20\\' height=\\'20\\' fill=\\'%23334155\\'/></svg>'" class="w-6 h-6 rounded border border-slate-700 object-contain">
                                <div class="min-w-0 truncate">
                                    <p class="text-xs font-semibold text-slate-200 truncate">${it.name}</p>
                                    <p class="text-[10px] text-slate-500 font-mono">ID: ${it.id}</p>
                                </div>
                            </div>
                        `).join('');
                    }
                    dropdown.classList.remove('hidden');
                } catch (e) {
                    console.error(e);
                }
            }, 250);
        }

        function escapeJs(str) {
            return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        }

        function selectMailItem(slotId, templateId, name, icon) {
            document.getElementById('template-slot-' + slotId).value = templateId;
            document.getElementById('search-slot-' + slotId).value = name;
            document.getElementById('dropdown-slot-' + slotId).classList.add('hidden');

            const preview = document.getElementById('preview-slot-' + slotId);
            const iconEl = document.getElementById('icon-slot-' + slotId);
            const nameEl = document.getElementById('name-slot-' + slotId);

            iconEl.src = `https://wartune-cdn.thnsdu.easypanel.host/icon/${icon}.png`;
            nameEl.innerText = `${name} (ID: ${templateId})`;
            preview.classList.remove('hidden');
        }

        async function submitSendMail(e) {
            e.preventDefault();
            const form = document.getElementById('form-send-mail');
            const data = new FormData(form);

            try {
                const res = await fetch('admin.php?api=send_mail', { method: 'POST', body: data });
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                showToast(`Correio enviado com sucesso para ${json.data.sent_count} jogador(es)!`);
                form.reset();
                document.getElementById('mail-items-container').innerHTML = '';
                mailSlotCount = 0;
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        // Recharge Submit
        async function submitRecharge(e) {
            e.preventDefault();
            const form = document.getElementById('form-recharge');
            const data = new FormData(form);

            try {
                const res = await fetch('admin.php?api=recharge', { method: 'POST', body: data });
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                showToast(`Recarga de ${data.get('amount')} diamantes efetuada! Novo saldo: ${json.data.new_point}`);
                form.reset();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }

        // Logs
        async function loadLogs(type) {
            document.querySelectorAll('#btn-log-login, #btn-log-recharge, #btn-log-items').forEach(b => {
                b.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-400 hover:text-white transition';
            });
            const activeBtn = document.getElementById('btn-log-' + type);
            if (activeBtn) activeBtn.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 text-white transition';

            const thead = document.getElementById('logs-table-head');
            const tbody = document.getElementById('logs-table-body');
            tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-slate-500">Carregando registros...</td></tr>';

            try {
                const res = await fetch(`admin.php?api=logs&type=${type}`);
                const json = await res.json();
                if (!json.ok) throw new Error(json.error);
                const logs = json.data;

                if (type === 'login') {
                    thead.innerHTML = `
                        <tr>
                            <th class="p-3.5 pl-6">Data/Hora</th>
                            <th class="p-3.5">Conta</th>
                            <th class="p-3.5">Personagem</th>
                            <th class="p-3.5">IP de Origem</th>
                            <th class="p-3.5 pr-6">Status</th>
                        </tr>
                    `;
                    tbody.innerHTML = logs.map(l => `
                        <tr class="hover:bg-slate-800/30">
                            <td class="p-3.5 pl-6 text-slate-400">${l.created_at || '--'}</td>
                            <td class="p-3.5 font-bold text-white">${l.username || '--'}</td>
                            <td class="p-3.5 text-slate-300">${l.nickname || '--'}</td>
                            <td class="p-3.5 text-cyan-400">${l.ip_address || '--'}</td>
                            <td class="p-3.5 pr-6"><span class="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded text-[11px]">Sucesso</span></td>
                        </tr>
                    `).join('');
                } else if (type === 'recharge') {
                    thead.innerHTML = `
                        <tr>
                            <th class="p-3.5 pl-6">Data</th>
                            <th class="p-3.5">Personagem</th>
                            <th class="p-3.5">Conta</th>
                            <th class="p-3.5">Qtd Diamantes</th>
                            <th class="p-3.5 pr-6">Referência</th>
                        </tr>
                    `;
                    tbody.innerHTML = logs.map(l => `
                        <tr class="hover:bg-slate-800/30">
                            <td class="p-3.5 pl-6 text-slate-400">${l.created_at || '--'}</td>
                            <td class="p-3.5 font-bold text-white">${l.nickname || '#' + l.character_id}</td>
                            <td class="p-3.5 text-slate-400">${l.username || '--'}</td>
                            <td class="p-3.5 text-amber-400 font-bold">+${Number(l.delta_point).toLocaleString()} 💎</td>
                            <td class="p-3.5 pr-6 text-slate-400">${l.ref_type || '--'}</td>
                        </tr>
                    `).join('');
                } else if (type === 'items') {
                    thead.innerHTML = `
                        <tr>
                            <th class="p-3.5 pl-6">ID</th>
                            <th class="p-3.5">Item</th>
                            <th class="p-3.5">Dono (Char ID)</th>
                            <th class="p-3.5">Qtd</th>
                            <th class="p-3.5 pr-6">Data</th>
                        </tr>
                    `;
                    tbody.innerHTML = logs.map(l => `
                        <tr class="hover:bg-slate-800/30">
                            <td class="p-3.5 pl-6 text-slate-500">#${l.id}</td>
                            <td class="p-3.5 font-bold text-white">${l.name || 'Template #' + l.template_id}</td>
                            <td class="p-3.5 text-cyan-400">#${l.character_id}</td>
                            <td class="p-3.5 text-slate-300">${l.count}</td>
                            <td class="p-3.5 pr-6 text-slate-400">${l.created_at || '--'}</td>
                        </tr>
                    `).join('');
                }
            } catch (err) {
                tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-rose-400">${err.message}</td></tr>`;
            }
        }

        // On Load
        document.addEventListener('DOMContentLoaded', () => {
            renderIcons();
            loadDashboard();
            addMailItemSlot();
        });
    </script>
</body>
</html>
