# services/regras_aprovacao.py
from __future__ import annotations

import unicodedata
from typing import Any

from config import email_config


def _norm_txt(v: Any) -> str:
    """
    Normaliza texto para comparação:
    - None -> ""
    - strip
    - remove acentos
    - upper
    """
    s = str(v or "").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.upper()


def _norm_colname(name: str) -> str:
    """
    Normaliza nome de coluna:
    - remove acentos
    - upper
    - troca múltiplos espaços por 1
    """
    return " ".join(_norm_txt(name).split())


def _get_col(linha, *candidatos: str, default=None):
    """
    Busca coluna por múltiplos nomes possíveis, tolerando:
    - acentos
    - espaços extras
    - variações simples

    Ex.: "VALIDAÇÃO", "VALIDACAO", "STATUS VALIDAÇÃO" etc.
    """
    # cria mapa {COL_NORMALIZADA: COL_ORIGINAL}
    idx = getattr(linha, "index", [])
    mapa = {_norm_colname(str(c)): str(c) for c in idx}

    for nome in candidatos:
        key = _norm_colname(nome)
        col_real = mapa.get(key)
        if col_real is not None:
            val = linha.get(col_real)
            if val is not None:
                return val

    return default


def identificar_destinatarios(
    linha,
    diretorio_acessos=None,
    debug: bool = False
) -> list[str]:
    """
    Regras:
    - STATUS ATUAL define para quem vai o email
    - Não há filtro por coluna de VALIDAÇÃO

    Regras fixas:
    - PENDENTE DIRETORIA -> Adriana + Thiago (fixos)
    - PENDENTE GOVERNANÇA - TI -> Lais + Lucas (fixos)

    Regras por lookup:
    - PENDENTE LÍDER -> bate nome do líder na aba LIDERES
    - PENDENTE ÁREA RESPONSÁVEL -> bate ACESSO na aba ACESSO e pega E-mail Líder
    """

    # =========================
    # 1) Base de decisão
    # =========================
    etapa = _norm_txt(_get_col(linha, "STATUS ATUAL", "STATUS_ATUAL", default=""))
    if debug:
        print(f"[DEBUG] STATUS ATUAL='{etapa}'")

    # =========================
    # 2) Governança - TI (fixo)
    #    cobre quando for qualquer variação que contenha GOVERNANCA e TI
    #    (ex.: "PENDENTE GOVERNANÇA - TI", "INATIVAR ... GOVERNANÇA - TI", "ANÁLISE GOVERNANÇA - TI")
    # =========================
    if "GOVERNANCA" in etapa and "TI" in etapa:
        return [e for e in email_config.GOVERNANCA_TI if e]

    # =========================
    # 3) Diretoria (pendente individual)
    # =========================
    if "DIRETORIA" in etapa:
        pendente_sistemas = _norm_txt(_get_col(linha, "DIRETORIA DE SISTEMAS", default=""))
        pendente_apoio = _norm_txt(_get_col(linha, "DIRETORIA APOIO", default=""))
        emails = []
        if "PENDENTE" in pendente_sistemas:
            emails.extend([e for e in list(email_config.DIRETORIA_SISTEMAS) if e])
        if "PENDENTE" in pendente_apoio:
            emails.extend([e for e in list(email_config.DIRETORIA_APOIO) if e])
        return emails

    # =========================
    # 4) Área responsável (por ACESSO -> aba ACESSO)
    # =========================
    # aceita qualquer etapa que contenha AREA
    if "AREA" in etapa:
        acesso = _get_col(linha, "ACESSO", "Acesso", default="")

        if debug:
            print(f"[DEBUG] Regra ÁREA | ACESSO='{acesso}'")

        if diretorio_acessos and acesso:
            if hasattr(diretorio_acessos, "emails_por_acesso"):
                emails = diretorio_acessos.emails_por_acesso(acesso)
                return [e for e in emails if e] if emails else []

            if hasattr(diretorio_acessos, "email_por_acesso"):
                email = diretorio_acessos.email_por_acesso(acesso)
                return [email] if email else []

        return []

    # =========================
    # 5) Líder (por nome -> aba LIDERES)
    # =========================
    if "LIDER" in etapa:
        nome_lider = _get_col(
            linha,
            "LIDER USUARIO DO ACESSO",
            "LÍDER USUÁRIO DO ACESSO",
            "LIDER USUÁRIO DO ACESSO",
            "LIDER",
            "LÍDER",
            default=""
        )

        if debug:
            print(f"[DEBUG] Regra LÍDER | nome_lider='{nome_lider}'")

        if diretorio_acessos and nome_lider:
            if hasattr(diretorio_acessos, "emails_por_lider"):
                emails = diretorio_acessos.emails_por_lider(nome_lider)
                return [e for e in emails if e] if emails else []

            if hasattr(diretorio_acessos, "email_por_lider"):
                email = diretorio_acessos.email_por_lider(nome_lider)
                return [email] if email else []
        return []

    return []