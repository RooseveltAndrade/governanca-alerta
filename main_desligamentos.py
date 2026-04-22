from __future__ import annotations

import html
import logging
import os
from collections import defaultdict
from pathlib import Path

from automation.portal_selenium import PortalGPS
from services.diretorio_acessos import DiretorioAcessos
from services.envio_email import enviar_alerta_operacional, enviar_email
from services.envio_teams import enviar_mensagem_teams, teams_habilitado
from services.leitura_desligamentos import (
    carregar_planilha_desligamentos,
    filtrar_desligados_ativos,
    resumir_desligados,
)
from services.regras_desligamentos import (
    identificar_destinatarios_desligamento,
    obter_destinatarios_sem_casos_desligamentos,
    obter_destinatarios_sumario_desligamentos,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


CAMINHO_DIRETORIO_ACESSOS = os.getenv("CAMINHO_DIRETORIO_ACESSOS", "data/Equipe Solucionadora.xlsx")
CAMINHO_ASSINATURA_GIF = Path(__file__).resolve().parent / "image" / "assinatura_gif.gif"


def _parse_env_list(nome_variavel: str) -> list[str]:
    valor = str(os.getenv(nome_variavel, "")).strip()
    return [item.strip() for item in valor.split(",") if item.strip()]


def _resolver_destinatarios_email(destinatarios: list[str]) -> list[str]:
    destinatarios_teste = _parse_env_list("DESLIGAMENTOS_SAFE_TEST_TO")
    if destinatarios_teste:
        logging.info("DESLIGAMENTOS_SAFE_TEST_TO ativo: redirecionando email de desligamentos para destinatário de teste.")
        return destinatarios_teste
    return destinatarios


def _teams_desligamentos_habilitado() -> bool:
    if str(os.getenv("DESLIGAMENTOS_DISABLE_TEAMS", "False")).strip().lower() in ("1", "true", "yes", "y", "sim"):
        return False
    return teams_habilitado()


def _somente_sumario_habilitado() -> bool:
    return str(os.getenv("DESLIGAMENTOS_ONLY_SUMMARY", "False")).strip().lower() in ("1", "true", "yes", "y", "sim")


def _obter_portal_url() -> str:
    return str(os.getenv("PORTAL_URL", "https://portal.gpssa.com.br/RAR/CriacaoUsuario")).strip()


def _obter_email_contato_principal() -> str:
    return str(os.getenv("REPLY_TO_GROUP_EMAIL", "")).strip()


def _obter_nome_lais() -> str:
    return str(os.getenv("CONTACT_LAIS_NAME", "Laís de Oliveira Cosme")).strip()


def _obter_nome_lucas() -> str:
    return str(os.getenv("CONTACT_LUCAS_NAME", "Lucas de Oliveira Barreto")).strip()


def _obter_email_lais() -> str:
    return str(os.getenv("EMAIL_GOV_LAIS", "")).strip()


def _obter_email_lucas() -> str:
    return str(os.getenv("EMAIL_GOV_LUCAS", "")).strip()


def _obter_link_teams(email: str) -> str:
    email_limpo = str(email or "").strip()
    if not email_limpo:
        return "#"
    return f"https://teams.microsoft.com/l/chat/0/0?users={html.escape(email_limpo, quote=True)}"


def _descricao_motivo(motivo: str) -> str:
    mapa = {
        "status_folha_desligado": "Usuário com STATUS FOLHA = DESLIGADO e acesso ainda ativo.",
        "contrato_cancelado_terceiro": "Usuário do tipo Terceiro com STATUS ATUAL = ATIVO e CONTRATO = CANCELADO.",
    }
    return mapa.get(str(motivo or "").strip(), str(motivo or "").strip())


def _rotulo_status_sumario(itens: list[dict]) -> str:
    motivos = {str(item.get("motivo_atuacao", "")).strip() for item in itens}
    rotulos = []
    if "status_folha_desligado" in motivos:
        rotulos.append("Desligamento")
    if "contrato_cancelado_terceiro" in motivos:
        rotulos.append("Contrato")
    return " / ".join(rotulos) if rotulos else "Desligamento"


def _rotulo_cargo_destinatario(destinatario: str) -> str:
    email = str(destinatario or "").strip().lower()
    if not email:
        return "Área"

    if email == _obter_email_contato_principal().strip().lower():
        return "Gestão de Acessos"

    governanca = {
        _obter_email_lais().strip().lower(),
        _obter_email_lucas().strip().lower(),
    }
    if email in governanca:
        return "Governança"

    return "Líder"


def _ordenar_envios_sumario_desligamentos(envios: list[dict]) -> list[dict]:
    ordem_cargos = {"Líder": 0, "Governança": 1, "Gestão de Acessos": 2, "Área": 3}
    ordem_status = {"Desligamento": 0, "Contrato": 1, "Desligamento / Contrato": 2}

    def chave(envio: dict):
        return (
            ordem_cargos.get(envio.get("cargo", ""), 99),
            ordem_status.get(envio.get("status", ""), 99),
            envio.get("destinatario", ""),
        )

    return sorted((envio.copy() for envio in envios), key=chave)


def _agrupar_envios_sumario_desligamentos(envios: list[dict]) -> list[dict]:
    agrupados: dict[tuple[str, str], dict] = {}
    for envio in envios:
        destinatario = str(envio.get("destinatario", "")).strip()
        status = str(envio.get("status", "")).strip()
        key = (destinatario, status)

        ids = [str(i).strip() for i in envio.get("ids", []) if str(i).strip()]

        if key not in agrupados:
            agrupados[key] = {
                "destinatario": destinatario,
                "cargo": envio.get("cargo", ""),
                "status": status,
                "regra": envio.get("regra", ""),
                "ids": ids,
            }
            continue

        existentes = set(agrupados[key]["ids"])
        for item_id in ids:
            if item_id not in existentes:
                agrupados[key]["ids"].append(item_id)
                existentes.add(item_id)

    for item in agrupados.values():
        item["qtd"] = len(item.get("ids", []))

    return list(agrupados.values())


def _normalizar_item(linha) -> dict[str, str]:
    return {
        "id": str(linha.get("ID", "")).strip(),
        "tipo_usuario": str(linha.get("TIPO USUARIO", linha.get("TIPO USUÁRIO", ""))).strip(),
        "usuario_acesso": str(linha.get("USUARIO DO ACESSO", linha.get("USUÁRIO DO ACESSO", ""))).strip(),
        "lider_usuario": str(linha.get("LIDER USUARIO DO ACESSO", linha.get("LIDER USUÁRIO DO ACESSO", ""))).strip(),
        "acesso": str(linha.get("ACESSO", "")).strip(),
        "sistema": str(linha.get("SISTEMA", "")).strip(),
        "status_atual": str(linha.get("STATUS ATUAL", "")).strip(),
        "status_folha": str(linha.get("STATUS FOLHA", "")).strip(),
        "contrato": str(linha.get("CONTRATO", "")).strip(),
        "motivo_atuacao": str(linha.get("MOTIVO_ATUACAO", "")).strip(),
    }


def _montar_assinatura_html() -> str:
    email_contato = html.escape(_obter_email_contato_principal())
    lais_nome = html.escape(_obter_nome_lais())
    lucas_nome = html.escape(_obter_nome_lucas())
    lais_link = _obter_link_teams(_obter_email_lais())
    lucas_link = _obter_link_teams(_obter_email_lucas())

    if CAMINHO_ASSINATURA_GIF.exists():
        return (
            "<table role='presentation' cellpadding='0' cellspacing='0' "
            "style='margin-top:6px; margin-left:auto; margin-right:auto; border-collapse:collapse;'>"
            "<tr>"
            "<td style='vertical-align:middle; padding-right:6px;'>"
            "<img src='cid:assinatura_gif' alt='Assinatura Grupo GPS' width='145' "
            "style='width:145px; max-width:145px; height:auto; display:block;'>"
            "</td>"
            "<td style='vertical-align:middle; padding-top:0; font-family:Arial, sans-serif; color:#1f3352; text-align:left;'>"
            "<div style='font-size:20px; line-height:1.1; font-weight:700; margin:0;'>Gestão de Acessos de TI</div>"
            "<div style='margin-top:0; color:#666666; font-size:14px; line-height:1.1;'>Gestão de Acessos | Governança de TI</div>"
            f"<div style='margin-top:0; line-height:1.1;'><a href='mailto:{email_contato}' style='color:#1f4e9a; font-size:14px;'>{email_contato}</a></div>"
            "<div style='margin-top:0; font-size:13px; line-height:1.1;'>"
            f"<a href='{lais_link}' style='color:#1f4e9a;'>Fale com a {lais_nome} no Teams</a> | "
            f"<a href='{lucas_link}' style='color:#1f4e9a;'>Fale com o {lucas_nome} no Teams</a>"
            "</div>"
            "</td>"
            "</tr>"
            "</table>"
        )

    return (
        "<p style='margin-top:18px;'><strong>Gestão de Acessos de TI</strong><br>"
        "Gestão de Acessos | Governança de TI<br>"
        f"<a href='mailto:{email_contato}'>{email_contato}</a><br>"
        f"<a href='{lais_link}'>Fale com a {lais_nome} no Teams</a> | "
        f"<a href='{lucas_link}'>Fale com o {lucas_nome} no Teams</a></p>"
    )


def _obter_inline_attachments_assinatura() -> list[dict]:
    inline_attachments = []
    if CAMINHO_ASSINATURA_GIF.exists():
        try:
            inline_attachments.append(
                {
                    "cid": "assinatura_gif",
                    "name": "assinatura_gif.gif",
                    "content_type": "image/gif",
                    "data": CAMINHO_ASSINATURA_GIF.read_bytes(),
                }
            )
        except Exception as e:
            logging.warning(f"Não foi possível carregar GIF da assinatura para desligamentos: {e}")
    return inline_attachments


def _montar_corpo_notificacao_desligamentos(itens: list[dict], is_lider: bool) -> tuple[str, str, list[dict]]:
    portal_url = _obter_portal_url()
    linhas_texto = []
    linhas_html = []

    for item in itens:
        linhas_texto.append(
            "- {id} | {tipo_usuario} | {usuario_acesso} | {acesso} | {sistema} | {status_atual} | {status_folha} | {contrato}".format(
                id=item["id"],
                tipo_usuario=item["tipo_usuario"],
                usuario_acesso=item["usuario_acesso"],
                acesso=item["acesso"],
                sistema=item["sistema"],
                status_atual=item["status_atual"],
                status_folha=item["status_folha"],
                contrato=item["contrato"],
            )
        )
        linhas_html.append(
            "<tr>"
            f"<td>{html.escape(item['id'])}</td>"
            f"<td>{html.escape(item['tipo_usuario'])}</td>"
            f"<td>{html.escape(item['usuario_acesso'])}</td>"
            f"<td>{html.escape(item['acesso'])}</td>"
            f"<td>{html.escape(item['sistema'])}</td>"
            f"<td>{html.escape(item['status_atual'])}</td>"
            f"<td>{html.escape(item['status_folha'])}</td>"
            f"<td>{html.escape(item['contrato'])}</td>"
            "</tr>"
        )

    corpo_texto = (
        "Prezado(a),\n\n"
        "Foram identificados acessos que exigem atuação no Portal Genéricos e Privilegiados em função de desligamento ou cancelamento de contrato.\n\n"
        "Pendências identificadas:\n"
        "ID | TIPO DE USUÁRIO | USUÁRIO DO ACESSO | ACESSO | SISTEMA | STATUS ATUAL | STATUS FOLHA | CONTRATO\n"
        f"{'\n'.join(linhas_texto)}\n\n"
    )
    if is_lider:
        corpo_texto += (
            "O acesso acima está atualmente vinculado a um recurso desligado ou sem contrato vigente. Caso o time de Gestão de Acessos de TI não receba a indicação de um novo responsável ou de um novo número de contrato, o acesso será revogado.\n\n"
            "Além disso, é de sua responsabilidade providenciar imediatamente a troca de senha, garantindo que o antigo responsável não mantenha qualquer possibilidade de uso do acesso.\n\n"
        )
    corpo_texto += (
        "Para mais informações sobre o chamado e para realizar a devida tratativa, acesse o portal: "
        f"{portal_url}\n\n"
        "IMPORTANTE! Esta é uma mensagem automática. Por favor, não responda."
    )

    corpo_html = (
        "<div style='font-family:Arial, sans-serif; font-size:16px; color:#1a1a1a; line-height:1.35;'>"
        "<p style='margin:0 0 8px 0;'>Prezado(a),</p>"
        "<p style='margin:0 0 8px 0;'>Foram identificados acessos que exigem atuação no Portal Genéricos e Privilegiados em função de desligamento ou cancelamento de contrato.</p>"
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse; margin:0;'>"
        "<thead><tr>"
        "<th>ID</th><th>TIPO DE USUÁRIO</th><th>USUÁRIO DO ACESSO</th><th>ACESSO</th><th>SISTEMA</th><th>STATUS ATUAL</th><th>STATUS FOLHA</th><th>CONTRATO</th>"
        "</tr></thead>"
        f"<tbody>{''.join(linhas_html)}</tbody>"
        "</table>"
    )
    if is_lider:
        corpo_html += (
            "<p style='margin:12px 0 8px 0;'>O acesso acima está atualmente vinculado a um recurso desligado ou sem contrato vigente. Caso o time de Gestão de Acessos de TI não receba a indicação de um novo responsável ou de um novo número de contrato, o acesso será revogado.</p>"
            "<p style='margin:12px 0 8px 0;'>Além disso, é de sua responsabilidade providenciar imediatamente a troca de senha, garantindo que o antigo responsável não mantenha qualquer possibilidade de uso do acesso.</p>"
        )
    corpo_html += (
        "<p style='margin:12px 0 8px 0;'>Para mais informações sobre o chamado e para realizar a devida tratativa, acesse o "
        f"<a href='{html.escape(portal_url, quote=True)}'>Portal Genéricos e Privilegiados</a>.</p>"
        "<p style='margin:12px 0 8px 0;'><strong>IMPORTANTE!</strong> Esta é uma mensagem automática. Por favor, não responda.</p>"
        f"{_montar_assinatura_html()}"
        "</div>"
    )
    return corpo_texto, corpo_html, _obter_inline_attachments_assinatura()


def _montar_mensagem_teams_desligamentos(itens: list[dict], is_lider: bool) -> str:
    portal_url = html.escape(_obter_portal_url(), quote=True)
    linhas = []
    for item in itens:
        linhas.append(
            "<tr>"
            f"<td>{html.escape(item['id'])}</td>"
            f"<td>{html.escape(item['tipo_usuario'])}</td>"
            f"<td>{html.escape(item['usuario_acesso'])}</td>"
            f"<td>{html.escape(item['acesso'])}</td>"
            f"<td>{html.escape(item['sistema'])}</td>"
            f"<td>{html.escape(item['status_atual'])}</td>"
            f"<td>{html.escape(item['status_folha'])}</td>"
            f"<td>{html.escape(item['contrato'])}</td>"
            "</tr>"
        )

    base_html = (
        "<div>"
        "<p><strong>Olá!</strong></p>"
        f"<p>Você possui <strong>{len(itens)}</strong> caso(s) para atuação em função de desligamento ou cancelamento de contrato.</p>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; margin-bottom:10px;'>"
        "<thead><tr><th>ID</th><th>TIPO DE USUÁRIO</th><th>USUÁRIO DO ACESSO</th><th>ACESSO</th><th>SISTEMA</th><th>STATUS ATUAL</th><th>STATUS FOLHA</th><th>CONTRATO</th></tr></thead>"
        f"<tbody>{''.join(linhas)}</tbody>"
        "</table>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
    )

    extra_html = ""
    if is_lider:
        extra_html = (
            "<p>O acesso acima está atualmente vinculado a um recurso desligado ou sem contrato vigente. Caso o time de Gestão de Acessos de TI não receba a indicação de um novo responsável ou de um novo número de contrato, o acesso será revogado.</p>"
            "<p>Além disso, é de sua responsabilidade providenciar imediatamente a troca de senha, garantindo que o antigo responsável não mantenha qualquer possibilidade de uso do acesso.</p>"
        )

    return (
        base_html
        + extra_html
        + f"<p>Para mais informações sobre o chamado e para realizar a devida tratativa, acesse o <a href='{portal_url}'>Portal Genéricos e Privilegiados</a>.</p>"
        + "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        + "<p><strong>IMPORTANTE!</strong> Esta é uma mensagem automática. Por favor, não responda.</p>"
        + "</div>"
    )


def _montar_corpo_sem_casos() -> tuple[str, str, list[dict]]:
    corpo_texto = (
        "Prezados,\n\n"
        "Não foram identificados casos elegíveis para atuação na rotina de desligamentos no ciclo atual.\n\n"
        "Critérios avaliados:\n"
        "- STATUS ATUAL = ATIVO e STATUS FOLHA = DESLIGADO\n"
        "- STATUS ATUAL = ATIVO, TIPO = TERCEIRO e CONTRATO = CANCELADO\n"
    )
    corpo_html = (
        "<div style='font-family:Arial, sans-serif; font-size:16px; color:#1a1a1a; line-height:1.35;'>"
        "<p>Prezados,</p>"
        "<p>Não foram identificados casos elegíveis para atuação na rotina de desligamentos no ciclo atual.</p>"
        "<p>Critérios avaliados:</p>"
        "<ul>"
        "<li>STATUS ATUAL = ATIVO e STATUS FOLHA = DESLIGADO</li>"
        "<li>STATUS ATUAL = ATIVO, TIPO = TERCEIRO e CONTRATO = CANCELADO</li>"
        "</ul>"
        f"{_montar_assinatura_html()}"
        "</div>"
    )
    return corpo_texto, corpo_html, _obter_inline_attachments_assinatura()


def _montar_mensagem_teams_sem_casos() -> str:
    return (
        "<div>"
        "<p><strong>Olá!</strong></p>"
        "<p>Não foram identificados casos elegíveis para atuação na rotina de desligamentos no ciclo atual.</p>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        "<p>Critérios avaliados:</p>"
        "<ul>"
        "<li>STATUS ATUAL = ATIVO e STATUS FOLHA = DESLIGADO</li>"
        "<li>STATUS ATUAL = ATIVO, TIPO = TERCEIRO e CONTRATO = CANCELADO</li>"
        "</ul>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        "<p><strong>IMPORTANTE!</strong> Esta é uma mensagem automática. Por favor, não responda.</p>"
        "</div>"
    )


def _montar_sumario_desligamentos(envios: list[dict]) -> tuple[str, str, str, list[dict]]:
    envios_ordenados = _ordenar_envios_sumario_desligamentos(envios)
    linhas_texto = []
    linhas_html = []
    for envio in envios_ordenados:
        linhas_texto.append(
            f"{envio['destinatario']} | {envio['status']} | {envio['qtd']} caso(s) | IDs: {', '.join(envio['ids'])}"
        )
        linhas_html.append(
            "<tr>"
            f"<td>{html.escape(envio['destinatario'])}</td>"
            f"<td>{html.escape(envio['status'])}</td>"
            f"<td>{envio['qtd']}</td>"
            f"<td>{html.escape(', '.join(envio['ids']))}</td>"
            "</tr>"
        )

    assunto = "[Sumário Executivo] Relatório de desligamentos"
    corpo_texto = "\n".join(linhas_texto)
    corpo_html = (
        "<div style='font-family:Arial, sans-serif; font-size:16px; color:#1a1a1a; line-height:1.35;'>"
        "<p>Prezados,</p>"
        "<p>Este é um e-mail automático de relatório, contendo o resumo dos status das notificações de desligamentos encaminhadas no ciclo atual.</p>"
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
        "<thead><tr><th>Destinatário</th><th>Status</th><th>Qtd Pendências</th><th>IDs</th></tr></thead>"
        f"<tbody>{''.join(linhas_html)}</tbody>"
        "</table>"
        f"{_montar_assinatura_html()}"
        "</div>"
    )
    return assunto, corpo_texto, corpo_html, _obter_inline_attachments_assinatura()


def _montar_sumario_desligamentos_teams(envios: list[dict]) -> str:
    envios_ordenados = _ordenar_envios_sumario_desligamentos(envios)
    linhas_html = []
    for envio in envios_ordenados:
        linhas_html.append(
            "<tr>"
            f"<td>{html.escape(envio['destinatario'])}</td>"
            f"<td>{html.escape(envio['status'])}</td>"
            f"<td>{envio['qtd']}</td>"
            f"<td>{html.escape(', '.join(envio['ids']))}</td>"
            "</tr>"
        )

    return (
        "<div>"
        "<p><strong>Olá!</strong></p>"
        "<p>Resumo das notificações de desligamentos encaminhadas no ciclo atual.</p>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;'>"
        "<thead><tr><th>Destinatário</th><th>Status</th><th>Qtd Pendências</th><th>IDs</th></tr></thead>"
        f"<tbody>{''.join(linhas_html)}</tbody>"
        "</table>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        "<p><strong>IMPORTANTE!</strong> Esta é uma mensagem automática. Por favor, não responda.</p>"
        "</div>"
    )


def executar() -> str | None:
    logging.info("Iniciando automação de desligamentos...")

    portal = PortalGPS(
        fast_mode=True,
        filtro_exportacao="TODOS",
        prefixo_arquivo="IntegracaoDesligamentos",
        download_timeout=300,
    )
    caminho_planilha = portal.executar()

    if not caminho_planilha:
        mensagem = "Não foi possível obter a planilha IntegracaoDesligamentos do portal."
        logging.error(mensagem)
        enviar_alerta_operacional("[ALERTA] Falha na exportação de desligamentos", mensagem)
        return None

    logging.info(f"Planilha IntegracaoDesligamentos obtida com sucesso: {caminho_planilha}")

    diretorio_acessos = DiretorioAcessos(CAMINHO_DIRETORIO_ACESSOS)
    df = carregar_planilha_desligamentos(caminho_planilha)
    df_filtrado = filtrar_desligados_ativos(df)
    resumo = resumir_desligados(df_filtrado)
    logging.info(f"Total elegível para desligamentos: {resumo['total']}")
    somente_sumario = _somente_sumario_habilitado()

    if df_filtrado.empty:
        corpo_texto, corpo_html, inline_attachments = _montar_corpo_sem_casos()
        destinatarios_sumario = obter_destinatarios_sumario_desligamentos()
        if destinatarios_sumario["email"]:
            enviar_email(
                destinatarios_sumario["email"],
                "[Desligamentos] Nenhum caso elegível para atuação",
                corpo_texto,
                corpo_html=corpo_html,
                inline_attachments=inline_attachments,
            )
        if _teams_desligamentos_habilitado() and destinatarios_sumario["teams"]:
            enviar_mensagem_teams(destinatarios_sumario["teams"], _montar_mensagem_teams_sem_casos(), content_type="html")
        return caminho_planilha

    envios_email = defaultdict(list)
    envios_teams = defaultdict(list)
    envios_sumario: list[dict] = []

    for _, linha in df_filtrado.iterrows():
        item = _normalizar_item(linha)

        # 🔒 VALIDAÇÃO FINAL (ANTI-BUG - GARANTE REGRA DE NEGÓCIO)
        status_atual = item["status_atual"].upper()
        status_folha = item["status_folha"].upper()
        tipo_usuario = item["tipo_usuario"].upper()
        contrato = item["contrato"].upper()

        regra_valida = (
            ("ATIVO" in status_atual and "DESLIGADO" in status_folha)
            or
            (
                "ATIVO" in status_atual and
                ("TERCEIRO" in tipo_usuario or "GENÉRICO" in tipo_usuario) and
                "CANCELADO" in contrato
            )
        )

        if not regra_valida:
            logging.warning(
                f"[IGNORADO - FORA DA REGRA] ID {item['id']} | "
                f"{status_atual} | {status_folha} | {tipo_usuario} | {contrato}"
            )
            continue
        # 🔒 FIM DA VALIDAÇÃO FINAL

        resolucao = identificar_destinatarios_desligamento(linha, diretorio_acessos)

        if not resolucao["destinatarios_email"] and not resolucao["destinatarios_teams"]:
            if tipo_usuario == "CLT":
                assunto_alerta = f"[ALERTA] Desligamento CLT sem destinatários resolvidos: {item['id']}"
                aviso_extra = (
                    "ATENÇÃO: Não foi enviado notificação pois o usuário é CLT e não há regra específica para esse caso."
                )
            else:
                assunto_alerta = f"[ALERTA] Desligamento sem destinatários resolvidos: {item['id']}"
                aviso_extra = ""

            corpo_texto = (
                f"{assunto_alerta}\n\n"
                f"ID: {item['id']}\n"
                f"Usuário do acesso: {item['usuario_acesso']}\n"
                f"Tipo: {item['tipo_usuario']}\n"
                f"Acesso: {item['acesso']}\n"
                f"Sistema: {item['sistema']}\n"
                f"Motivo: {_descricao_motivo(item['motivo_atuacao'])}"
            )
            if aviso_extra:
                corpo_texto = f"{corpo_texto}\n\n{aviso_extra}"

            corpo_html = (
                "<div style='font-family:Arial, sans-serif; font-size:16px; color:#1a1a1a; line-height:1.35;'>"
                f"<p><strong>{html.escape(assunto_alerta)}</strong></p>"
                "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
                "<thead><tr><th>ID</th><th>Usuário do acesso</th><th>Tipo</th><th>Acesso</th><th>Sistema</th><th>Motivo</th></tr></thead>"
                "<tbody><tr>"
                f"<td>{html.escape(str(item['id']))}</td>"
                f"<td>{html.escape(str(item['usuario_acesso']))}</td>"
                f"<td>{html.escape(str(item['tipo_usuario']))}</td>"
                f"<td>{html.escape(str(item['acesso']))}</td>"
                f"<td>{html.escape(str(item['sistema']))}</td>"
                f"<td>{html.escape(_descricao_motivo(item['motivo_atuacao']))}</td>"
                "</tr></tbody>"
                "</table>"
            )
            if aviso_extra:
                corpo_html += f"<p style='margin-top:10px;'><strong>{html.escape(aviso_extra)}</strong></p>"
            corpo_html += f"{_montar_assinatura_html()}" "</div>"

            teams_html = (
                "<div>"
                f"<p><strong>{html.escape(assunto_alerta)}</strong></p>"
                "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;'>"
                "<thead><tr><th>ID</th><th>Usuário do acesso</th><th>Tipo</th><th>Acesso</th><th>Sistema</th><th>Motivo</th></tr></thead>"
                "<tbody><tr>"
                f"<td>{html.escape(str(item['id']))}</td>"
                f"<td>{html.escape(str(item['usuario_acesso']))}</td>"
                f"<td>{html.escape(str(item['tipo_usuario']))}</td>"
                f"<td>{html.escape(str(item['acesso']))}</td>"
                f"<td>{html.escape(str(item['sistema']))}</td>"
                f"<td>{html.escape(_descricao_motivo(item['motivo_atuacao']))}</td>"
                "</tr></tbody>"
                "</table>"
            )
            if aviso_extra:
                teams_html += f"<p><strong>{html.escape(aviso_extra)}</strong></p>"
            teams_html += "</div>"
            enviar_alerta_operacional(
                assunto_alerta,
                corpo_texto,
                corpo_html=corpo_html,
                inline_attachments=_obter_inline_attachments_assinatura(),
                teams_html=teams_html,
            )
            continue

        for destinatario in resolucao["destinatarios_email"]:
            envios_email[destinatario].append(item)

        for destinatario in resolucao["destinatarios_teams"]:
            envios_teams[destinatario].append(item)
            
    for destinatario, itens in envios_email.items():
        assunto = f"[Desligamentos] Você possui {len(itens)} caso(s) para atuação no Portal"
        cargo = _rotulo_cargo_destinatario(destinatario)
        corpo_texto, corpo_html, inline_attachments = _montar_corpo_notificacao_desligamentos(itens, cargo == "Líder")
        if somente_sumario:
            logging.info(f"DESLIGAMENTOS_ONLY_SUMMARY ativo: não enviando email individual para {destinatario}.")
            envios_sumario.append(
                {
                    "destinatario": destinatario,
                    "canal": "Email",
                    "cargo": _rotulo_cargo_destinatario(destinatario),
                    "status": _rotulo_status_sumario(itens),
                    "regra": ", ".join(sorted({_descricao_motivo(item['motivo_atuacao']) for item in itens})),
                    "qtd": len(itens),
                    "ids": [item["id"] for item in itens],
                }
            )
        elif enviar_email(
            _resolver_destinatarios_email([destinatario]),
            assunto,
            corpo_texto,
            corpo_html=corpo_html,
            inline_attachments=inline_attachments,
        ):
            envios_sumario.append(
                {
                    "destinatario": destinatario,
                    "canal": "Email",
                    "cargo": _rotulo_cargo_destinatario(destinatario),
                    "status": _rotulo_status_sumario(itens),
                    "regra": ", ".join(sorted({_descricao_motivo(item['motivo_atuacao']) for item in itens})),
                    "qtd": len(itens),
                    "ids": [item["id"] for item in itens],
                }
            )

    if _teams_desligamentos_habilitado():
        for destinatario, itens in envios_teams.items():
            cargo = _rotulo_cargo_destinatario(destinatario)
            mensagem = _montar_mensagem_teams_desligamentos(itens, cargo == "Líder")
            if somente_sumario:
                logging.info(f"DESLIGAMENTOS_ONLY_SUMMARY ativo: não enviando Teams individual para {destinatario}.")
                envios_sumario.append(
                    {
                        "destinatario": destinatario,
                        "canal": "Teams",
                        "cargo": _rotulo_cargo_destinatario(destinatario),
                        "status": _rotulo_status_sumario(itens),
                        "regra": ", ".join(sorted({_descricao_motivo(item['motivo_atuacao']) for item in itens})),
                        "qtd": len(itens),
                        "ids": [item["id"] for item in itens],
                    }
                )
            elif enviar_mensagem_teams([destinatario], mensagem, content_type="html"):
                envios_sumario.append(
                    {
                        "destinatario": destinatario,
                        "canal": "Teams",
                        "cargo": _rotulo_cargo_destinatario(destinatario),
                        "status": _rotulo_status_sumario(itens),
                        "regra": ", ".join(sorted({_descricao_motivo(item['motivo_atuacao']) for item in itens})),
                        "qtd": len(itens),
                        "ids": [item["id"] for item in itens],
                    }
                )

    if envios_sumario:
        envios_sumario_unicos = _agrupar_envios_sumario_desligamentos(envios_sumario)
        assunto_sumario, corpo_texto_sumario, corpo_html_sumario, inline_attachments_sumario = _montar_sumario_desligamentos(envios_sumario_unicos)
        destinatarios_sumario = obter_destinatarios_sumario_desligamentos()
        if destinatarios_sumario["email"]:
            enviar_email(
                _resolver_destinatarios_email(destinatarios_sumario["email"]),
                assunto_sumario,
                corpo_texto_sumario,
                corpo_html=corpo_html_sumario,
                inline_attachments=inline_attachments_sumario,
            )
        if _teams_desligamentos_habilitado() and destinatarios_sumario["teams"]:
            enviar_mensagem_teams(destinatarios_sumario["teams"], _montar_sumario_desligamentos_teams(envios_sumario_unicos), content_type="html")

    return caminho_planilha


if __name__ == "__main__":
    executar()