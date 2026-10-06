# Manual de Instalação e Uso: Plugin Web AutoWoL para OPNsense

Este manual orienta a instalação e uso do **AutoWoL** como um **Plugin Web completo** dentro do menu **Services** do OPNsense.

---

## 1. Instalação no OPNsense

Acesse o terminal do OPNsense (via SSH como `root`) apenas para rodar o instalador automatizado:

```sh
cd /tmp
git clone https://github.com/danieldefreitasleite/Opnsense-autowol.git autowol
cd autowol
chmod +x install.sh
./install.sh
```

O instalador registra automaticamente:
- O novo menu **Services -> AutoWoL** na interface Web.
- As telas Volt e controladores MVC.
- Os modelos e formulários de configuração.
- As permissões de acesso (ACL).
- O motor de backend em Python nativo.
- O gerador de configuração e cron automático.

---

## 2. Como Usar na Interface Web

Abra o seu navegador e acesse o OPNsense. No menu lateral esquerdo, clique em:  
👉 **Services** -> **AutoWoL**

Você verá uma tela com 4 abas:

### Aba 1: 🖥️ Máquinas / Servidores
1. Clique no botão **+ Adicionar Máquina**.
2. Preencha os campos da janela:
   - **Nome do Host**: Identificador (ex: `Servidor NAS`, `Proxmox Homelab`, `Desktop TI`).
   - **Endereço IPv4**: IP da máquina (ex: `192.168.1.50`).
   - **Endereço MAC**: Endereço físico (ex: `00:11:32:AA:BB:CC`).
   - **Método de Checagem**:
     - *ICMP Ping*: Padrão para Linux e servidores.
     - *Porta TCP*: Recomendado para Windows (ex: informe `3389` para RDP ou `445` para SMB caso o firewall do Windows bloqueie ping).
     - *Ambos*: Tenta ping primeiro; se falhar, tenta a porta TCP antes de considerar desligado.
   - **Tentativas Específicas**: Quantas vezes tentar dar WoL antes de alertar (padrão 3).
3. Clique em **Salvar**.
4. *(Opcional)* Você pode clicar no ícone verde de **Power** na tabela para testar o envio de Wake-on-LAN imediato para qualquer computador cadastrado.

---

### Aba 2: ⚙️ Configurações Gerais
1. Marque a caixa **Ativar AutoWoL**.
2. Defina o **Intervalo de Checagem** em minutos (ex: a cada `2` ou `5` minutos).
   > **Atenção**: Você **não** precisa ir na tela de Cron do sistema. Ao salvar, o plugin cria e ativa a regra de agendamento no sistema automaticamente.
3. Configure o **Tempo de Boot** (tolerância para a máquina ligar, ex: 60 segundos).
4. Configure o **Cooldown de Alertas** (ex: 120 minutos para evitar receber mensagens repetidas da mesma máquina caída).
5. Clique em **Salvar Configurações Gerais**.

---

### Aba 3: 🔔 Canais de Notificação
1. Ative os canais desejados e preencha as credenciais:
   - **WhatsApp**:
     - Escolha entre CallMeBot (gratuito), Evolution API (servidor próprio), Z-API ou Twilio.
     - Preencha o número de telefone e chave de API.
   - **Telegram**:
     - Preencha o Token do Bot e o Chat ID.
   - **Email (SMTP)**:
     - Preencha servidor SMTP, porta, usuário, senha de app e destinatários.
   - **SMS**:
     - Preencha dados da Twilio ou a URL do seu Gateway HTTP/Modem GSM.
   - **Webhooks**:
     - Cole a URL do seu Webhook do Discord, Ntfy.sh ou JSON genérico.
2. Clique em **Salvar Notificações**.
3. Use o botão **Testar Disparo de Alerta** no canto inferior direito para validar se a mensagem chega no seu celular/email antes de colocar em produção.

---

### Aba 4: 📊 Status em Tempo Real
- Exibe o estado de cada equipamento cadastrado:
  - 🟢 **ONLINE**: Equipamento respondendo perfeitamente.
  - 🟡 **WAKING**: Equipamento desligado; pacotes de WoL foram enviados e o sistema está aguardando o tempo de boot.
  - 🔴 **ALERTED**: Equipamento não ligou após as tentativas configuradas e os alertas foram disparados.
- Use o botão **Checar Hosts Agora** no topo para forçar uma verificação manual a qualquer momento.

---

## 3. Botão "Salvar e Aplicar Alterações"

Sempre que fizer alterações nos hosts, tempos ou canais de alerta, clique no botão azul no topo da página:  
👉 **Salvar e Aplicar Alterações**

O OPNsense recarregará os templates, reescreverá a configuração interna e atualizará a rotina de cron do sistema de forma 100% transparente.
