<?php
declare(strict_types=1);
require __DIR__ . '/src/bootstrap.php';
require __DIR__ . '/src/Admin.php';

$me = current_account();
if (!$me || !in_array($me['username'], $CONFIG['gm_users'] ?? [], true)) {
    http_response_code(403);
    exit('Acesso restrito a GMs.');
}
$admin = new Admin(db(), (string) ($CONFIG['gm_secret'] ?? ''), $me['username']);
$accountId = (int) ($_GET['account'] ?? $_POST['account'] ?? 0);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    $char = (int) ($_POST['character'] ?? 0);
    try {
        switch ($_POST['action'] ?? '') {
            case 'edit':
                // só o que o GM mudou: o resto pode ter andado no jogo depois que a página abriu
                $orig = is_array($_POST['orig'] ?? null) ? $_POST['orig'] : [];
                $changed = array_filter(
                    array_intersect_key($_POST, Admin::EDITABLE),
                    fn ($v, $col) => (string) ($orig[$col] ?? '') !== (is_array($v) ? '' : (string) $v),
                    ARRAY_FILTER_USE_BOTH
                );
                $admin->edit($char, $changed);
                $flash = 'Personagem atualizado.';
                break;
            case 'recharge':
                $admin->recharge($char, (string) ($_POST['amount'] ?? ''), trim((string) ($_POST['ref'] ?? '')));
                $flash = 'Recarga creditada.';
                break;
            case 'reset':
                $row = db()->one('SELECT nickname FROM characters WHERE id = ?', [$char]);
                if (!$row || trim((string) ($_POST['confirm'] ?? '')) !== (string) ($row['nickname'] ?? $char)) {
                    throw new AdminError('Confirmação não confere: digite o nick exato do personagem.');
                }
                $admin->reset($char);
                $flash = 'Personagem apagado.';
                break;
            case 'ban':
                $banned = ($_POST['banned'] ?? '') === '1';
                $warnings = $admin->ban($accountId, $banned);
                $flash = ($banned ? 'Conta banida.' : 'Conta desbanida.')
                    . ($warnings ? ' Avisos: ' . implode('; ', $warnings) : '');
                break;
            default:
                throw new AdminError('Ação desconhecida.');
        }
    } catch (AdminError | PDOException $e) {
        $flash = 'Erro: ' . $e->getMessage();
    }
    $_SESSION['flash'] = $flash;
    redirect('admin.php' . ($accountId ? "?account=$accountId" : ''));
}

$flash = $_SESSION['flash'] ?? null;
unset($_SESSION['flash']);
$q = trim((string) ($_GET['q'] ?? ''));
$account = $accountId ? $admin->account($accountId) : null;
$chars = $account ? $admin->characters($accountId) : [];
$charIds = array_map(fn ($c) => (int) $c['id'], $chars);
$nick = array_column($chars, 'nickname', 'id');
$money = fn ($v) => number_format((int) $v, 0, ',', '.');
?>
<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GM · <?= h($CONFIG['site_name']) ?></title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
<main class="panel wide">
    <h1>Painel GM</h1>
    <p class="muted">GM <b><?= h($me['username']) ?></b> · <a href="admin.php">busca</a> · <a href="./">portal</a></p>
    <?php if ($flash): ?><p class="card <?= str_starts_with($flash, 'Erro') ? 'error' : '' ?>"><?= h($flash) ?></p><?php endif ?>

<?php if (!$account): ?>
    <form method="get" class="card actions">
        <input name="q" value="<?= h($q) ?>" placeholder="usuário, nick ou id" style="flex:1">
        <button>Buscar</button>
    </form>
    <div class="scroll"><table>
        <tr><th>Conta</th><th>Personagem</th><th>Srv</th><th>Nível</th><th>Ouro</th><th>Point</th><th>Gift</th><th>Ruh</th><th>Último login</th></tr>
        <?php foreach ($admin->search($q) as $r): ?>
        <tr class="<?= (int) $r['banned'] ? 'banned' : '' ?>">
            <td><a href="admin.php?account=<?= (int) $r['account_id'] ?>">#<?= (int) $r['account_id'] ?> <?= h($r['username']) ?></a><?= (int) $r['banned'] ? ' <span class="badge off">banida</span>' : '' ?></td>
            <td><?= $r['id'] ? '#' . (int) $r['id'] . ' ' . h($r['nickname'] ?? '(sem nick)') : '—' ?></td>
            <td><?= h((string) $r['server_id']) ?></td>
            <td><?= h((string) $r['grades']) ?></td>
            <td><?= $r['id'] ? $money($r['gold']) : '' ?></td>
            <td><?= $r['id'] ? $money($r['point']) : '' ?></td>
            <td><?= $r['id'] ? $money($r['gift_token']) : '' ?></td>
            <td><?= $r['id'] ? $money($r['strategy']) : '' ?></td>
            <td class="muted"><?= h($r['char_login_at'] ?? $r['last_login_at']) ?></td>
        </tr>
        <?php endforeach ?>
    </table></div>
<?php else: ?>
    <section class="card">
        <h2>#<?= (int) $account['id'] ?> <?= h($account['username']) ?>
            <?= (int) $account['banned'] ? '<span class="badge off">banida</span>' : '' ?></h2>
        <p class="muted">criada <?= h($account['created_at']) ?> · último login no portal <?= h($account['last_login_at']) ?></p>
        <form method="post" onsubmit="return confirm('Confirmar?')">
            <input type="hidden" name="csrf" value="<?= h(csrf_token()) ?>">
            <input type="hidden" name="account" value="<?= (int) $account['id'] ?>">
            <input type="hidden" name="banned" value="<?= (int) $account['banned'] ? 0 : 1 ?>">
            <button name="action" value="ban" class="<?= (int) $account['banned'] ? 'secondary' : 'danger' ?>">
                <?= (int) $account['banned'] ? 'Desbanir conta' : 'Banir conta' ?></button>
        </form>
    </section>

    <?php foreach ($chars as $c): $id = (int) $c['id']; ?>
    <section class="card">
        <h2>#<?= $id ?> <?= h($c['nickname'] ?? '(sem nick)') ?> <span class="muted">servidor <?= (int) $c['server_id'] ?> · último login <?= h($c['last_login_at']) ?></span></h2>
        <form method="post" class="grid">
            <input type="hidden" name="csrf" value="<?= h(csrf_token()) ?>">
            <input type="hidden" name="account" value="<?= (int) $account['id'] ?>">
            <input type="hidden" name="character" value="<?= $id ?>">
            <?php foreach (Admin::EDITABLE as $col => $min): ?>
                <label><?= h($col) ?><input name="<?= h($col) ?>" type="number" min="<?= $min ?>" max="<?= Admin::INT32_MAX ?>" value="<?= (int) $c[$col] ?>"><input type="hidden" name="orig[<?= h($col) ?>]" value="<?= (int) $c[$col] ?>"></label>
            <?php endforeach ?>
            <div class="actions"><button name="action" value="edit">Salvar (derruba o jogador)</button></div>
        </form>
        <form method="post" class="actions">
            <input type="hidden" name="csrf" value="<?= h(csrf_token()) ?>">
            <input type="hidden" name="account" value="<?= (int) $account['id'] ?>">
            <input type="hidden" name="character" value="<?= $id ?>">
            <input name="amount" type="number" min="1" max="<?= Admin::INT32_MAX ?>" placeholder="point" required style="flex:1">
            <input name="ref" placeholder="referência (comprovante)" style="flex:2">
            <button name="action" value="recharge">Recarregar</button>
        </form>
        <form method="post" class="actions" onsubmit="return confirm('Apagar o personagem e tudo dele? Não tem volta.')">
            <input type="hidden" name="csrf" value="<?= h(csrf_token()) ?>">
            <input type="hidden" name="account" value="<?= (int) $account['id'] ?>">
            <input type="hidden" name="character" value="<?= $id ?>">
            <input name="confirm" placeholder="digite <?= h($c['nickname'] ?? (string) $id) ?> para confirmar" required style="flex:1">
            <button name="action" value="reset" class="danger">Resetar personagem</button>
        </form>
    </section>
    <?php endforeach ?>

    <?php
    $tables = [
        'Logins' => [$admin->history('login_history', 'account_id', [(int) $account['id']]), ['created_at', 'source', 'character_id', 'ip', 'user_agent']],
        'Cash (compras, GM, recargas)' => [$admin->history('cash_ledger', 'character_id', $charIds), ['created_at', 'character_id', 'reason', 'delta_point', 'delta_gift_token', 'balance_point', 'balance_gift_token', 'ref', 'gm']],
        'Itens' => [$admin->history('item_log', 'character_id', $charIds), ['created_at', 'character_id', 'action', 'template_id', 'count', 'ref']],
    ];
    foreach ($tables as $title => [$rows, $cols]): ?>
    <section class="card">
        <h2><?= h($title) ?></h2>
        <?php if (!$rows): ?><p class="muted">nada registrado</p><?php else: ?>
        <div class="scroll"><table>
            <tr><?php foreach ($cols as $col): ?><th><?= h($col) ?></th><?php endforeach ?></tr>
            <?php foreach ($rows as $r): ?>
            <tr><?php foreach ($cols as $col): ?><td><?= h($col === 'character_id' && isset($nick[$r[$col]]) ? $nick[$r[$col]] : (string) $r[$col]) ?></td><?php endforeach ?></tr>
            <?php endforeach ?>
        </table></div>
        <?php endif ?>
    </section>
    <?php endforeach ?>
<?php endif ?>
</main>
</body>
</html>
