<?php
// Configuração do portal. Endereço, portas e chave RSA de cada servidor de jogo NÃO ficam aqui:
// vêm da tabela game_servers, que cada processo do servidor (Python) preenche ao iniciar.

$dbDsn = getenv('WARTUNE_DB_DSN') ?: getenv('DB_DSN') ?: 'sqlite:' . __DIR__ . '/../../wartune-reborne-emulator/data/wartune.db';
$dbUser = getenv('WARTUNE_DB_USER') ?: getenv('DB_USER') ?: null;
$dbPass = getenv('WARTUNE_DB_PASS') ?: getenv('DB_PASSWORD') ?: null;

$portalUrl = getenv('WARTUNE_PORTAL_URL') ?: getenv('PORTAL_URL') ?: 'http://127.0.0.1:8090/wartune-reborn/portal/';
$cdnUrl = getenv('WARTUNE_CDN_URL') ?: getenv('CDN_URL') ?: 'http://127.0.0.1:8090/wartune-reborn/cdn/';
$gameUrl = getenv('WARTUNE_GAME_URL') ?: getenv('GAME_URL') ?: 'http://127.0.0.1:8090/wartune-reborn/game/';
$serverHttpUrl = getenv('WARTUNE_SERVER_HTTP_URL') ?: '';

$ticketTtl = (int) (getenv('WARTUNE_TICKET_TTL') ?: 300);
$gmSecret = getenv('WARTUNE_GM_SECRET') ?: '';
$gmUsersEnv = getenv('WARTUNE_GM_USERS');
$gmUsers = ($gmUsersEnv !== false && $gmUsersEnv !== '') ? array_map('trim', explode(',', $gmUsersEnv)) : ['admin', 'Arescin', 'ArescinBR'];

return [
    // Mesmo banco do servidor do jogo (WARTUNE_DATABASE_URL). Exemplos:
    //   'sqlite:/data/wartune.db'
    //   'pgsql:host=wartune-db;port=5432;dbname=wartune'
    //   'mysql:host=wartune-db;port=3306;dbname=wartune;charset=utf8mb4'
    'db' => [
        'dsn' => $dbDsn,
        'user' => $dbUser,
        'password' => $dbPass,
    ],

    // URLs públicas (com barra no fim)
    'portal_url' => rtrim($portalUrl, '/') . '/',
    'cdn_url' => rtrim($cdnUrl, '/') . '/',
    // Site do servidor de jogo (o s134 oficial): client/Loading.swf, client/resouececheck.sq e xml/tempinfos.xml
    'game_url' => rtrim($gameUrl, '/') . '/',
    'server_http_url' => rtrim($serverHttpUrl, '/'),

    // Validade do ticket de entrada (segundos): o Loading.swf precisa fazer o login HTTP nesse prazo
    'ticket_ttl' => $ticketTtl,

    // Painel GM (admin.php): usuários do portal com acesso e o mesmo segredo do WARTUNE_GM_SECRET
    // do servidor (usado no POST /gm/kick e /gm/ban antes de editar ou banir)
    'gm_users' => $gmUsers,
    'gm_secret' => $gmSecret,

    'site_name' => getenv('WARTUNE_SITE_NAME') ?: 'Wartune Reborn',
    'ruffle_js' => getenv('WARTUNE_RUFFLE_JS') ?: 'https://unpkg.com/@ruffle-rs/ruffle@0.7.1/ruffle.js',
];
