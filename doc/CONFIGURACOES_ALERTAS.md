# Guia de Configuração dos Canais de Alerta

O AutoWoL suporta múltiplos canais de alerta simultâneos. Você pode ativar um ou todos eles em `/usr/local/etc/autowol/config.json`.

---

## 1. WhatsApp

O AutoWoL suporta 4 provedores diferentes de WhatsApp:

### Opção A: CallMeBot (Gratuito, Rápido e Sem Servidor)
Ideal para homelabs e administradores que querem notificações imediatas sem precisar subir uma API própria.

1. Salve o número do CallMeBot na sua agenda: `+34 644 44 20 63` (ou consulte em [callmebot.com](https://www.callmebot.com/blog/free-api-whatsapp-messages/)).
2. Envie a seguinte mensagem pelo WhatsApp para ele:
   `I allow callmebot to send me messages`
3. O bot responderá com a sua **API Key** (ex: `123456`).
4. Configure no `config.json`:
```json
"whatsapp": {
  "enabled": true,
  "provider": "callmebot",
  "phone": "+5511999999999",
  "apikey": "123456"
}
```

---

### Opção B: Evolution API (Self-Hosted)
Se você já possui uma instância da [Evolution API](https://evolution-api.com/) no seu homelab ou VPS:

```json
"whatsapp": {
  "enabled": true,
  "provider": "evolution_api",
  "server_url": "https://evolution.seuhomelab.com",
  "instance": "nome-da-instancia",
  "apikey": "SEU_API_KEY_GLOBAL_OU_DA_INSTANCIA",
  "phone": "5511999999999"
}
```

---

### Opção C: Z-API
Para contas na plataforma comercial Z-API:

```json
"whatsapp": {
  "enabled": true,
  "provider": "z_api",
  "instance": "SUA_INSTANCIA",
  "token": "SEU_TOKEN",
  "client_token": "OPCIONAL_CLIENT_TOKEN",
  "phone": "5511999999999"
}
```

---

### Opção D: Twilio WhatsApp
Para contas corporativas na Twilio:

```json
"whatsapp": {
  "enabled": true,
  "provider": "twilio",
  "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "auth_token": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
  "from_number": "+14155238886",
  "phone": "+5511999999999"
}
```

---

## 2. Telegram Bot (Altamente Recomendado)

O Telegram é 100% gratuito, sem limite de envio e extremamente confiável para alertas de rede.

### Como criar o Bot e pegar as credenciais:
1. No Telegram, converse com o [@BotFather](https://t.me/BotFather) e envie `/newbot`.
2. Diga o nome e o username do bot (ex: `MeuOpnsenseAlertBot`).
3. O BotFather fornecerá o **Token da API** (ex: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`).
4. Inicie uma conversa com o seu novo bot clicando em **Start / Começar**.
5. Para descobrir o seu `chat_id`, converse com o bot [@userinfobot](https://t.me/userinfobot) ou [@RawDataBot](https://t.me/RawDataBot) que ele informará o seu ID numérico (ex: `123456789`).
6. Configure no `config.json`:
```json
"telegram": {
  "enabled": true,
  "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
  "chat_id": "123456789",
  "parse_mode": "HTML"
}
```

---

## 3. Email (SMTP Autenticado / TLS / SSL)

Suporte nativo a Gmail, Outlook, Amazon SES ou servidor SMTP local.

### Exemplo Gmail (Requer "Senha de App"):
> *No Google, acesse sua conta -> Segurança -> Verificação em 2 etapas -> Senhas de aplicativo -> Crie uma senha para "AutoWoL".*

```json
"email": {
  "enabled": true,
  "host": "smtp.gmail.com",
  "port": 587,
  "use_tls": true,
  "use_ssl": false,
  "username": "seu.email@gmail.com",
  "password": "abcd efgh ijkl mnop",
  "from_addr": "OPNsense AutoWoL <seu.email@gmail.com>",
  "to_addrs": ["admin@seuhomelab.com", "backup@seuhomelab.com"]
}
```

### Exemplo Servidor Interno / Relé sem Autenticação:
```json
"email": {
  "enabled": true,
  "host": "192.168.1.5",
  "port": 25,
  "use_tls": false,
  "use_ssl": false,
  "username": "",
  "password": "",
  "from_addr": "opnsense@lan.local",
  "to_addrs": ["admin@lan.local"]
}
```

---

## 4. SMS

### Opção A: Twilio SMS
```json
"sms": {
  "enabled": true,
  "provider": "twilio",
  "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "auth_token": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
  "from_number": "+15551234567",
  "phone": "+5511999999999"
}
```

### Opção B: Gateway HTTP Customizado (Modem GSM / App Android)
Caso você use um aplicativo Android SMS Gateway ou um modem 4G local com API:
```json
"sms": {
  "enabled": true,
  "provider": "http_gateway",
  "url": "http://192.168.1.200:8080/send?number={phone}&message={message}",
  "method": "GET",
  "phone": "5511999999999"
}
```

---

## 5. Webhooks (Discord, Ntfy.sh, n8n, Home Assistant)

### Discord:
1. No seu servidor do Discord, vá nas configurações do canal -> Integrações -> Webhooks -> Criar Webhook.
2. Copie a URL do Webhook e configure:
```json
"webhook": {
  "enabled": true,
  "type": "discord",
  "url": "https://discord.com/api/webhooks/123456789/abcdefgh"
}
```

### Ntfy.sh (Push notification gratuito no celular):
```json
"webhook": {
  "enabled": true,
  "type": "ntfy",
  "topic": "meu-canal-secreto-opnsense"
}
```
*(Basta instalar o app Ntfy no Android ou iOS e se inscrever no tópico configurado).*
