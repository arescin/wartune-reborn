<?php
declare(strict_types=1);

final class AdminError extends RuntimeException
{
}

/**
 * Painel GM. Toda escrita num personagem passa antes por POST /gm/kick no servidor dele: com o
 * jogador online, a sessão gravaria o snapshot por cima da edição. Servidor fora do ar (conexão
 * recusada) = ninguém online, pode gravar; qualquer outro erro = não grava.
 */
final class Admin
{
    public const INT32_MAX = 2147483647;
    /** Colunas editáveis => valor mínimo. */
    public const EDITABLE = [
        'gold' => 0, 'point' => 0, 'gift_token' => 0, 'strategy' => 0, 'novice_process' => 0, 'grades' => 1,
    ];

    public function __construct(private readonly Database $db, private readonly string $secret, private readonly string $gm)
    {
    }

    public function search(string $q): array
    {
        $like = '%' . $q . '%';
        return $this->db->all(
            'SELECT a.id AS account_id, a.username, a.banned, a.last_login_at, c.id, c.server_id, c.nickname,
                    c.grades, c.gold, c.point, c.gift_token, c.strategy, c.last_login_at AS char_login_at
             FROM accounts a LEFT JOIN characters c ON c.account_id = a.id
             WHERE ? = \'\' OR a.username LIKE ? OR c.nickname LIKE ? OR a.id = ? OR c.id = ?
             ORDER BY a.id DESC, c.server_id LIMIT 100',
            [$q, $like, $like, (int) $q, (int) $q]
        );
    }

    public function account(int $id): ?array
    {
        return $this->db->one('SELECT id, username, banned, created_at, last_login_at FROM accounts WHERE id = ?', [$id]);
    }

    public function characters(int $accountId): array
    {
        return $this->db->all('SELECT * FROM characters WHERE account_id = ? ORDER BY server_id', [$accountId]);
    }

    /** Histórico; tabela ausente (servidor antigo) vira lista vazia. */
    public function history(string $table, string $column, array $ids): array
    {
        if (!$ids) {
            return [];
        }
        $in = implode(',', array_fill(0, count($ids), '?'));
        try {
            return $this->db->all("SELECT * FROM $table WHERE $column IN ($in) ORDER BY id DESC LIMIT 200", $ids);
        } catch (PDOException) {
            return [];
        }
    }

    /** @param array<string, string> $values coluna => valor do formulário */
    public function edit(int $characterId, array $values): void
    {
        $set = [];
        foreach (self::EDITABLE as $column => $min) {
            if (!isset($values[$column]) || $values[$column] === '') {
                continue;
            }
            $value = filter_var($values[$column], FILTER_VALIDATE_INT, ['options' => ['min_range' => $min, 'max_range' => self::INT32_MAX]]);
            if ($value === false) {
                throw new AdminError("$column deve ser um inteiro entre $min e " . self::INT32_MAX . '.');
            }
            $set[$column] = $value;
        }
        if (!$set) {
            throw new AdminError('Nada para alterar.');
        }
        $this->kick($characterId);
        $this->write($characterId, fn (array $c): array => [$set, 'gm', 'portal']);
    }

    public function recharge(int $characterId, string $amount, string $ref): void
    {
        $value = filter_var($amount, FILTER_VALIDATE_INT, ['options' => ['min_range' => 1, 'max_range' => self::INT32_MAX]]);
        if ($value === false) {
            throw new AdminError('Valor da recarga inválido.');
        }
        $this->kick($characterId);
        $this->write($characterId, function (array $c) use ($value, $ref): array {
            $point = (int) $c['point'] + $value;
            if ($point > self::INT32_MAX) {
                throw new AdminError('O saldo passaria do limite int32.');
            }
            return [['point' => $point], 'recharge', $ref];
        });
    }

    public function reset(int $characterId): void
    {
        $this->kick($characterId);
        $this->db->run('DELETE FROM characters WHERE id = ?', [$characterId]); // FKs em CASCADE levam o resto
    }

    /** Marca a conta e avisa cada servidor (derruba e invalida as chaves de login). Devolve avisos. */
    public function ban(int $accountId, bool $banned): array
    {
        $this->db->run('UPDATE accounts SET banned = ? WHERE id = ?', [$banned ? 1 : 0, $accountId]);
        $warnings = [];
        foreach ($this->db->all('SELECT * FROM game_servers ORDER BY id') as $server) {
            $error = $this->call($server, 'gm/ban', ['account_id' => $accountId, 'banned' => $banned ? 1 : 0]);
            if ($error !== null) {
                $warnings[] = "{$server['name']}: $error";
            }
        }
        return $warnings;
    }

    /**
     * Lê o personagem, aplica e grava numa transação; mudança de point/gift_token vai para o cash_ledger.
     * @param callable(array): array{0: array<string,int>, 1: string, 2: string} $change
     */
    private function write(int $characterId, callable $change): void
    {
        $pdo = $this->db->pdo;
        $pdo->beginTransaction();
        try {
            $c = $this->db->one('SELECT * FROM characters WHERE id = ?', [$characterId])
                ?? throw new AdminError('Personagem não encontrado.');
            [$set, $reason, $ref] = $change($c);
            $assign = implode(', ', array_map(fn ($col) => "$col = ?", array_keys($set))); // colunas da whitelist
            $this->db->run("UPDATE characters SET $assign WHERE id = ?", [...array_values($set), $characterId]);
            $point = $set['point'] ?? (int) $c['point'];
            $gift = $set['gift_token'] ?? (int) $c['gift_token'];
            if ($point !== (int) $c['point'] || $gift !== (int) $c['gift_token']) {
                $this->db->run(
                    'INSERT INTO cash_ledger (character_id, delta_point, delta_gift_token, balance_point,
                        balance_gift_token, reason, ref, gm, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    [$characterId, $point - (int) $c['point'], $gift - (int) $c['gift_token'], $point, $gift,
                        $reason, $ref, $this->gm, Database::now()]
                );
            }
            $pdo->commit();
        } catch (Throwable $e) {
            $pdo->rollBack();
            throw $e;
        }
    }

    // ponytail: o jogador pode relogar entre o kick e o UPDATE (janela de milissegundos); trava no
    // servidor (recusar login durante a edição) se isso aparecer na prática
    private function kick(int $characterId): void
    {
        $server = $this->db->one(
            'SELECT s.* FROM game_servers s JOIN characters c ON c.server_id = s.id WHERE c.id = ?',
            [$characterId]
        ) ?? throw new AdminError('Personagem ou servidor não encontrado.');
        $error = $this->call($server, 'gm/kick', ['character_id' => $characterId]);
        if ($error !== null) {
            throw new AdminError("Não gravei: o servidor {$server['name']} não confirmou a saída do jogador ($error).");
        }
    }

    /** null = ok ou servidor fora do ar; senão a mensagem do erro. */
    private function call(array $server, string $path, array $form): ?string
    {
        $ch = curl_init(GameServers::requestUrl($server) . $path);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => http_build_query($form),
            CURLOPT_HTTPHEADER => ['X-GM-Secret: ' . $this->secret],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_TIMEOUT => 10, // o kick espera a sessão gravar e sair
        ]);
        $body = curl_exec($ch);
        $errno = curl_errno($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $error = curl_error($ch);
        if ($errno === CURLE_COULDNT_CONNECT) {
            return null; // servidor fora: ninguém online nele
        }
        if ($errno !== 0) {
            return $error;
        }
        if ($status === 200) {
            return null;
        }
        $message = json_decode((string) $body, true)['error'] ?? '';
        return match ($status) {
            403 => 'segredo GM diferente do WARTUNE_GM_SECRET',
            404 => 'rota GM desligada (WARTUNE_GM_SECRET vazio no servidor)',
            default => "HTTP $status $message",
        };
    }
}
