<?php
declare(strict_types=1);

/**
 * Gera o client/config.xml de um servidor a partir do arquivo oficial capturado.
 *
 * Troca só o necessário, com substituição de texto (o arquivo tem comentários e aspas mistas):
 * REQUEST_PATH -> servidor do jogo (endpoints dinâmicos), ResourcePath -> CDN, TEMPLATE_PATH -> site do jogo,
 * SocktPath -> socket do jogo, NODE/RSAKey -> site e chave pública daquele servidor.
 */
final class ClientConfig
{
    public function __construct(
        private readonly string $template,
        private readonly string $cdnUrl,
        private readonly string $gameUrl,
    ) {
    }

    public function render(array $server): string
    {
        $text = $this->template;
        $oldRequest = self::attr($text, 'REQUEST_PATH');
        $oldResource = self::attr($text, 'ResourcePath');
        $oldSite = self::attr($text, 'NODE', 'site');

        $text = str_replace([$oldResource, $oldRequest], [$this->cdnUrl, GameServers::requestUrl($server)], $text);
        $text = self::setAttr($text, 'TEMPLATE_PATH', 'value', $this->gameUrl . 'xml/');
        $text = self::setAttr($text, 'SocktPath', 'value', $server['public_host']);
        $text = self::setAttr($text, 'SocktPath', 'SocketPort', (string) $server['socket_port']);
        $text = self::setAttr($text, 'RSAKey', 'PublicKeyModulus', $server['rsa_modulus']);
        $text = self::setAttr($text, 'RSAKey', 'publicExponent', $server['rsa_exponent']);
        return str_replace(["'$oldSite'", "\"$oldSite\""], ["'{$server['site']}'", "\"{$server['site']}\""], $text);
    }

    private static function attr(string $text, string $tag, string $attr = 'value'): string
    {
        if (!preg_match("/<$tag\\b[^>]*?\\b$attr\\s*=\\s*([\"'])(.*?)\\1/s", $text, $m)) {
            throw new RuntimeException("config.xml modelo sem <$tag $attr=...>");
        }
        return $m[2];
    }

    private static function setAttr(string $text, string $tag, string $attr, string $value): string
    {
        return preg_replace_callback(
            "/(<$tag\\b[^>]*?\\b$attr\\s*=\\s*)([\"'])(.*?)\\2/s",
            fn(array $m) => $m[1] . $m[2] . htmlspecialchars($value, ENT_QUOTES | ENT_XML1) . $m[2],
            $text
        );
    }
}
