import os
from config import email_config


def _to_upper(v) -> str:
    return str(v or "").strip().upper()


def _montar_email_por_nome(nome: str, dominio: str | None = None) -> str:
    """
    Regra temporária:
    'JOAO DA SILVA' -> 'joao.da.silva@dominio'
    Quando você tiver a lista oficial (nome->email), trocamos por lookup seguro.
    """
    dominio = dominio or os.getenv("EMAIL_DOMAIN", "empresa.com")

    nome = (nome or "").strip().lower()
    nome = " ".join(nome.split())
    nome = nome.replace(" ", ".")
    return f"{nome}@{dominio}" if nome else ""


def identificar_destinatario(linha) -> list[str]:
    """
    Espera colunas normalizadas (via leitura_planilha.py):
    - STATUS ATUAL
    - STATUS VALIDACAO
    - LIDER USUARIO DO ACESSO
    - USUARIO RESPONSAVEL
    """

    etapa = _to_upper(linha.get("STATUS ATUAL"))
    status_validacao = _to_upper(linha.get("STATUS VALIDACAO"))

    # Só envia se estiver pendente ou em andamento
    if status_validacao not in ["PENDENTE", "EM ANDAMENTO"]:
        return []

    # =========================
    # GOVERNANÇA
    # =========================
    if "GOVERNANCA" in etapa:
        # pega tanto: "PENDENTE GOVERNANÇA - TI" quanto "INATIVAR PENDENTE GOVERNANÇA - TI"
        return list(email_config.GOVERNANCA_TI)

    # =========================
    # LÍDER
    # =========================
    if "LIDER" in etapa:
        lider = linha.get("LIDER USUARIO DO ACESSO")
        email = _montar_email_por_nome(lider)
        return [email] if email else []

    # =========================
    # ÁREA RESPONSÁVEL
    # =========================
    if "AREA" in etapa:
        # pega tanto: "PENDENTE ÁREA RESPONSÁVEL" quanto "INATIVAR PENDENTE PARA ÁREA"
        responsavel = linha.get("USUARIO RESPONSAVEL")  # na planilha real existe "USUÁRIO RESPONSÁVEL"
        email = _montar_email_por_nome(responsavel)
        return [email] if email else []

    # =========================
    # DIRETORIA
    # =========================
    if "DIRETORIA" in etapa:
        # IMPORTANTE:
        # No Excel exportado, não vem "Sistemas" vs "Apoio", vem só "PENDENTE DIRETORIA".
        # Então, por enquanto, mandamos para ambos (Bahia + Adriana).
        # Quando você confirmar como distinguir, refinamos.
        return list(email_config.DIRETORIA_SISTEMAS) + list(email_config.DIRETORIA_APOIO)

    return []
