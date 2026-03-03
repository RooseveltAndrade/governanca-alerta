📄 README.md Atualizado
# 🛡️ Governança - Alerta Automático de Aprovação


Automação para monitoramento de chamados de concessão de acesso no Portal GPS, identificando pendências de aprovação e enviando alertas automáticos para os responsáveis (Líder, Governança ou Diretoria) via Microsoft Graph API (M365). O sistema também suporta fallback para SMTP/Outlook e possui alertas automáticos de falha.

---

## 🎯 Objetivo do Projeto

Automatizar o processo de:

1. Acessar o Portal GPS
2. Exportar planilha de chamados pendentes
3. Identificar responsáveis pela aprovação
4. Mapear nome → email
5. Notificar automaticamente via Microsoft Graph (e-mail corporativo M365)
6. (Opcional) Notificar via Outlook/SMTP se configurado
7. (Opcional) Testes de integração com Teams (ver limitações)
6. Repetir alertas enquanto o chamado permanecer pendente

---

## 🔄 Fluxo da Automação

```text
Selenium → Exporta Excel → Organiza pasta (mês/dia)
          ↓
Leitura da Planilha
          ↓
Identificação de Status
          ↓
Mapeamento Nome → Email
          ↓
Envio de Notificação
```

## 📂 Estrutura do Projeto

```bash
governanca-alerta/
│
├── automation/
│   └── portal_selenium.py        # Automação do Portal via Selenium
│
├── services/
│   ├── leitura_planilha.py       # Normalização e leitura do Excel
│   ├── regras_aprovacao.py       # Regras de identificação do responsável
│   ├── diretorio_emails.py       # Match nome → email
│   └── envio_email.py            # Envio via Microsoft Graph, SMTP ou Outlook
│
├── planilhas/                    # Pasta onde os arquivos são organizados
│   └── fev/
│       └── 19-02-2026/
│
├── config.py                     # Configurações de e-mail (Graph, SMTP, Outlook) e emails fixos
├── main.py                       # Orquestrador principal
├── .env                          # Variáveis sensíveis
└── requirements.txt
```
## 🐍 Ambiente Virtual (venv)

Recomendado usar um ambiente virtual para isolar dependências.

### Windows (PowerShell)
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Windows (CMD)
```bat
python -m venv .venv
.\.venv\Scripts\activate.bat
pip install -r requirements.txt
```
## Linux/macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
## Para sair do ambiente virtual:
```bash
deactivate
```
---
## 📥 Download Automático

A automação:

1 - Acessa o Portal GPS

2 - Filtra por "PENDENTES"

3 - Exporta Excel

4 - Aguarda conclusão do download

5 - Organiza o arquivo em:
```php-template
planilhas/<mes>/<dia-mes-ano>/
```

Exemplo:
```makefile
C:\governanca-alerta\planilhas\fev\19-02-2026\
```
---
## 🧠 Regras de Aprovação

A identificação é feita com base em:

STATUS ATUAL

STATUS VALIDAÇÃO

Fluxo de Responsáveis:

Status Contém	Destinatário
GOVERNANÇA	Equipe Governança TI
LÍDER	Líder do usuário
ÁREA RESPONSÁVEL	Responsável da área
DIRETORIA	Diretores (Sistemas + Apoio)

⚠️ Somente chamados com STATUS VALIDAÇÃO = PENDENTE ou EM ANDAMENTO são notificados.

---


## 📧 Envio de E-mail (Microsoft 365)

O envio principal é feito via Microsoft Graph API, utilizando uma conta de serviço M365 configurada no Azure AD.

**Configuração obrigatória no .env:**

```
EMAIL_PROVIDER=graph
M365_TENANT_ID=...
M365_CLIENT_ID=...
M365_CLIENT_SECRET=...
M365_SENDER_UPN=governanca.ti@gpssa.com.br
DRY_RUN=False
```

**Permissões necessárias no Azure AD:**
- Mail.Send (application)
- User.Read.All (application)

**Fallback:**
- Se EMAIL_PROVIDER=outlook, usa Outlook Desktop local (requer Outlook instalado e sessão ativa).
- Se EMAIL_PROVIDER=smtp, usa SMTP tradicional (requer SMTP_USERNAME/SMTP_PASSWORD).

**Modo de Teste:**
- Para simular sem enviar e-mails reais, use `DRY_RUN=True`.
- Para redirecionar todos os envios para um e-mail de teste, use `SAFE_TEST_TO=seu@email.com`.

**Alerta de Falha:**
- Se algum e-mail não for enviado, um alerta automático é enviado para governanca.ti@gpssa.com.br com o motivo do erro.

**Limitações Teams:**
- Testes de envio para Teams 1:1 requerem permissões delegadas ou bot registrado. O envio para canais pode ser feito via webhook (não implementado por padrão).

---

## 🔐 Segurança

1 - Senhas ficam no .env

2 - .env não deve ser versionado

3 - Emails fixos centralizados no config.py

4 - Nenhum email hardcoded nas regras

---

## 📦 Dependências

Instalar com:

```bash
pip install -r requirements.txt
```
Principais:

1 - selenium

2 - pandas

3 - xlrd (para leitura de .xls)

4 - python-dotenv

5 - webdriver-manager

---

## 🚀 Executar

```bash
python main.py
```

---

## 🕒 Automação no Windows Server (Task Scheduler)

Para não rodar manualmente no terminal, use os scripts em `scripts/`:

- `scripts/run_main.ps1`: executa `main.py` com Python da `.venv` e grava log em `logs/`
- `scripts/install_task.ps1`: cria tarefa agendada diária no Windows

### 1) Testar execução do script (manual)

No PowerShell, na pasta do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_main.ps1
```


### 2) Criar as tarefas agendadas (09:00 e 14:00)

O script já está preparado para criar duas tarefas diárias:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_task.ps1
```

Isso criará:
- GovernancaAlertaAcessos_09h (09:00)
- GovernancaAlertaAcessos_14h (14:00)

Se quiser rodar com uma conta de serviço específica, adicione os parâmetros -RunAsUser e -RunAsPassword.


### 3) Validar se as tarefas foram criadas

```powershell
schtasks /Query /FO LIST | Select-String "GovernancaAlertaAcessos"
```


### 4) Rodar imediatamente (teste)

```powershell
schtasks /Run /TN "GovernancaAlertaAcessos_09h"
schtasks /Run /TN "GovernancaAlertaAcessos_14h"
```

### 5) Logs da execução

Os logs ficam em:

```text
logs/main_yyyyMMdd_HHmmss.log
```


### 6) Alterar horários ou remover tarefas

- Para alterar horários, edite o script `install_task.ps1` e execute novamente.
- Para remover tarefas:

```powershell
schtasks /Delete /TN "GovernancaAlertaAcessos_09h" /F
schtasks /Delete /TN "GovernancaAlertaAcessos_14h" /F
```

---

## 👨‍💻 Desenvolvedor


Roosevelt Andrade (Projeto interno de automação de Governança de TI).

---

## 📝 Notas Finais

- O sistema está preparado para produção, com logs detalhados, fallback de envio e alertas automáticos de falha.
- Testes com Teams 1:1 dependem de permissões delegadas ou bot (não suportado por padrão pelo Graph API em modo aplicação).
- Para dúvidas, consulte o código ou abra uma issue.

