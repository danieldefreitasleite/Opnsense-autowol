# OPNsense AutoWoL & Host Monitor (Plugin Web Oficial) 🚀

> **Plugin Nativo para OPNsense**: Adiciona o menu **Services -> AutoWoL** na interface Web oficial do OPNsense. Permite cadastrar servidores e máquinas, checar se estão ligadas, enviar **Wake-on-LAN** automaticamente, verificar inicialização e disparar alertas via **WhatsApp**, **Telegram**, **Email**, **SMS** ou **Webhooks**.  
> **100% Gerenciado pela Web**: Sem necessidade de editar arquivos no terminal (`nano`) ou navegar para outras telas de agendamento (o plugin configura o cron e o sistema automaticamente ao clicar em *Salvar e Aplicar*).

---

## 🖥️ Como Funciona na Interface Web

Ao instalar, o plugin adiciona a opção **AutoWoL** dentro do menu **Services** do seu OPNsense com 4 abas integradas:

1. **🖥️ Máquinas / Servidores**:
   - Tabela interativa para Adicionar (`+`), Editar e Excluir computadores monitorados.
   - Botão **Ligar Agora (WoL)** para acordar qualquer máquina com 1 clique.
   - Configurações por host: IP, MAC, Método (Ping ICMP / Porta TCP / Ambos), tentativas máximas e tempo de boot.
2. **⚙️ Configurações Gerais**:
   - Chave de ativação do AutoWoL (*Enable/Disable*).
   - Intervalo de checagem em minutos (ex: a cada 2 ou 5 min) — **o plugin cria e ativa a regra de Cron no sistema automaticamente**.
   - Definições globais de tempo de boot, limite de tentativas e cooldown anti-flood de alertas.
3. **🔔 Canais de Notificação**:
   - Campos visuais para **WhatsApp** (CallMeBot gratuito, Evolution API, Z-API, Twilio).
   - Campos visuais para **Telegram** (Bot Token e Chat ID).
   - Campos visuais para **Email SMTP** (Gmail, Outlook, servidores locais com TLS/SSL).
   - Campos visuais para **SMS** (Twilio ou Gateways HTTP).
   - Campos visuais para **Webhooks** (Discord com cartões coloridos, Ntfy.sh no celular, JSON).
   - Menu **Testar Disparo de Alerta**: botão na própria tela para enviar uma mensagem de teste em qualquer canal sem precisar reiniciar nada.
4. **📊 Status em Tempo Real**:
   - Acompanhamento do status de cada máquina (`ONLINE`, `WAKING` ou `ALERTED`), número de tentativas e data da última conexão.

---

## ⚡ Instalação em 1 Comando no OPNsense

No terminal SSH do seu OPNsense (como `root`), execute:

```sh
cd /tmp
git clone https://github.com/danieldefreitasleite/Opnsense-autowol.git autowol
cd autowol
chmod +x install.sh
./install.sh
```

Pronto! Atualize a página do seu navegador: o menu **Services -> AutoWoL** já estará visível e pronto para uso imediato.

---

## 📁 Estrutura do Plugin MVC

```
Opnsense-autowol/
├── Makefile                               # Compilação e empacotamento FreeBSD (.pkg)
├── install.sh                             # Instalador de 1 comando para o OPNsense
├── uninstall.sh                           # Desinstalador limpo
├── README.md                              # Este documento
├── opnsense/
│   ├── mvc/app/
│   │   ├── models/OPNsense/AutoWoL/       # Modelo de dados XML, Menu.xml e ACL.xml
│   │   ├── controllers/OPNsense/AutoWoL/  # Controladores PHP (Index, Settings, Host, Service)
│   │   │   └── forms/                     # Formulários visuais (general.xml, dialogHost.xml, notifications.xml)
│   │   └── views/OPNsense/AutoWoL/        # Telas Web Volt (index.volt)
│   ├── service/
│   │   ├── conf/actions.d/                # Ações do Configd (check, wake, testalert, reconfigure)
│   │   └── templates/OPNsense/AutoWoL/    # Templates Jinja2 (geração automática de config e cron)
│   └── scripts/autowol/                   # Motor Python nativo (wol.py, prober.py, notifiers/)
├── doc/
│   ├── MANUAL_INSTALACAO.md               # Manual de uso na interface Web
│   └── CONFIGURACOES_ALERTAS.md           # Exemplos de setup de WhatsApp, Telegram, SMTP, etc.
└── tests/
    └── test_autowol.py                    # Testes unitários do motor Python
```

---

## 🧪 Testes Automatizados

Para testar a lógica do motor de WoL, rede e notificações:
```sh
python tests/test_autowol.py
```
*(Todos os 9 testes passam com 100% de sucesso)*.
