<?php
declare(strict_types=1);

require __DIR__ . '/Database.php';
require __DIR__ . '/Accounts.php';
require __DIR__ . '/GameServers.php';
require __DIR__ . '/Tickets.php';
require __DIR__ . '/ClientConfig.php';

/** @var array<string, mixed> $CONFIG */
$CONFIG = require __DIR__ . '/../config.php';

session_set_cookie_params(['httponly' => true, 'samesite' => 'Lax']);
session_start();

function h(?string $value): string
{
    return htmlspecialchars((string) $value, ENT_QUOTES, 'UTF-8');
}

function redirect(string $to): never
{
    header('Location: ' . $to);
    exit;
}

function csrf_token(): string
{
    return $_SESSION['csrf'] ??= bin2hex(random_bytes(16));
}

function csrf_check(): void
{
    if (!hash_equals(csrf_token(), (string) ($_POST['csrf'] ?? ''))) {
        http_response_code(400);
        exit('Formulário expirado. Volte e tente de novo.');
    }
}

function db(): Database
{
    global $CONFIG;
    static $db = null;
    return $db ??= new Database($CONFIG['db']['dsn'], $CONFIG['db']['user'], $CONFIG['db']['password']);
}

/**
 * Conta da sessão, conferida no banco a cada página: banco recriado ou conta bloqueada derruba a sessão
 * (senão o ticket sai para uma conta que não existe mais e o INSERT falha na chave estrangeira).
 *
 * @return array{id:int, username:string}|null
 */
function current_account(): ?array
{
    $account = $_SESSION['account'] ?? null;
    if ($account === null) {
        return null;
    }
    $row = db()->one('SELECT id, username FROM accounts WHERE id = ? AND banned = FALSE', [$account['id']]);
    if (!$row || $row['username'] !== $account['username']) {
        unset($_SESSION['account']);
        return null;
    }
    return $account;
}
