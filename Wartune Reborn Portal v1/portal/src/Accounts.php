<?php
declare(strict_types=1);

final class AccountError extends RuntimeException
{
}

/** Contas globais: uma conta pode ter um personagem em cada servidor. */
final class Accounts
{
    private const USERNAME = '/^[A-Za-z0-9_.-]{3,32}$/';

    public function __construct(private readonly Database $db)
    {
    }

    /** @return array{id:int, username:string} */
    public function register(string $username, string $password): array
    {
        if (!preg_match(self::USERNAME, $username)) {
            throw new AccountError('Usuário deve ter 3 a 32 caracteres: letras, números, _ . -');
        }
        if (strlen($password) < 6) {
            throw new AccountError('A senha deve ter pelo menos 6 caracteres.');
        }
        if ($this->db->one('SELECT id FROM accounts WHERE username = ?', [$username])) {
            throw new AccountError('Esse usuário já existe.');
        }
        $this->db->run(
            'INSERT INTO accounts (username, password_hash, created_at, banned) VALUES (?, ?, ?, 0)',
            [$username, password_hash($password, PASSWORD_DEFAULT), Database::now()]
        );
        return $this->authenticate($username, $password);
    }

    /** @return array{id:int, username:string} */
    public function authenticate(string $username, string $password): array
    {
        $row = $this->db->one('SELECT id, username, password_hash, banned FROM accounts WHERE username = ?', [$username]);
        if (!$row || !password_verify($password, $row['password_hash'])) {
            throw new AccountError('Usuário ou senha inválidos.');
        }
        if ((int) $row['banned']) {
            throw new AccountError('Conta bloqueada.');
        }
        $this->db->run('UPDATE accounts SET last_login_at = ? WHERE id = ?', [Database::now(), $row['id']]);
        try {
            $this->db->run(
                "INSERT INTO login_history (account_id, source, ip, user_agent, created_at) VALUES (?, 'portal', ?, ?, ?)",
                [$row['id'], $_SERVER['REMOTE_ADDR'] ?? '', $_SERVER['HTTP_USER_AGENT'] ?? null, Database::now()]
            );
        } catch (PDOException) {
            // banco ainda sem a migração do histórico: o login não pode depender disso
        }
        return ['id' => (int) $row['id'], 'username' => $row['username']];
    }
}
