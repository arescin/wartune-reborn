<?php
declare(strict_types=1);
require __DIR__ . '/src/bootstrap.php';

$error = null;
$tab = $_POST['action'] ?? 'login';

try {
    db();
} catch (PDOException $e) {
    http_response_code(503);
    exit('Banco indisponível. Suba o servidor do jogo uma vez (uv run wartune-server run) para criar as tabelas.');
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    $accounts = new Accounts(db());
    $username = trim((string) ($_POST['username'] ?? ''));
    $password = (string) ($_POST['password'] ?? '');
    try {
        $account = $tab === 'register'
            ? $accounts->register($username, $password)
            : $accounts->authenticate($username, $password);
        session_regenerate_id(true);
        $_SESSION['account'] = $account;
        redirect('./');
    } catch (AccountError $e) {
        $error = $e->getMessage();
    }
}

$account = current_account();
$servers = [];
$characters = [];
if ($account) {
    $repo = new GameServers(db());
    $servers = $repo->all();
    $characters = $repo->charactersOf($account['id']);
}
?>
<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= h($CONFIG['site_name']) ?></title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
<main class="panel">
    <h1><?= h($CONFIG['site_name']) ?></h1>

<?php if (!$account): ?>
    <form method="post" class="card">
        <input type="hidden" name="csrf" value="<?= h(csrf_token()) ?>">
        <label for="u">Usuário</label>
        <input id="u" name="username" autocomplete="username" required value="<?= h($_POST['username'] ?? '') ?>">
        <label for="p">Senha</label>
        <input id="p" name="password" type="password" autocomplete="current-password" required>
        <div class="actions">
            <button name="action" value="login">Entrar</button>
            <button name="action" value="register" class="secondary">Criar conta</button>
        </div>
        <?php if ($error): ?><p class="error"><?= h($error) ?></p><?php endif ?>
    </form>
<?php else: ?>
    <p class="muted">Conectado como <b><?= h($account['username']) ?></b> · <a href="logout.php">sair</a><?php
        $isGm = in_array(strtolower($account['username']), array_unique(array_merge(['admin', 'arescin', 'arescinbr'], array_map('strtolower', $CONFIG['gm_users'] ?? []))), true);
        if ($isGm): ?> · <a href="admin.php" style="font-weight: bold; color: #38bdf8;">painel GM</a><?php endif ?></p>
    <h2>Escolha o servidor</h2>
    <?php if (!$servers): ?>
        <p class="error">Nenhum servidor publicado ainda. Suba o servidor do jogo.</p>
    <?php endif ?>
    <ul class="servers">
    <?php foreach ($servers as $server):
        $online = GameServers::isOnline($server);
        $char = $characters[$server['id']] ?? null; ?>
        <li class="card server <?= $online ? '' : 'off' ?>">
            <div>
                <b><?= h($server['name']) ?></b>
                <span class="badge"><?= $online ? 'online' : 'offline' ?></span>
                <div class="muted">
                    <?= $char ? h($char['nickname']) . ' · nível ' . (int) $char['grades'] : 'sem personagem ainda' ?>
                </div>
                <div class="muted"><?= h(GameServers::clock($server)) ?></div>
            </div>
            <?php if ($online): ?>
                <a class="button" href="play.php?server=<?= (int) $server['id'] ?>">Jogar</a>
            <?php endif ?>
        </li>
    <?php endforeach ?>
    </ul>
<?php endif ?>
</main>
</body>
</html>
