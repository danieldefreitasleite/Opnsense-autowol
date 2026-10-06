#!/bin/sh
# ==============================================================================
# AutoWoL & Host Monitor - Instalador Oficial do Plugin MVC para OPNsense
# ==============================================================================
set -e

echo "====================================================="
echo "   Instalando Plugin AutoWoL no OPNsense (Web GUI)   "
echo "====================================================="

# 1. Verifica privilégios de root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERRO: Este instalador deve ser executado como root." >&2
    exit 1
fi

# 2. Localiza o Python 3
PYTHON_BIN=""
if [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=$(command -v python3)
else
    echo "ERRO: Python 3 não foi encontrado. O OPNsense requer Python 3." >&2
    exit 1
fi
echo "✓ Python detectado: $PYTHON_BIN"

# 3. Diretório base da instalação
BASE_DIR=$(cd "$(dirname "$0")" && pwd)

# 4. Criação dos diretórios do sistema
echo "Criando diretórios do sistema e MVC..."
mkdir -p /usr/local/etc/autowol
mkdir -p /usr/local/etc/cron.d
mkdir -p /usr/local/etc/rc.d
mkdir -p /usr/local/opnsense/scripts/autowol/notifiers
mkdir -p /usr/local/opnsense/service/conf/actions.d
mkdir -p /usr/local/opnsense/service/templates/OPNsense/AutoWoL
mkdir -p /usr/local/opnsense/mvc/app/models/OPNsense/AutoWoL/Menu
mkdir -p /usr/local/opnsense/mvc/app/models/OPNsense/AutoWoL/ACL
mkdir -p /usr/local/opnsense/mvc/app/controllers/OPNsense/AutoWoL/Api
mkdir -p /usr/local/opnsense/mvc/app/controllers/OPNsense/AutoWoL/forms
mkdir -p /usr/local/opnsense/mvc/app/views/OPNsense/AutoWoL

# 5. Instalação dos Scripts de Backend
echo "Instalando motor backend AutoWoL..."
cp -R "$BASE_DIR"/opnsense/scripts/autowol/* /usr/local/opnsense/scripts/autowol/
chmod +x /usr/local/opnsense/scripts/autowol/*.py

# 6. Instalação das Ações do Configd
echo "Registrando ações no subsistema configd..."
cp "$BASE_DIR"/opnsense/service/conf/actions.d/actions_autowol.conf /usr/local/opnsense/service/conf/actions.d/
chmod 644 /usr/local/opnsense/service/conf/actions.d/actions_autowol.conf

# 7. Instalação dos Templates Jinja2 (Geração automática de config e cron)
echo "Instalando templates automáticos..."
cp -R "$BASE_DIR"/opnsense/service/templates/OPNsense/AutoWoL/* /usr/local/opnsense/service/templates/OPNsense/AutoWoL/

# 8. Instalação dos Modelos MVC (Model, Menu e ACL)
echo "Instalando modelos MVC, Menu e ACL..."
cp "$BASE_DIR"/opnsense/mvc/app/models/OPNsense/AutoWoL/AutoWoL.php /usr/local/opnsense/mvc/app/models/OPNsense/AutoWoL/
cp "$BASE_DIR"/opnsense/mvc/app/models/OPNsense/AutoWoL/AutoWoL.xml /usr/local/opnsense/mvc/app/models/OPNsense/AutoWoL/
cp "$BASE_DIR"/opnsense/mvc/app/models/OPNsense/AutoWoL/Menu/Menu.xml /usr/local/opnsense/mvc/app/models/OPNsense/AutoWoL/Menu/
cp "$BASE_DIR"/opnsense/mvc/app/models/OPNsense/AutoWoL/ACL/ACL.xml /usr/local/opnsense/mvc/app/models/OPNsense/AutoWoL/ACL/

# 9. Instalação dos Controladores e Formulários Web
echo "Instalando controladores e formulários da interface Web..."
cp "$BASE_DIR"/opnsense/mvc/app/controllers/OPNsense/AutoWoL/IndexController.php /usr/local/opnsense/mvc/app/controllers/OPNsense/AutoWoL/
cp "$BASE_DIR"/opnsense/mvc/app/controllers/OPNsense/AutoWoL/Api/*.php /usr/local/opnsense/mvc/app/controllers/OPNsense/AutoWoL/Api/
cp "$BASE_DIR"/opnsense/mvc/app/controllers/OPNsense/AutoWoL/forms/*.xml /usr/local/opnsense/mvc/app/controllers/OPNsense/AutoWoL/forms/

# 10. Instalação das Views Volt (Telas do OPNsense)
echo "Instalando telas Web (Volt)..."
cp "$BASE_DIR"/opnsense/mvc/app/views/OPNsense/AutoWoL/index.volt /usr/local/opnsense/mvc/app/views/OPNsense/AutoWoL/

# 11. Serviço rc.d
cp "$BASE_DIR"/etc/rc.d/autowol /usr/local/etc/rc.d/autowol
chmod +x /usr/local/etc/rc.d/autowol

# 12. Arquivo modelo inicial de configuração
cp "$BASE_DIR"/etc/autowol/config.sample.json /usr/local/etc/autowol/config.sample.json
if [ ! -f /usr/local/etc/autowol/config.json ] || grep -q "Servidor NAS / Storage" /usr/local/etc/autowol/config.json 2>/dev/null; then
    cp /usr/local/etc/autowol/config.sample.json /usr/local/etc/autowol/config.json
    chmod 600 /usr/local/etc/autowol/config.json
fi

# Limpa estados de máquinas de exemplo anteriores
rm -f /var/run/autowol_state.json*

# 13. Limpeza de cache e reinicialização de serviços
echo "Limpando caches de Volt e recarregando serviços..."
rm -rf /tmp/volt/* 2>/dev/null || true

if service configd status >/dev/null 2>&1; then
    service configd restart
elif [ -x "/usr/local/etc/rc.d/configd" ]; then
    /usr/local/etc/rc.d/configd restart
fi

# Recarrega templates do OPNsense
if [ -x "/usr/local/bin/configctl" ]; then
    /usr/local/bin/configctl template reload OPNsense/AutoWoL >/dev/null 2>&1 || true
fi

# Atualiza permissões e cache de navegação do OPNsense
if [ -x "/usr/local/etc/rc.php_ini_setup" ]; then
    /usr/local/etc/rc.php_ini_setup >/dev/null 2>&1 || true
fi

echo ""
echo "================================================================"
echo "   ✓ PLUGIN AUTOWOL INSTALADO COM SUCESSO NO OPNSENSE!          "
echo "================================================================"
echo ""
echo "ONDE ENCONTRAR NO NAVEGADOR:"
echo "1. Abra a interface web do OPNsense."
echo "2. No menu lateral, acesse: Services -> AutoWoL"
echo "3. Você terá acesso à tela completa para:"
echo "   • Cadastrar, editar e excluir máquinas monitoradas (+ Adicionar)."
echo "   • Ligar qualquer máquina imediatamente com um clique no botão WoL."
echo "   • Ativar e configurar WhatsApp, Telegram, Email, SMS ou Webhook."
echo "   • Testar os alertas diretamente na tela com botão 'Testar'."
echo "   • Clicar em 'Salvar e Aplicar Alterações' (o cron do sistema"
echo "     será configurado e ativado automaticamente sem mexer no terminal)."
echo "================================================================"
