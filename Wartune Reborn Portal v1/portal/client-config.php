<?php
declare(strict_types=1);
require __DIR__ . '/src/bootstrap.php';

// config.xml que o Loading.swf baixa (flashvar "config"). Público: não tem segredo, só endereços
// e a chave pública do login.
$server = (new GameServers(db()))->get((int) ($_GET['server'] ?? 0));
if (!$server || $server['rsa_modulus'] === '') {
    http_response_code(404);
    exit;
}

$template = file_get_contents(__DIR__ . '/templates/config.xml');
$template = preg_replace('/^\xEF\xBB\xBF/', '', $template); // BOM
header('Content-Type: text/xml; charset=utf-8');
header('Cache-Control: no-cache');
echo (new ClientConfig($template, $CONFIG['cdn_url'], $CONFIG['game_url']))->render($server);
