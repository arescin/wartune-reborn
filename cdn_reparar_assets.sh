#!/bin/sh
# Restaura, direto da origem da 7road, os assets que o espelho local guardou corrompidos.
#
# Todo arquivo que o Loading.swf consome chega com 37 bytes na frente: "road7" mais 32
# caracteres com o MD5 do conteudo. O MD5Installer descarta esse cabecalho antes do
# loadBytes, entao um arquivo cru entra no player 37 bytes menor e simplesmente nao abre
# - sem erro, sem log, a cena fica preta.
#
# Dois defeitos distintos aparecem no espelho e os dois precisam de tratamento:
#   1. o arquivo em res134 esta cru, truncado ou com o corpo adulterado;
#   2. o arquivo em s134 esta corrompido e, como /game/ serve s134 primeiro, ele encobre
#      a copia boa de res134 - conferir so o cabecalho nao basta, o corpo tambem mente.
#
# Roda no arranque do container, antes do nginx, porque o espelho vive num bind mount do
# host e nao ha outro caminho de escrita. Nunca impede a subida: se a origem estiver fora
# do ar o arquivo antigo continua sendo servido.

RES=/opt/wartune-cdn/res134-bmclas-sq.7road.net
TPL=/opt/wartune-cdn/s134-bmclas-sq.7road.net
ORIGEM=https://res134-bmclas-sq.7road.net

valido() {
    [ -f "$1" ] || return 1
    [ "$(head -c 5 "$1")" = "road7" ] || return 1
    [ "$(head -c 37 "$1" | tail -c 32)" = "$2" ] || return 1
    [ "$(tail -c +38 "$1" | md5sum | cut -d' ' -f1)" = "$2" ] || return 1
}

restaurar() {
    esperado="$2"

    sombra="$TPL/$1"
    if [ -f "$sombra" ] && ! valido "$sombra" "$esperado"; then
        mv "$sombra" "$sombra.corrompido"
        echo "reparar-assets: $1 encobria res134 a partir de s134, movido para .corrompido"
    fi

    alvo="$RES/$1"
    if valido "$alvo" "$esperado"; then
        return
    fi
    mkdir -p "$(dirname "$alvo")"
    temp="$alvo.novo"
    if ! wget -q -T 60 --no-check-certificate -O "$temp" "$ORIGEM/$1"; then
        rm -f "$temp"
        echo "reparar-assets: $1 indisponivel na origem"
        return
    fi
    if ! valido "$temp" "$esperado"; then
        rm -f "$temp"
        echo "reparar-assets: $1 veio da origem sem bater com o manifesto"
        return
    fi
    mv "$temp" "$alvo"
    echo "reparar-assets: $1 restaurado"
}

restaurar ui/zh_cn/swf/castle.swf 4cb4fa48a90671b48e2ba0a49ed4c75b
restaurar ui/zh_cn/swf/castlemap1.swf 0d4a1f810236fd533bc1226a509a8d67
restaurar ui/zh_cn/swf/castlemap2.swf 951d7054cb165a69e86eb95eaa7f40ba
restaurar ui/zh_cn/xml/xml.png d794962eefaa35247e74dbc993459aad
restaurar ui/zh_cn/swf/novice.swf 4da735853902adcfa96f37b638d7ac87
# O manifesto pede b97b135c9d304f891642d80de4440ea4 para 9.png, mas a origem so tem a
# revisao abaixo e o espelho nao tem copia nenhuma. Sem o arquivo o Nginx devolve o
# empty.png com HTTP 200 e o cliente carrega 37 bytes de lixo; com a revisao da origem o
# MD5 apenas diverge do cache e o Loading.swf rebaixa, que e o mal menor.
restaurar 9.png eff1749b2e3221b792637af6534b915d

exec nginx -g 'daemon off;'
