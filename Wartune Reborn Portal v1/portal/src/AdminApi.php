<?php
declare(strict_types=1);

final class AdminApi
{
    private static ?array $itemsCache = null;

    public function __construct(
        private readonly Database $db,
        private readonly string $secret,
        private readonly string $gm,
        private readonly array $config
    ) {
    }

    public function handle(string $action): array
    {
        return match ($action) {
            'dashboard' => $this->getDashboard(),
            'search' => $this->search((string) ($_GET['q'] ?? '')),
            'account' => $this->getAccount((int) ($_GET['id'] ?? 0)),
            'character' => $this->getCharacter((int) ($_GET['id'] ?? 0)),
            'character_edit' => $this->editCharacter((int) ($_POST['character_id'] ?? 0), $_POST),
            'character_vip' => $this->setVip((int) ($_POST['character_id'] ?? 0), (int) ($_POST['days'] ?? 0), (int) ($_POST['grade'] ?? 1)),
            'character_kick' => $this->kickPlayer((int) ($_POST['character_id'] ?? 0)),
            'character_reset' => $this->resetCharacter((int) ($_POST['character_id'] ?? 0), (string) ($_POST['confirm'] ?? '')),
            'account_ban' => $this->banAccount((int) ($_POST['account_id'] ?? 0), (bool) ($_POST['banned'] ?? false)),
            'account_password' => $this->changePassword((int) ($_POST['account_id'] ?? 0), (string) ($_POST['password'] ?? '')),
            'recharge' => $this->recharge((int) ($_POST['character_id'] ?? 0), (int) ($_POST['amount'] ?? 0), (string) ($_POST['ref'] ?? '')),
            'send_mail' => $this->sendMail($_POST),
            'search_items' => $this->searchItems((string) ($_GET['q'] ?? '')),
            'logs' => $this->getLogs((string) ($_GET['type'] ?? 'login'), (int) ($_GET['page'] ?? 1)),
            default => throw new InvalidArgumentException("Ação desconhecida: $action"),
        };
    }

    private function getDashboard(): array
    {
        $accountsCount = (int) ($this->db->one('SELECT count(*) as c FROM accounts')['c'] ?? 0);
        $charsCount = (int) ($this->db->one('SELECT count(*) as c FROM characters')['c'] ?? 0);
        
        $totals = $this->db->one('SELECT 
            coalesce(sum(gold), 0) as total_gold,
            coalesce(sum(point), 0) as total_point,
            coalesce(sum(gift_token), 0) as total_gift,
            coalesce(sum(strategy), 0) as total_strategy
        FROM characters') ?? [];

        $totalRecharge = (int) ($this->db->one('SELECT coalesce(sum(delta_point), 0) as s FROM cash_ledger WHERE delta_point > 0')['s'] ?? 0);

        // Teste de conectividade dos serviços
        $serverHost = '179.198.96.49';
        $services = [
            'game_server' => ['name' => 'Game Server TCP', 'port' => 5000, 'online' => $this->checkPort($serverHost, 5000)],
            'database' => ['name' => 'PostgreSQL 16', 'port' => 5432, 'online' => true],
            'portal_web' => ['name' => 'Portal HTTP', 'port' => 80, 'online' => true],
        ];

        // Últimos personagens criados / ativos
        $recentChars = $this->db->all('
            SELECT c.id, c.server_id, c.nickname, c.grades, c.gold, c.point, c.gift_token, c.strategy, c.job, c.fighting_capacity,
                   a.id AS account_id, a.username AS account_name
            FROM characters c
            JOIN accounts a ON a.id = c.account_id
            ORDER BY c.id DESC LIMIT 8
        ');

        return [
            'accounts_count' => $accountsCount,
            'characters_count' => $charsCount,
            'totals' => [
                'total_gold' => (int) ($totals['total_gold'] ?? 0),
                'total_point' => (int) ($totals['total_point'] ?? 0),
                'total_gift' => (int) ($totals['total_gift'] ?? 0),
                'total_strategy' => (int) ($totals['total_strategy'] ?? 0),
            ],
            'total_recharge' => $totalRecharge,
            'services' => $services,
            'recent_characters' => $recentChars,
        ];
    }

    private function checkPort(string $host, int $port, float $timeout = 0.8): bool
    {
        $fp = @fsockopen($host, $port, $errno, $errstr, $timeout);
        if ($fp) {
            fclose($fp);
            return true;
        }
        return false;
    }

    private function search(string $q): array
    {
        $q = trim($q);
        $like = '%' . $q . '%';
        $intVal = (int) $q;

        $chars = $this->db->all(
            'SELECT c.id, c.server_id, c.nickname, c.grades, c.gold, c.point, c.gift_token, c.job, c.fighting_capacity,
                    a.id AS account_id, a.username AS account_name
             FROM characters c
             JOIN accounts a ON a.id = c.account_id
             WHERE ? = \'\' OR c.nickname ILIKE ? OR a.username ILIKE ? OR c.id = ? OR a.id = ?
             ORDER BY c.id DESC LIMIT 30',
            [$q, $like, $like, $intVal, $intVal]
        );

        $accounts = $this->db->all(
            'SELECT a.id, a.username, a.banned, a.created_at, a.last_login_at
             FROM accounts a
             WHERE ? = \'\' OR a.username ILIKE ? OR a.id = ?
             ORDER BY a.id DESC LIMIT 30',
            [$q, $like, $intVal]
        );

        return [
            'characters' => $chars,
            'accounts' => array_map(fn($a) => [
                'id' => (int) $a['id'],
                'username' => (string) $a['username'],
                'is_banned' => (bool) $a['banned'],
                'created_at' => $a['created_at'],
                'last_login_at' => $a['last_login_at'],
            ], $accounts)
        ];
    }

    private function getAccount(int $id): array
    {
        $acc = $this->db->one('SELECT id, username, banned, created_at, last_login_at FROM accounts WHERE id = ?', [$id]);
        if (!$acc) {
            throw new RuntimeException('Conta não encontrada.');
        }
        $chars = $this->db->all('SELECT * FROM characters WHERE account_id = ? ORDER BY server_id', [$id]);
        $isGm = in_array($acc['username'], $this->config['gm_users'] ?? [], true);
        return [
            'account' => $acc,
            'characters' => $chars,
            'is_gm' => $isGm,
        ];
    }

    private function getCharacter(int $id): array
    {
        $char = $this->db->one('SELECT * FROM characters WHERE id = ?', [$id]);
        if (!$char) {
            throw new RuntimeException('Personagem não encontrado.');
        }
        $account = $this->db->one('SELECT id, username, banned FROM accounts WHERE id = ?', [$char['account_id']]);

        // Dados VIP de event_states
        $vipState = $this->db->one("SELECT value, text, updated_at FROM event_states WHERE character_id = ? AND key = 'vip'", [$id]);
        $vipTypeState = $this->db->one("SELECT value FROM event_states WHERE character_id = ? AND key = 'vip:type'", [$id]);

        $vipInfo = [
            'active' => false,
            'expires_at' => null,
            'vip_gp' => (int) ($vipState['value'] ?? 0),
            'vip_type' => (int) ($vipTypeState['value'] ?? 0),
            'grade' => (int) ($vipTypeState['value'] ?? 0),
        ];
        if (!empty($vipState['text'])) {
            $expiry = strtotime((string) $vipState['text']);
            if ($expiry && $expiry > time()) {
                $vipInfo['active'] = true;
                $vipInfo['expires_at'] = $vipState['text'];
            }
        }

        // Itens com mapeamento de nomes e ícones do catálogo
        $items = $this->db->all('
            SELECT id, template_id, count, pos
            FROM items
            WHERE character_id = ? AND count > 0
            ORDER BY pos ASC LIMIT 80
        ', [$id]);

        $catalog = $this->getItemsCatalog();
        $inv = [];
        foreach ($items as $it) {
            $tid = (int) $it['template_id'];
            $meta = $catalog[$tid] ?? null;
            $inv[] = [
                'id' => (int) $it['id'],
                'template_id' => $tid,
                'count' => (int) $it['count'],
                'place' => (int) $it['pos'],
                'pos' => (int) $it['pos'],
                'name' => $meta['name'] ?? ('Item #' . $tid),
                'icon' => $meta['icon'] ?? '0',
                'quality' => (int) ($meta['quality'] ?? 1),
            ];
        }

        return [
            'character' => array_merge($char, ['account_name' => $account['username'] ?? '']),
            'vip' => $vipInfo,
            'inventory' => $inv,
        ];
    }

    private function editCharacter(int $charId, array $post): array
    {
        $char = $this->db->one('SELECT * FROM characters WHERE id = ?', [$charId]);
        if (!$char) {
            throw new RuntimeException('Personagem não encontrado.');
        }

        $server = $this->db->one('SELECT * FROM game_servers WHERE id = ?', [$char['server_id']]);
        if ($server) {
            $this->callGm($server, '/gm/kick', ['character_id' => $charId]);
        }

        $fields = [
            'grades' => max(1, min(100, (int) ($post['grades'] ?? $char['grades']))),
            'gold' => max(0, min(2000000000, (int) ($post['gold'] ?? $char['gold']))),
            'point' => max(0, min(2000000000, (int) ($post['point'] ?? $char['point']))),
            'gift_token' => max(0, min(2000000000, (int) ($post['gift_token'] ?? $char['gift_token']))),
            'strategy' => max(0, min(2000000000, (int) ($post['strategy'] ?? $char['strategy']))),
            'crystals' => max(0, min(2000000000, (int) ($post['crystal'] ?? $char['crystals']))),
            'gp' => max(0, (int) ($post['gp'] ?? $char['gp'])),
            'fighting_capacity' => max(0, (int) ($post['fight_capacity'] ?? $char['fighting_capacity'])),
        ];

        $sets = [];
        $params = [];
        foreach ($fields as $col => $val) {
            $sets[] = "$col = ?";
            $params[] = $val;
        }
        $params[] = $charId;

        $this->db->exec('UPDATE characters SET ' . implode(', ', $sets) . ' WHERE id = ?', $params);
        return ['updated' => true, 'character_id' => $charId];
    }

    private function setVip(int $charId, int $days, int $grade): array
    {
        $days = max(1, min(3650, $days));
        $grade = max(1, min(10, $grade));
        $expiryTime = date('Y-m-d H:i:s', strtotime("+{$days} days"));

        $this->db->exec("
            INSERT INTO event_states (character_id, key, value, text, updated_at)
            VALUES (?, 'vip', ?, ?, NOW())
            ON CONFLICT (character_id, key) DO UPDATE 
            SET value = EXCLUDED.value, text = EXCLUDED.text, updated_at = NOW()
        ", [$charId, $grade * 1000, $expiryTime]);

        $this->db->exec("
            INSERT INTO event_states (character_id, key, value, text, updated_at)
            VALUES (?, 'vip:type', ?, '', NOW())
            ON CONFLICT (character_id, key) DO UPDATE 
            SET value = EXCLUDED.value, updated_at = NOW()
        ", [$charId, $grade]);

        return ['success' => true, 'expires_at' => $expiryTime, 'grade' => $grade];
    }

    private function kickPlayer(int $charId): array
    {
        $char = $this->db->one('SELECT server_id FROM characters WHERE id = ?', [$charId]);
        if (!$char) {
            throw new RuntimeException('Personagem não encontrado.');
        }
        $server = $this->db->one('SELECT * FROM game_servers WHERE id = ?', [$char['server_id']]);
        if (!$server) {
            throw new RuntimeException('Servidor não localizado.');
        }
        $err = $this->callGm($server, '/gm/kick', ['character_id' => $charId]);
        if ($err !== null) {
            throw new RuntimeException("Aviso GM: $err");
        }
        return ['kicked' => true];
    }

    private function resetCharacter(int $charId, string $confirm): array
    {
        $char = $this->db->one('SELECT * FROM characters WHERE id = ?', [$charId]);
        if (!$char) {
            throw new RuntimeException('Personagem não encontrado.');
        }
        if (trim($confirm) !== (string) $char['nickname']) {
            throw new RuntimeException('Confirmação inválida. Digite exatamente o nickname do personagem.');
        }

        $server = $this->db->one('SELECT * FROM game_servers WHERE id = ?', [$char['server_id']]);
        if ($server) {
            $this->callGm($server, '/gm/kick', ['character_id' => $charId]);
        }

        $this->db->exec('DELETE FROM items WHERE character_id = ?', [$charId]);
        $this->db->exec('DELETE FROM event_states WHERE character_id = ?', [$charId]);
        $this->db->exec('DELETE FROM mails WHERE receiver_id = ?', [$charId]);
        $this->db->exec('DELETE FROM characters WHERE id = ?', [$charId]);

        return ['deleted' => true];
    }

    private function banAccount(int $accId, bool $banned): array
    {
        $this->db->exec('UPDATE accounts SET banned = ? WHERE id = ?', [$banned ? 1 : 0, $accId]);
        if ($banned) {
            $chars = $this->db->all('SELECT id, server_id FROM characters WHERE account_id = ?', [$accId]);
            foreach ($chars as $c) {
                $server = $this->db->one('SELECT * FROM game_servers WHERE id = ?', [$c['server_id']]);
                if ($server) {
                    $this->callGm($server, '/gm/kick', ['character_id' => (int) $c['id']]);
                }
            }
        }
        return ['banned' => $banned, 'account_id' => $accId];
    }

    private function changePassword(int $accId, string $newPassword): array
    {
        if (strlen($newPassword) < 4) {
            throw new RuntimeException('A senha deve ter pelo menos 4 caracteres.');
        }
        $hash = password_hash($newPassword, PASSWORD_DEFAULT);
        $this->db->exec('UPDATE accounts SET password_hash = ? WHERE id = ?', [$hash, $accId]);
        return ['updated' => true];
    }

    private function recharge(int $charId, int $amount, string $ref): array
    {
        if ($amount <= 0 || $amount > 2000000000) {
            throw new RuntimeException('Quantidade de diamantes inválida.');
        }
        $char = $this->db->one('SELECT * FROM characters WHERE id = ?', [$charId]);
        if (!$char) {
            throw new RuntimeException('Personagem não encontrado.');
        }

        $server = $this->db->one('SELECT * FROM game_servers WHERE id = ?', [$char['server_id']]);
        if ($server) {
            $this->callGm($server, '/gm/recharge', [
                'character_id' => $charId,
                'amount' => $amount,
                'ref' => $ref ?: 'Painel GM',
            ]);
        }

        $this->db->exec('UPDATE characters SET point = point + ? WHERE id = ?', [$amount, $charId]);
        $newPoint = (int) ($char['point'] + $amount);

        $this->db->exec('
            INSERT INTO cash_ledger (character_id, delta_point, delta_gift_token, balance_point, balance_gift_token, reason, ref, gm, created_at)
            VALUES (?, ?, 0, ?, ?, ?, ?, ?, NOW())
        ', [
            $charId,
            $amount,
            $newPoint,
            (int) $char['gift_token'],
            'Recarga Painel GM',
            $ref ?: 'Painel GM',
            $this->gm,
        ]);

        return ['new_point' => $newPoint, 'credited' => $amount];
    }

    private function sendMail(array $post): array
    {
        $targetType = (string) ($post['target_type'] ?? 'single');
        $title = trim((string) ($post['title'] ?? 'Recompensa do Sistema'));
        $contents = trim((string) ($post['contents'] ?? ''));
        $senderNick = trim((string) ($post['sender_nick'] ?? 'Sistema GM')) ?: 'Sistema GM';

        $gold = max(0, min(2000000000, (int) ($post['gold'] ?? 0)));
        $diamonds = max(0, min(2000000000, (int) ($post['diamonds'] ?? 0)));
        $boundDiamonds = max(0, min(2000000000, (int) ($post['bound_diamonds'] ?? 0)));

        $items = $post['items'] ?? [];
        if (!is_array($items)) {
            $items = [];
        }

        $annexes = [];
        $slot = 1;

        if ($gold > 0) {
            $annexes[] = ['slot' => $slot++, 'template_id' => -100, 'count' => $gold];
        }
        if ($diamonds > 0) {
            $annexes[] = ['slot' => $slot++, 'template_id' => -400, 'count' => $diamonds];
        }
        if ($boundDiamonds > 0) {
            $annexes[] = ['slot' => $slot++, 'template_id' => -500, 'count' => $boundDiamonds];
        }

        foreach ($items as $it) {
            $tid = (int) ($it['template_id'] ?? 0);
            $cnt = (int) ($it['count'] ?? 1);
            if ($tid > 0 && $cnt > 0 && $slot <= 5) {
                $annexes[] = ['slot' => $slot++, 'template_id' => $tid, 'count' => $cnt];
            }
        }

        $receivers = [];
        if ($targetType === 'all') {
            $allChars = $this->db->all('SELECT id FROM characters WHERE active = true');
            $receivers = array_column($allChars, 'id');
        } else {
            $rawReceiver = trim((string) ($post['receiver'] ?? ''));
            if ($rawReceiver === '') {
                throw new RuntimeException('Informe o ID ou Nickname do personagem.');
            }
            if (ctype_digit($rawReceiver)) {
                $target = $this->db->one('SELECT id FROM characters WHERE id = ?', [(int) $rawReceiver]);
            } else {
                $target = $this->db->one('SELECT id FROM characters WHERE nickname = ?', [$rawReceiver]);
            }
            if (!$target) {
                throw new RuntimeException("Personagem '$rawReceiver' não encontrado.");
            }
            $receivers[] = (int) $target['id'];
        }

        $sentCount = 0;
        foreach ($receivers as $rcvId) {
            $inserted = $this->db->one('
                INSERT INTO mails (receiver_id, sender_id, sender_nick, sender_grades, mail_type, send_type, title, contents, sent_at, validity_days)
                VALUES (?, 0, ?, 100, 1, 1, ?, ?, NOW(), 30)
                RETURNING id
            ', [$rcvId, $senderNick, $title, $contents]);

            $mailId = (int) ($inserted['id'] ?? $this->db->lastInsertId('mails_id_seq'));

            foreach ($annexes as $anx) {
                $this->db->exec('
                    INSERT INTO mail_annexes (mail_id, slot, template_id, count, taken, item_id)
                    VALUES (?, ?, ?, ?, false, 0)
                ', [$mailId, $anx['slot'], $anx['template_id'], $anx['count']]);
            }
            $sentCount++;
        }

        return ['sent_count' => $sentCount];
    }

    private function searchItems(string $q): array
    {
        $qNorm = $this->normalizeText($q);
        if (strlen($qNorm) < 2) {
            return [];
        }
        $catalog = $this->getItemsCatalog();
        $matches = [];
        foreach ($catalog as $tid => $meta) {
            $nameNorm = $this->normalizeText($meta['name'] ?? '');
            if (str_contains($nameNorm, $qNorm) || (string) $tid === $q) {
                $matches[] = array_merge(['id' => $tid], $meta);
                if (count($matches) >= 30) {
                    break;
                }
            }
        }
        return $matches;
    }

    private function normalizeText(string $str): string
    {
        $str = mb_strtolower(trim($str), 'UTF-8');
        $map = [
            'á'=>'a', 'à'=>'a', 'ã'=>'a', 'â'=>'a', 'ä'=>'a',
            'é'=>'e', 'è'=>'e', 'ê'=>'e', 'ë'=>'e',
            'í'=>'i', 'ì'=>'i', 'î'=>'i', 'ï'=>'i',
            'ó'=>'o', 'ò'=>'o', 'õ'=>'o', 'ô'=>'o', 'ö'=>'o',
            'ú'=>'u', 'ù'=>'u', 'û'=>'u', 'ü'=>'u',
            'ç'=>'c', 'ñ'=>'n'
        ];
        return strtr($str, $map);
    }

    private function getItemsCatalog(): array
    {
        if (self::$itemsCache !== null) {
            return self::$itemsCache;
        }
        $path = __DIR__ . '/../assets/items_data.json';
        if (file_exists($path)) {
            $raw = json_decode((string) file_get_contents($path), true);
            if (is_array($raw)) {
                $map = [];
                foreach ($raw as $item) {
                    $map[(int) $item['id']] = $item;
                }
                self::$itemsCache = $map;
                return self::$itemsCache;
            }
        }
        return [];
    }

    private function getLogs(string $type, int $page): array
    {
        $page = max(1, $page);
        $perPage = 30;
        $offset = ($page - 1) * $perPage;
        $catalog = $this->getItemsCatalog();

        return match ($type) {
            'login' => array_map(function ($r) {
                return [
                    'id' => $r['id'],
                    'created_at' => $r['created_at'],
                    'ip_address' => $r['ip'] ?? '',
                    'username' => $r['username'] ?? '',
                    'nickname' => $r['nickname'] ?? '',
                ];
            }, $this->db->all(
                'SELECT l.id, l.created_at, l.ip, a.username, c.nickname
                 FROM login_history l
                 JOIN accounts a ON a.id = l.account_id
                 LEFT JOIN characters c ON c.id = l.character_id
                 ORDER BY l.id DESC LIMIT ? OFFSET ?',
                [$perPage, $offset]
            )),
            'recharge' => array_map(function ($r) {
                return [
                    'id' => $r['id'],
                    'created_at' => $r['created_at'],
                    'character_id' => $r['character_id'],
                    'delta_point' => $r['delta_point'],
                    'ref_type' => $r['ref'] ?: $r['reason'],
                    'nickname' => $r['nickname'] ?? '',
                    'username' => $r['username'] ?? '',
                ];
            }, $this->db->all(
                'SELECT cl.id, cl.created_at, cl.character_id, cl.delta_point, cl.ref, cl.reason, c.nickname, a.username
                 FROM cash_ledger cl
                 JOIN characters c ON c.id = cl.character_id
                 JOIN accounts a ON a.id = c.account_id
                 WHERE cl.delta_point > 0
                 ORDER BY cl.id DESC LIMIT ? OFFSET ?',
                [$perPage, $offset]
            )),
            'items' => array_map(function ($r) use ($catalog) {
                $tid = (int) $r['template_id'];
                $meta = $catalog[$tid] ?? null;
                return [
                    'id' => $r['id'],
                    'created_at' => $r['created_at'],
                    'character_id' => $r['character_id'],
                    'template_id' => $tid,
                    'name' => $meta['name'] ?? ('Template #' . $tid),
                    'count' => $r['count'],
                    'action' => $r['action'] ?? '',
                ];
            }, $this->db->all(
                'SELECT il.id, il.created_at, il.character_id, il.template_id, il.count, il.action
                 FROM item_log il
                 ORDER BY il.id DESC LIMIT ? OFFSET ?',
                [$perPage, $offset]
            )),
            default => [],
        };
    }

    private function callGm(array $server, string $path, array $form): ?string
    {
        $url = GameServers::requestUrl($server) . $path;
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => http_build_query($form),
            CURLOPT_HTTPHEADER => ['X-GM-Secret: ' . $this->secret],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 3,
            CURLOPT_TIMEOUT => 6,
        ]);
        $body = curl_exec($ch);
        $errno = curl_errno($ch);
        $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $err = curl_error($ch);
        curl_close($ch);

        if ($errno === CURLE_COULDNT_CONNECT) {
            return null; // Servidor fora
        }
        if ($errno !== 0) {
            return $err;
        }
        if ($status === 200) {
            return null;
        }
        $msg = json_decode((string) $body, true)['error'] ?? '';
        return match ($status) {
            403 => 'Segredo GM inválido',
            404 => 'Rota GM desligada',
            default => "HTTP $status $msg",
        };
    }
}
