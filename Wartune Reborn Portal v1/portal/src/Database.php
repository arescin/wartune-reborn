<?php
declare(strict_types=1);

/** PDO para o banco compartilhado com o servidor do jogo. As tabelas são criadas pelo servidor. */
final class Database
{
    public readonly PDO $pdo;

    public function __construct(string $dsn, ?string $user, ?string $password)
    {
        $this->pdo = new PDO($dsn, $user, $password, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_TIMEOUT => 5, // SQLite: espera o servidor do jogo liberar a escrita
        ]);
        if (str_starts_with($dsn, 'sqlite:')) {
            $this->pdo->exec('PRAGMA foreign_keys = ON');
        }
    }

    /** Datas no banco são UTC, formato que o SQLAlchemy lê nos três bancos. */
    public static function now(int $plusSeconds = 0): string
    {
        return gmdate('Y-m-d H:i:s', time() + $plusSeconds);
    }

    public function one(string $sql, array $params = []): ?array
    {
        $stmt = $this->pdo->prepare($sql);
        $stmt->execute($params);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    public function all(string $sql, array $params = []): array
    {
        $stmt = $this->pdo->prepare($sql);
        $stmt->execute($params);
        return $stmt->fetchAll();
    }

    public function run(string $sql, array $params = []): void
    {
        $this->pdo->prepare($sql)->execute($params);
    }
}
