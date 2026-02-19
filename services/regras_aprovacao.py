import os
from config import email_config


def _to_upper(v) -> str:
    return str(v or "").strip().upper()


def _montar_email_por_nome(nome: str, dominio: str | None = None) -> str:
    """
    Regra simples temporária:
    "João da Silva" -> "joao.da.silva@dominio"

    Quando você tiver a lista oficial (nome -> email), trocamos por lookup seguro.
    """
    dominio = dominio or os.getenv("EMAIL_DOMAIN", "empresa.com")

    nome = (nome or "").strip().lower()
    nome = " ".join(nome.split())
    nome = nome.replace(" ", ".")

    return f"{nome}@{dominio}" if nome else ""


def identificar_destinatario(linha) -> list[str]:
    # ✅ colunas já estão normalizadas pela leitura_planilha.py
    etapa = _to_upper(linha.get("STATUS ATUAL"))
    status_validacao = _to_upper(linha.get("STATUS VALIDACAO"))

    # Só envia se estiver pendente ou em andamento
    if status_validacao not in ["PENDENTE", "EM ANDAMENTO"]:
        return []

    # Diretoria
    if "DIRETORIA DE SISTEMAS" in etapa:
        return list(email_config.DIRETORIA_SISTEMAS)

    if "DIRETORIA DE APOIO" in etapa:
        return list(email_config.DIRETORIA_APOIO)

    # Liderança
    if "LIDER" in etapa:
        lider = linha.get("LIDER USUARIO DO ACESSO")
        email = _montar_email_por_nome(lider)
        return [email] if email else []

    # Governança
    if "GOVERNANCA" in etapa or "GOVERNANÇA" in etapa:
        return list(email_config.GOVERNANCA_TI)

    # Área responsável
    if "AREA RESPONSAVEL" in etapa or "ÁREA RESPONSÁVEL" in etapa:
        responsavel = linha.get("USUARIO RESPONSAVEL")
        email = _montar_email_por_nome(responsavel)
        return [email] if email else []

    return []
