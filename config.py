import os
from dataclasses import dataclass

@dataclass
class EmailConfig:
    # =========================
    # CONFIGURAÇÃO SMTP
    # =========================
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gpssa.com.br")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True") == "True"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "False") == "True"

    # =========================
    # USUÁRIO PADRÃO
    # =========================
    SMTP_USERNAME: str = os.getenv(
        "SMTP_USERNAME",
        "roosevelt.pimentel@gpssa.com.br"
    )

    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # =========================
    # EMAILS PADRÃO DO SISTEMA
    # =========================
    DEFAULT_FROM_EMAIL: str = os.getenv(
        "DEFAULT_FROM_EMAIL",
        "roosevelt.pimentel@gpssa.com.br"
    )

    ADMIN_EMAIL: str = os.getenv(
        "ADMIN_EMAIL",
        "roosevelt.pimentel@gpssa.com.br"
    )


# Instância global para importar no projeto
email_config = EmailConfig()
