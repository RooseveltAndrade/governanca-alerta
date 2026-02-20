📄 README.md Atualizado
# 🛡️ Governança - Alerta Automático de Aprovação

Automação para monitoramento de chamados de concessão de acesso no Portal GPS, identificando pendências de aprovação e enviando alertas automáticos para os responsáveis (Líder, Governança ou Diretoria).

---

## 🎯 Objetivo do Projeto

Automatizar o processo de:

1. Acessar o Portal GPS
2. Exportar planilha de chamados pendentes
3. Identificar responsáveis pela aprovação
4. Mapear nome → email
5. Notificar automaticamente via Outlook (e futuramente Teams)
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
│   └── envio_email.py            # Envio via SMTP (stub por enquanto)
│
├── planilhas/                    # Pasta onde os arquivos são organizados
│   └── fev/
│       └── 19-02-2026/
│
├── config.py                     # Configurações SMTP e emails fixos
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
```nginx
E não esquece de garantir que a venv não vai pro Git:

**.gitignore**
```gitignore
.venv/
venv/
.env
__pycache__/
*.pyc

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

## 📧 Envio de Email

Atualmente o envio está em modo simulação (DRY_RUN=True).

Para ativar envio real:

No .env:

```ini
DRY_RUN=False
```

SMTP configurado via config.py.

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

## 👨‍💻 Desenvolvedor

Roosevelt Andrade (Projeto interno de automação de Governança de TI).

