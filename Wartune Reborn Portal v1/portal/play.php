<?php
declare(strict_types=1);
require __DIR__ . '/src/bootstrap.php';

$account = current_account() ?? redirect('./');
$server = (new GameServers(db()))->get((int) ($_GET['server'] ?? 0));
if (!$server || $server['rsa_modulus'] === '') {
    http_response_code(404);
    exit('Servidor não encontrado ou nunca iniciado.');
}

$ticket = (new Tickets(db(), (int) $CONFIG['ticket_ttl']))->issue($account['id'], (int) $server['id']);
$flashvars = [
    'user' => $account['username'],
    'key' => $ticket,
    'site' => $server['site'],
    'config' => $CONFIG['portal_url'] . 'client-config.php?server=' . (int) $server['id'],
    'playfb' => '0',
];
$loadingDir = $CONFIG['game_url'] . 'client/';
$swfUrl = $loadingDir . 'Loading.swf?' . http_build_query($flashvars, '', '&', PHP_QUERY_RFC3986);
$ruffle = [
    'url' => $loadingDir . 'Loading.swf',
    'base' => $loadingDir,
    'parameters' => $flashvars,
    'socket' => [
        'host' => $server['public_host'],
        'port' => (int) $server['socket_port'],
        // WARTUNE_WS_URL permite sobrescrever o proxy WebSocket via env (ex: wss://wartune-server.thnsdu.easypanel.host/ws)
        'proxy' => (int) $server['websocket_port']
            ? (getenv('WARTUNE_WS_URL') ?: sprintf('wss://%s:%d', $server['public_host'], $server['websocket_port']))
            : null,
    ],
];
?>
<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= h($server['name']) ?> · <?= h($CONFIG['site_name']) ?></title>
    <link rel="stylesheet" href="assets/style.css">
    <script src="<?= h($CONFIG['ruffle_js']) ?>"></script>
</head>
<body>
<main class="panel" id="panel">
    <p class="muted"><a href="./">← servidores</a></p>
    <h1><?= h($server['name']) ?></h1>
    <div class="card">
        <p><b>Flash Player projector</b>: File → Open e cole a URL (vale <?= (int) ($CONFIG['ticket_ttl'] / 60) ?> min):</p>
        <p><code id="swf"><?= h($swfUrl) ?></code></p>
        <div class="actions">
            <button type="button" id="copy">Copiar URL</button>
            <button type="button" id="ruffle" class="secondary"<?= $ruffle['socket']['proxy'] ? '' : ' disabled' ?>>Jogar no navegador (Ruffle)</button>
        </div>
    </div>
</main>
<div id="game"></div>
<script>
const game = <?= json_encode($ruffle, JSON_UNESCAPED_SLASHES) ?>;
document.getElementById("copy").onclick = () => navigator.clipboard.writeText(document.getElementById("swf").textContent);
document.getElementById("ruffle").onclick = () => {
    window.RufflePlayer = window.RufflePlayer || {};
    window.RufflePlayer.config = {
        maxExecutionDuration: 300, // o setup do core.swf passa dos 15s padrão
        socketProxy: [game.socket.host, "127.0.0.1", "localhost"].map(host => ({ host, port: game.socket.port, proxyUrl: game.socket.proxy })),
    };
    document.getElementById("panel").style.display = "none";
    const box = document.getElementById("game");
    box.style.display = "block";
    const player = window.RufflePlayer.newest().createPlayer();
    player.style.width = "100%";
    player.style.height = "100%";
    box.appendChild(player);
    // base: caminhos relativos do SWF (resouececheck.sq...) resolvem na pasta do Loading, não na página do portal
    player.ruffle().load({ url: game.url, base: game.base, parameters: game.parameters, allowScriptAccess: true });
};
</script>
</body>
</html>
