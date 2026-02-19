import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class EmailConfig:
    # ======================================================
    # 🔹 CONFIGURAÇÃO SMTP
    # ======================================================
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gpssa.com.br")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True") == "True"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "False") == "True"

    # ======================================================
    # 🔹 USUÁRIO PADRÃO
    # ======================================================
    SMTP_USERNAME: str = os.getenv(
        "SMTP_USERNAME",
        "roosevelt.pimentel@gpssa.com.br"
    )

    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # ======================================================
    # 🔹 EMAIL PADRÃO DO SISTEMA
    # ======================================================
    DEFAULT_FROM_EMAIL: str = os.getenv(
        "DEFAULT_FROM_EMAIL",
        "roosevelt.pimentel@gpssa.com.br"
    )

    ADMIN_EMAIL: str = os.getenv(
        "ADMIN_EMAIL",
        "roosevelt.pimentel@gpssa.com.br"
    )

    # ======================================================
    # 🔹 EMAILS FIXOS DE APROVAÇÃO
    # ======================================================
    GOVERNANCA_TI: tuple[str, ...] = (
        os.getenv("EMAIL_GOV_LUCAS", "lucas@empresa.com"),
        os.getenv("EMAIL_GOV_LAISA", "laisa@empresa.com"),
        os.getenv("EMAIL_GOV_KLEYTON", "kleyton@empresa.com"),
    )

    DIRETORIA_SISTEMAS: tuple[str, ...] = (
        os.getenv("EMAIL_DIR_SISTEMAS", "bahia@empresa.com"),
    )

    DIRETORIA_APOIO: tuple[str, ...] = (
        os.getenv("EMAIL_DIR_APOIO", "adriana@empresa.com"),
    )


# Instância global
email_config = EmailConfig()
