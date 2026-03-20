from __future__ import annotations

import os
import unicodedata
from typing import Any

from dotenv import load_dotenv


load_dotenv()


def _norm_txt(v: Any) -> str:
    s = str(v or "").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split()).upper()


def classificar_regra_desligamento(tipo_usuario: Any) -> str:
    tipo = _norm_txt(tipo_usuario)
    if tipo in {"TERCEIRO", "GENERICO", "GENERICO/TERCEIRO", "TERCEIRO/GENERICO"}:
        return "lider_governanca"
    if tipo in {"SOCIO", "CONSELHEIRO"}:
        return "governanca"
    return "ignorar"


def _emails_governanca_individual() -> list[str]:
    emails = [
        str(os.getenv("EMAIL_GOV_LAIS", "")).strip(),
        str(os.getenv("EMAIL_GOV_LUCAS", "")).strip(),
    ]
    return [email for email in emails if email and "@" in email]


def _email_grupo_gestao_acessos() -> list[str]:
    email = str(os.getenv("REPLY_TO_GROUP_EMAIL", "")).strip()
    return [email] if email and "@" in email else []


def _deduplicar(destinatarios: list[str]) -> list[str]:
    vistos = set()
    destinatarios_unicos = []
    for email in destinatarios:
        chave = str(email).strip().lower()
        if not chave or "@" not in chave or chave in vistos:
            continue
        vistos.add(chave)
        destinatarios_unicos.append(email)
    return destinatarios_unicos


def obter_destinatarios_sumario_desligamentos() -> dict[str, list[str]]:
    email_roosevelt = str(os.getenv("CONTACT_ROOSEVELT_EMAIL", "")).strip()
    email_kleyton = str(os.getenv("CONTACT_KLEYTON_EMAIL", "kleyton.eleuterio@gpssa.com.br")).strip()

    emails = []
    for email in [email_kleyton, email_roosevelt]:
        if email and "@" in email and email.lower() not in {e.lower() for e in emails}:
            emails.append(email)

    return {
        "email": emails,
        "teams": emails.copy(),
    }


def obter_destinatarios_sem_casos_desligamentos() -> dict[str, list[str]]:
    emails = []
    for email in [
        str(os.getenv("EMAIL_GOV_LAIS", "")).strip(),
        str(os.getenv("EMAIL_GOV_LUCAS", "")).strip(),
        str(os.getenv("CONTACT_KLEYTON_EMAIL", "kleyton.eleuterio@gpssa.com.br")).strip(),
        str(os.getenv("CONTACT_ROOSEVELT_EMAIL", "")).strip(),
    ]:
        if email and "@" in email and email.lower() not in {e.lower() for e in emails}:
            emails.append(email)

    return {
        "email": emails,
        "teams": emails.copy(),
    }


def identificar_destinatarios_desligamento(linha, diretorio_acessos=None) -> dict[str, Any]:
    tipo_usuario = linha.get("TIPO USUARIO", linha.get("TIPO USUÁRIO", ""))
    regra = classificar_regra_desligamento(tipo_usuario)
    motivo_atuacao = str(linha.get("MOTIVO_ATUACAO", "")).strip()

    destinatarios_email: list[str] = []
    destinatarios_teams: list[str] = []
    governanca_email = _email_grupo_gestao_acessos()
    governanca_teams = _emails_governanca_individual()

    if motivo_atuacao == "contrato_cancelado_terceiro":
        destinatarios_email.extend(governanca_email)
        destinatarios_teams.extend(governanca_teams)
        return {
            "regra": "contrato_cancelado_terceiro",
            "destinatarios_email": _deduplicar(destinatarios_email),
            "destinatarios_teams": _deduplicar(destinatarios_teams),
        }

    if regra == "lider_governanca":
        nome_lider = linha.get("LIDER USUARIO DO ACESSO", linha.get("LIDER USUÁRIO DO ACESSO", ""))
        email_lider = ""
        if diretorio_acessos and nome_lider and hasattr(diretorio_acessos, "email_por_lider"):
            email_lider = diretorio_acessos.email_por_lider(nome_lider)
        if email_lider:
            destinatarios_email.append(email_lider)
            destinatarios_teams.append(email_lider)
        destinatarios_email.extend(governanca_email)
        destinatarios_teams.extend(governanca_teams)

    elif regra == "governanca":
        destinatarios_email.extend(governanca_email)
        destinatarios_teams.extend(governanca_teams)

    return {
        "regra": regra,
        "destinatarios_email": _deduplicar(destinatarios_email),
        "destinatarios_teams": _deduplicar(destinatarios_teams),
    }