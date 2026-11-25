<?php
declare(strict_types=1);

/**
 * Ticket de entrada: único contrato entre o portal e o servidor do jogo.
 * Vai como flashvar "key"; o Loading.swf o manda no POST /login e o servidor confere
 * (conta, servidor e validade) em play_tickets.
 */
final class Tickets
{
    public function __construct(private readonly Database $db, private readonly int $ttlSeconds)
    {
    }

    public function issue(int $accountId, int $serverId): string
    {
        $token = rtrim(strtr(base64_encode(random_bytes(24)), '+/', '-_'), '=');
        $this->db->run(
            'INSERT INTO play_tickets (token, account_id, server_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?)',
            [$token, $accountId, $serverId, Database::now(), Database::now($this->ttlSeconds)]
        );
        $this->db->run('DELETE FROM play_tickets WHERE expires_at < ?', [Database::now(-86400)]);
        return $token;
    }
}
