<?php
declare(strict_types=1);

/** Servidores de jogo publicados pelos processos Python em game_servers. */
final class GameServers
{
    public function __construct(private readonly Database $db)
    {
    }

    public function all(): array
    {
        return $this->db->all('SELECT * FROM game_servers ORDER BY id');
    }

    public function get(int $id): ?array
    {
        return $this->db->one('SELECT * FROM game_servers WHERE id = ?', [$id]);
    }

    /** Teste rápido: o socket do jogo aceita conexão? */
    public static function isOnline(array $server, float $timeout = 0.3): bool
    {
        $socket = @fsockopen($server['public_host'], (int) $server['socket_port'], $errno, $error, $timeout);
        if ($socket === false) {
            return false;
        }
        fclose($socket);
        return true;
    }

    /** "fuso UTC · agora 14:05": o horário do jogo (eventos, chefes) para o jogador escolher o servidor. */
    public static function clock(array $server): string
    {
        $tz = (string) ($server['timezone'] ?? 'UTC');
        try {
            $now = new DateTime('now', new DateTimeZone($tz));
        } catch (Exception) {
            return "fuso $tz";
        }
        $offset = $now->format('P') === '+00:00' ? '' : ' (UTC' . $now->format('P') . ')';
        return "fuso $tz · agora " . $now->format('H:i') . $offset;
    }

    public static function requestUrl(array $server): string
    {
        // Configuração explícita tem precedência sobre qualquer descoberta automática.
        $base = getenv('WARTUNE_SERVER_HTTP_URL') ?: '';
        if ($base !== '') {
            return rtrim($base, '/') . '/';
        }

        // Sem configuração: se a rede interna do Docker resolver o serviço, usa a porta interna 8080.
        // O resultado fica em cache no processo para não sondar o socket a cada chamada.
        static $internal = null;
        if ($internal === null) {
            $fp = @fsockopen('bots_wartune-server', 8080, $errno, $errstr, 0.3);
            $internal = $fp ? 'http://bots_wartune-server:8080/' : '';
            if ($fp) {
                fclose($fp);
            }
        }
        if ($internal !== '') {
            return $internal;
        }

        return sprintf('http://%s:%d/', $server['public_host'], $server['http_port']);
    }

    /** Quantos personagens a conta tem em cada servidor (para mostrar na lista). */
    public function charactersOf(int $accountId): array
    {
        $rows = $this->db->all(
            'SELECT server_id, nickname, grades FROM characters WHERE account_id = ? AND active = TRUE',
            [$accountId]
        );
        return array_column($rows, null, 'server_id');
    }
}
