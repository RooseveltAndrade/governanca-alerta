import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class EmailConfig:
    # ======================================================
    # 🔹 CONFIGURAÇÃO SMTP
    # ======================================================
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True") == "True"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "False") == "True"

    # ======================================================
    # 🔹 USUÁRIO PADRÃO
    # ======================================================
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")

    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # ======================================================
    # 🔹 EMAIL PADRÃO DO SISTEMA
    # ======================================================
    DEFAULT_FROM_EMAIL: str = os.getenv("DEFAULT_FROM_EMAIL", "")

    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")

    # ======================================================
    # 🔹 EMAILS FIXOS DE APROVAÇÃO (REGRAS OFICIAIS)
    # ======================================================

    # ✅ GOVERNANÇA - TI
    GOVERNANCA_TI: tuple[str, ...] = (
        os.getenv("EMAIL_GOV_LAIS", ""),
        os.getenv("EMAIL_GOV_LUCAS", ""),
    )

    # ✅ DIRETORIA (ambos até exportação individual)
    DIRETORIA_SISTEMAS: tuple[str, ...] = (
        os.getenv("EMAIL_DIR_ADRIANA", ""),
    )

    DIRETORIA_APOIO: tuple[str, ...] = (
        os.getenv("EMAIL_DIR_THIAGO", ""),
    )


# Instância global
email_config = EmailConfig()