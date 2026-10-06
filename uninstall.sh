#!/bin/sh
# ==============================================================================
# AutoWoL & Host Monitor - Desinstalador Limpo do Plugin OPNsense
# ==============================================================================
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "ERRO: Este desinstalador deve ser executado como root." >&2
    exit 1
fi

echo "Removendo Plugin AutoWoL do OPNsense..."

# Remove MVC
rm -rf /usr/local/opnsense/mvc/app/models/OPNsense/AutoWoL
rm -rf /usr/local/opnsense/mvc/app/controllers/OPNsense/AutoWoL
rm -rf /usr/local/opnsense/mvc/app/views/OPNsense/AutoWoL

# Remove Templates
rm -rf /usr/local/opnsense/service/templates/OPNsense/AutoWoL

# Remove Scripts e Ações
rm -rf /usr/local/opnsense/scripts/autowol
rm -f /usr/local/opnsense/service/conf/actions.d/actions_autowol.conf
rm -f /usr/local/etc/cron.d/autowol.cron
rm -f /usr/local/etc/rc.d/autowol
rm -f /var/run/autowol_state.json*
rm -rf /tmp/volt/* 2>/dev/null || true

echo "Deseja remover também os arquivos de configuração salvos em /usr/local/etc/autowol? [s/N]"
read -r resp
case "$resp" in
    [sS][iI][mM]|[sS])
        rm -rf /usr/local/etc/autowol
        echo "Configurações removidas."
        ;;
    *)
        echo "Configurações preservadas em /usr/local/etc/autowol."
        ;;
esac

echo "Recarregando configd..."
if service configd status >/dev/null 2>&1; then
    service configd restart
fi

echo "AutoWoL foi desinstalado com sucesso."
