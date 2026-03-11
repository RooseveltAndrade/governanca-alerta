def _montar_assinatura_sumario(inline_gif=True):
    # Usa GIF inline (cid) igual ao e-mail principal
    gif_html = ""
    if inline_gif:
        gif_html = (
            "<img src='cid:assinatura_gif' alt='Assinatura Grupo GPS' width='145' style='width:145px; max-width:145px; height:auto; display:block;'><br>"
        )
    email_contato = html.escape(_obter_email_contato_principal())
    return (
        f"<div style='margin-top:18px;'>"
        f"{gif_html}"
        "<strong>Gestão de Acessos de TI</strong><br>"
        "Gestão de Acessos | Governança de TI<br>"
        f"{email_contato}<br>"
        "</div>"
    )


def _ordenar_envios_sumario(envios):
    envios_todos = [e.copy() for e in envios]
    for envio in envios_todos:
        if envio['cargo'] == 'Apoio':
            envio['cargo'] = 'Área'

    ordem_cargos = {'Líder': 0, 'Governança': 1, 'Diretoria': 2, 'Área': 3}
    ordem_status = {
        'PENDENTE LÍDER': 0,
        'PENDENTE GOVERNANÇA DE TI': 1,
        'INATIVAR PENDENTE GOVERNANÇA DE TI': 2,
        'PENDENTE DIRETORIA DE APOIO': 3,
        'PENDENTE DIRETORIA DE SISTEMAS': 4,
        'PENDENTE ÁREA RESPONSÁVEL': 5,
        'INATIVAR PENDENTE PARA A ÁREA': 6,
        'PENDENTE ANÁLISE DE GOVERNANÇA DE TI': 7,
        'PENDENTE INATIVAR ANÁLISE DE GOVERNANÇA DE TI': 8,
    }

    def sort_key(envio):
        cargo_ord = ordem_cargos.get(envio['cargo'], 99)
        status_ord = ordem_status.get(envio['status'].strip().upper(), 99)
        return (cargo_ord, status_ord, envio['email'])

    envios_todos.sort(key=sort_key)
    return envios_todos

def _montar_sumario_executivo(envios, saudacao):
    envios_todos = _ordenar_envios_sumario(envios)

    linhas = []
    linhas.append(f"<p>{saudacao}</p>")
    linhas.append("<p>Este é um e-mail automático de relatório, contendo o resumo dos status das notificações de acessos encaminhadas no ciclo atual. Caso haja dúvidas ou necessidade de esclarecimentos, estou à disposição.</p>")

    # Tabela única, ordenada por cargo e status
    if envios_todos:
        linhas.append("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse; margin:0 0 18px 0;'>")
        linhas.append("<thead><tr><th>Destinatário</th><th>Cargo</th><th>Status</th><th>Qtd Pendências</th><th>IDs</th></tr></thead><tbody>")
        for envio in envios_todos:
            linhas.append(
                f"<tr>"
                f"<td>{html.escape(envio['email'])}</td>"
                f"<td>{html.escape(envio['cargo'])}</td>"
                f"<td>{html.escape(envio['status'])}</td>"
                f"<td>{envio['qtd']}</td>"
                f"<td>{', '.join(envio['ids'])}</td>"
                "</tr>"
            )
        linhas.append("</tbody></table>")

    linhas.append(_montar_assinatura_sumario(inline_gif=True))
    return "\n".join(linhas)


def _montar_sumario_executivo_teams(envios, saudacao):
    envios_todos = _ordenar_envios_sumario(envios)
    roosevelt_nome = html.escape(_obter_nome_roosevelt())
    roosevelt_link = _obter_link_teams(_obter_email_roosevelt())

    linhas = []
    linhas.append("<div>")
    linhas.append(f"<p><strong>{html.escape(saudacao.rstrip(','))}</strong></p>")
    linhas.append(
        "<p>Resumo das notificações de acessos encaminhadas no ciclo atual.</p>"
    )

    if envios_todos:
        linhas.append("<div style='height:10px; line-height:10px;'>&nbsp;</div>")
        linhas.append("<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;'>")
        linhas.append("<thead><tr><th>Destinatário</th><th>Cargo</th><th>Status</th><th>Qtd Pendências</th><th>IDs</th></tr></thead><tbody>")
        for envio in envios_todos:
            linhas.append(
                f"<tr>"
                f"<td>{html.escape(envio['email'])}</td>"
                f"<td>{html.escape(envio['cargo'])}</td>"
                f"<td>{html.escape(envio['status'])}</td>"
                f"<td>{envio['qtd']}</td>"
                f"<td>{html.escape(', '.join(envio['ids']))}</td>"
                "</tr>"
            )
        linhas.append("</tbody></table>")
        linhas.append("<div style='height:10px; line-height:10px;'>&nbsp;</div>")

    linhas.append(
        "<p>Em caso de dúvidas, entre em contato com "
        f"<a href='{roosevelt_link}'>{roosevelt_nome}</a>.</p>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        "<p><strong>IMPORTANTE!</strong> Esta é uma mensagem automática. Por favor, não responda.</p>"
    )
    linhas.append("</div>")
    return "\n".join(linhas)


def _obter_destinatarios_sumario_teams() -> list[str]:
    configurado = str(os.getenv("TEAMS_SUMMARY_RECIPIENTS", "")).strip()
    return [item.strip() for item in configurado.split(',') if item.strip()]
from datetime import datetime, timedelta
def _hora_em_janela(hora_atual, janela):
    """
    Verifica se hora_atual (str HH:MM) está dentro da janela (lista de tuplas [(inicio, fim)]).
    """
    hora_dt = datetime.strptime(hora_atual, "%H:%M")
    for inicio, fim in janela:
        inicio_dt = datetime.strptime(inicio, "%H:%M")
        fim_dt = datetime.strptime(fim, "%H:%M")
        if inicio_dt <= hora_dt <= fim_dt:
            return True
    return False
import os
import html
import base64
import logging
from datetime import datetime
from config import email_config
import pandas as pd
import unicodedata
from pathlib import Path
from collections import defaultdict

from automation.portal_selenium import PortalGPS
from services.leitura_planilha import carregar_planilha
from services.regras_aprovacao import identificar_destinatarios
from services.diretorio_acessos import DiretorioAcessos
from services.envio_email import enviar_email
from services.envio_teams import enviar_mensagem_teams, teams_habilitado


def _parse_env_list(nome_variavel: str) -> list[str]:
    valor = str(os.getenv(nome_variavel, "")).strip()
    return [item.strip() for item in valor.split(",") if item.strip()]


def _obter_email_contato_principal() -> str:
    return str(os.getenv("REPLY_TO_GROUP_EMAIL", "")).strip()


def _obter_email_lais() -> str:
    return str(os.getenv("EMAIL_GOV_LAIS", "")).strip()


def _obter_nome_lais() -> str:
    return str(os.getenv("CONTACT_LAIS_NAME", "Laís de Oliveira Cosme")).strip()


def _obter_email_lucas() -> str:
    return str(os.getenv("EMAIL_GOV_LUCAS", "")).strip()


def _obter_nome_lucas() -> str:
    return str(os.getenv("CONTACT_LUCAS_NAME", "Lucas de Oliveira Barreto")).strip()


def _obter_email_roosevelt() -> str:
    return str(os.getenv("CONTACT_ROOSEVELT_EMAIL", "")).strip()


def _obter_nome_roosevelt() -> str:
    return str(os.getenv("CONTACT_ROOSEVELT_NAME", "Roosevelt H D Andrade Pimentel")).strip()


def _obter_portal_url() -> str:
    return str(os.getenv("PORTAL_URL", "https://portal.gpssa.com.br/RAR/CriacaoUsuario")).strip()


def _obter_link_teams(email: str) -> str:
    email_limpo = str(email or "").strip()
    return f"https://teams.microsoft.com/l/chat/0/0?users={html.escape(email_limpo, quote=True)}" if email_limpo else "#"


def _obter_destinatarios_sumario_email() -> list[str]:
    configurado = _parse_env_list("SUMMARY_EMAIL_RECIPIENTS")
    if configurado:
        return configurado

    email_principal = _obter_email_contato_principal()
    return [email_principal] if email_principal else []

# ======================================================
# 🔹 CONFIG LOG
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)



# caminho da planilha de mapeamento ACESSO -> líder
CAMINHO_DIRETORIO_ACESSOS = "data/Equipe Solucionadora.xlsx"
CAMINHO_IMAGEM_EMAIL = Path(__file__).resolve().parent / "image" / "imagem_email.png"
CAMINHO_ASSINATURA_GIF = Path(__file__).resolve().parent / "image" / "assinatura_gif.gif"

ASSINATURA_TEXTO = (
    "\n\nGestão de Acessos de TI\n"
    "Gestão de Acessos | Governança de TI\n"
    f"{_obter_email_contato_principal()}\n"
    f"Fale com {_obter_nome_lais()} no Teams | Fale com {_obter_nome_lucas()} no Teams\n"
)


def _montar_mensagem_teams(itens: list[dict], incluir_observacao_lider: bool = False) -> str:
    quantidade = len(itens)
    linhas_tabela = []
    portal_url = html.escape(_obter_portal_url(), quote=True)
    lais_nome = html.escape(_obter_nome_lais())
    lucas_nome = html.escape(_obter_nome_lucas())
    lais_link = _obter_link_teams(_obter_email_lais())
    lucas_link = _obter_link_teams(_obter_email_lucas())

    for item in itens:
        id_chamado = html.escape(str(item.get("id", "")))
        tipo_usuario = html.escape(str(item.get("tipo_usuario", "")))
        usuario_acesso = html.escape(str(item.get("usuario_acesso", "")))
        acesso = html.escape(str(item.get("acesso", "")))
        sistema = html.escape(str(item.get("sistema", "")))
        linhas_tabela.append(
            "<tr>"
            f"<td>{id_chamado}</td>"
            f"<td>{tipo_usuario}</td>"
            f"<td>{usuario_acesso}</td>"
            f"<td>{acesso}</td>"
            f"<td>{sistema}</td>"
            "</tr>"
        )

    observacao_html = ""
    if incluir_observacao_lider:
        observacao_html = (
            "<p><strong>Observação:</strong> Caso o chamado não seja aprovado no prazo de 3 dias, "
            "contados a partir da data de abertura, ele será cancelado automaticamente.</p>"
            "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        )

    return (
        "<div>"
        "<p><strong>Olá!</strong></p>"
        f"<p>Você possui <strong>{quantidade}</strong> pendência(s) no Portal Genéricos e Privilegiados.</p>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse; margin-bottom:10px;'>"
        "<thead><tr>"
        "<th>ID</th><th>TIPO DE USUÁRIO</th><th>USUÁRIO DO ACESSO</th><th>ACESSO</th><th>SISTEMA</th>"
        "</tr></thead>"
        f"<tbody>{''.join(linhas_tabela)}</tbody>"
        "</table>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        "<p>Para mais informações sobre o chamado e para realizar as ações necessárias (aprovação ou revogação), acesse o "
        f"<a href='{portal_url}'>Portal Genéricos e Privilegiados</a></p>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        f"{observacao_html}"
        "<p>Em caso de dúvidas, entre em contato com "
        f"<a href='{lais_link}'>{lais_nome}</a> ou "
        f"<a href='{lucas_link}'>{lucas_nome}</a> via Teams.</p>"
        "<div style='height:10px; line-height:10px;'>&nbsp;</div>"
        "<p><strong>IMPORTANTE!</strong> Esta é uma mensagem automática. Por favor, não responda.</p>"
        "</div>"
    )


# ======================================================
# 🔹 MONTA CORPO DO EMAIL AGREGADO
# ======================================================

def _montar_corpo_agregado(itens: list[dict], incluir_observacao_lider: bool = False):
    portal_url = html.escape(_obter_portal_url(), quote=True)
    email_contato = html.escape(_obter_email_contato_principal())
    lais_nome = html.escape(_obter_nome_lais())
    lucas_nome = html.escape(_obter_nome_lucas())
    lais_link = _obter_link_teams(_obter_email_lais())
    lucas_link = _obter_link_teams(_obter_email_lucas())

    linhas_texto = []
    linhas_html = []

    for item in itens:
        id_chamado = item.get("id", "")
        tipo_usuario = item.get("tipo_usuario", "")
        usuario_acesso = item.get("usuario_acesso", "")
        acesso = item.get("acesso", "")
        sistema = item.get("sistema", "")

        linhas_texto.append(
            f"- {id_chamado} | {tipo_usuario} | {usuario_acesso} | {acesso} | {sistema}"
        )

        linhas_html.append(
            "<tr>"
            f"<td>{html.escape(str(id_chamado))}</td>"
            f"<td>{html.escape(str(tipo_usuario))}</td>"
            f"<td>{html.escape(str(usuario_acesso))}</td>"
            f"<td>{html.escape(str(acesso))}</td>"
            f"<td>{html.escape(str(sistema))}</td>"
            "</tr>"
        )

    observacao_texto = ""
    observacao_html = ""
    if incluir_observacao_lider:
        observacao_texto = (
            "\n\nObservação: Caso o chamado não seja aprovado no prazo de 3 dias, "
            "contados a partir da data de abertura do chamado, ele será cancelado automaticamente."
        )
        observacao_html = (
            "<p><strong>Observação:</strong> Caso o chamado não seja aprovado no prazo de 3 dias, "
            "contados a partir da data de abertura do chamado, ele será cancelado automaticamente.</p>"
        )

    imagem_html = "(imagem do print)"
    if CAMINHO_IMAGEM_EMAIL.exists():
        try:
            imagem_b64 = base64.b64encode(CAMINHO_IMAGEM_EMAIL.read_bytes()).decode("ascii")
            imagem_html = (
                f"<img src='data:image/png;base64,{imagem_b64}' "
                "alt='Exemplo de ícone de ação' style='max-width:420px;height:auto;'>"
            )
        except Exception as e:
            logging.warning(f"Não foi possível carregar imagem do email: {e}")

    if incluir_observacao_lider:
        instrucao_texto = (
            "Para verificar o chamado, acesse o link "
            f"{_obter_portal_url()} e realize a análise da solicitação.\n"
            "Em seguida, clique no ícone de ação, conforme o exemplo abaixo:\n"
            "(imagem do print)"
        )
        instrucao_html = (
            "<p style='margin:12px 0 8px 0;'>Para verificar o chamado, acesse "
            f"<a href='{portal_url}'>Portal Genéricos e Privilegiados</a> "
            "e realize a análise da solicitação de acesso.<br>"
            "Em seguida, clique no ícone de ação, conforme o exemplo abaixo:</p>"
            f"<p style='margin:0 0 8px 0;'>{imagem_html}</p>"
        )
    else:
        instrucao_texto = (
            "Para mais informações sobre o chamado e para realizar a devida tratativa, "
            f"acesse o Portal Genéricos e Privilegiados: {_obter_portal_url()}"
        )
        instrucao_html = (
            "<p style='margin:12px 0 8px 0;'>Para mais informações sobre o chamado e para realizar a devida tratativa, "
            f"acesse o <a href='{portal_url}'>Portal Genéricos e Privilegiados</a>.</p>"
        )

    assinatura_html = (
        "<p style='margin-top:18px;'><strong>Gestão de Acessos de TI</strong><br>"
        "Gestão de Acessos | Governança de TI<br>"
        f"<a href='mailto:{email_contato}'>{email_contato}</a><br>"
        f"<a href='{lais_link}'>Fale com a {lais_nome} no Teams</a> | "
        f"<a href='{lucas_link}'>Fale com o {lucas_nome} no Teams</a></p>"
    )

    inline_attachments = []

    assinatura_gif_data = ""
    if CAMINHO_ASSINATURA_GIF.exists():
        try:
            assinatura_gif_data = "cid:assinatura_gif"
            inline_attachments.append(
                {
                    "cid": "assinatura_gif",
                    "name": "assinatura_gif.gif",
                    "content_type": "image/gif",
                    "data": CAMINHO_ASSINATURA_GIF.read_bytes(),
                }
            )
        except Exception as e:
            logging.warning(f"Não foi possível carregar GIF da assinatura: {e}")

    if assinatura_gif_data:
        assinatura_margin_top = "4px" if incluir_observacao_lider else "6px"
        assinatura_html = (
            "<table role='presentation' cellpadding='0' cellspacing='0' "
            f"style='margin-top:{assinatura_margin_top}; margin-left:auto; margin-right:auto; border-collapse:collapse;'>"
            "<tr>"
            "<td style='vertical-align:middle; padding-right:6px;'>"
            f"<img src='{assinatura_gif_data}' alt='Assinatura Grupo GPS' width='145' style='width:145px; max-width:145px; height:auto; display:block;'>"
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


    frase_duvidas = "\n\nEm caso de dúvidas, o time de Gestão de Acessos de TI está à disposição."
    frase_duvidas_html = "<p style='margin:12px 0 8px 0;'>Em caso de dúvidas, o time de Gestão de Acessos de TI está à disposição.</p>"

    corpo_texto = (
        "Prezado(a),\n\n"
        f"Você possui {len(itens)} aprovação(ões) pendente(s) no Portal.\n\n"
        f"{instrucao_texto}\n\n"
        "Pendências:\n"
        "ID | TIPO DE USUÁRIO | USUÁRIO DO ACESSO | ACESSO | SISTEMA\n"
        f"{os.linesep.join(linhas_texto)}"
        f"{observacao_texto}"
        f"{frase_duvidas}"
        f"{ASSINATURA_TEXTO}"
    )

    corpo_html = (
        "<div style='font-family:Arial, sans-serif; font-size:16px; color:#1a1a1a; line-height:1.35;'>"
        "<p style='margin:0 0 8px 0;'>Prezado(a),</p>"
        f"<p style='margin:0 0 8px 0;'>Você possui {len(itens)} aprovação(ões) pendente(s) no Portal Genéricos e Privilegiados.</p>"
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse; margin:0;'>"
        "<thead><tr>"
        "<th>ID</th><th>TIPO DE USUÁRIO</th><th>USUÁRIO DO ACESSO</th><th>ACESSO</th><th>SISTEMA</th>"
        "</tr></thead>"
        f"<tbody>{''.join(linhas_html)}</tbody>"
        "</table>"
        f"{instrucao_html}"
        f"{observacao_html}"
        f"{frase_duvidas_html}"
        f"{assinatura_html}"
        "</div>"
    )

    return corpo_texto, corpo_html, inline_attachments


def _norm_txt(v) -> str:
    s = str(v or "").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.upper()


def _norm_colname(name: str) -> str:
    return " ".join(_norm_txt(name).split())


def _get_col(linha, *candidatos: str, default=""):
    idx = getattr(linha, "index", [])
    mapa = {_norm_colname(str(c)): str(c) for c in idx}

    for nome in candidatos:
        key = _norm_colname(nome)
        col_real = mapa.get(key)
        if col_real is not None:
            val = linha.get(col_real)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return default
            return str(val).strip()

    return default


# ======================================================
# 🔹 EXECUÇÃO PRINCIPAL
# ======================================================

def executar():

    # ==================================================
    # 1️⃣ Baixa planilha pelo portal
    # ==================================================
    logging.info("Iniciando automação do portal...")

    portal = PortalGPS(fast_mode=True)
    caminho_planilha = portal.executar()

    if not caminho_planilha:
        logging.error("Não foi possível obter a planilha do portal.")
        return

    logging.info(f"Planilha obtida com sucesso: {caminho_planilha}")

    # ==================================================
    # 2️⃣ Carrega diretório de acessos (Área Responsável)
    # ==================================================
    try:
        diretorio_acessos = DiretorioAcessos(CAMINHO_DIRETORIO_ACESSOS)
        logging.info("Diretório de acessos carregado com sucesso.")
    except Exception as e:
        logging.error(f"Erro ao carregar diretório de acessos: {e}")
        diretorio_acessos = None

    # ==================================================
    # 3️⃣ Lê planilha exportada
    # ==================================================
    df = carregar_planilha(caminho_planilha)
    logging.info(f"{len(df)} registros encontrados.")

    # ==================================================
    # 4️⃣ Agrega pendências por destinatário
    # ==================================================
    pendencias_por_email = defaultdict(list)

    for index, linha in df.iterrows():
        try:
            id_chamado = linha.get("ID")
            status = linha.get("STATUS ATUAL")

            if pd.isna(id_chamado) or pd.isna(status):
                continue

            status_txt = str(status).strip().upper()

            if status_txt == "APROVADO":
                continue

            destinatarios = identificar_destinatarios(
                linha,
                diretorio_acessos=diretorio_acessos
            )

            if not destinatarios:
                status_atual = linha.get("STATUS ATUAL")
                validacao = linha.get("VALIDAÇÃO")
                if validacao is None:
                    validacao = linha.get("VALIDACAO")
                acesso = linha.get("ACESSO")
                lider = linha.get("LIDER USUARIO DO ACESSO")

                validacao_txt = str(validacao or "").strip().upper()
                if validacao_txt == "VERIFICADO":
                    logging.info(
                        f"Chamado {id_chamado} já verificado (linha {index}) | "
                        f"status='{status_atual}' | acesso='{acesso}' | lider='{lider}'"
                    )
                else:
                    logging.warning(
                        f"Nenhum destinatário encontrado para chamado {id_chamado} (linha {index}) | "
                        f"status='{status_atual}' | validacao='{validacao}' | "
                        f"acesso='{acesso}' | lider='{lider}'"
                    )
                continue

            status_norm = _norm_txt(status)
            eh_lider = "LIDER" in status_norm
            acesso_item = _get_col(linha, "ACESSO", default="")

            for email in destinatarios:
                teams_destinatarios = [email]

                if "AREA" in status_norm and diretorio_acessos and acesso_item:
                    origem_email = ""
                    email_lider_area = ""

                    if hasattr(diretorio_acessos, "origem_email_por_acesso"):
                        origem_email = diretorio_acessos.origem_email_por_acesso(acesso_item)

                    if hasattr(diretorio_acessos, "email_lider_por_acesso"):
                        email_lider_area = diretorio_acessos.email_lider_por_acesso(acesso_item)

                    if origem_email == "equipe":
                        teams_destinatarios = [email_lider_area] if email_lider_area else []

                chave_envio = (email, eh_lider, tuple(teams_destinatarios))
                pendencias_por_email[chave_envio].append({
                    "id": id_chamado,
                    "status": str(status).strip(),
                    "tipo_usuario": _get_col(
                        linha,
                        "TIPO DE USUÁRIO",
                        "TIPO DE USUARIO",
                        "TIPO USUÁRIO",
                        "TIPO USUARIO",
                        "TIPO_USUARIO",
                        default=""
                    ),
                    "usuario_acesso": _get_col(linha, "USUÁRIO DO ACESSO", "USUARIO DO ACESSO", default=""),
                    "acesso": _get_col(linha, "ACESSO", default=""),
                    "sistema": _get_col(linha, "SISTEMA", default=""),
                })

        except Exception as e:
            logging.error(f"Erro ao processar linha {index}: {e}")

    # ==================================================
    # 5️⃣ Envia 1 email por destinatário
    # ==================================================
    if not pendencias_por_email:
        logging.info("Nenhuma pendência encontrada para notificação.")
        return

    # Identifica horário atual (HH:MM)
    hora_atual = datetime.now().strftime('%H:%M')
    janela_9 = [("09:00", "09:10")]
    janela_14 = [("14:00", "14:10")]
    janela_9_14 = janela_9 + janela_14
    ignorar_janela_envio = str(os.getenv("IGNORE_SEND_WINDOW", "False")).strip().lower() in ("1", "true", "yes", "y", "sim")
    emails_diretoria = set(email_config.DIRETORIA_SISTEMAS) | set(email_config.DIRETORIA_APOIO)



    envios_sumario = []
    emails_governanca = set(email_config.GOVERNANCA_TI)
    for (email, eh_lider, teams_destinatarios), itens in pendencias_por_email.items():
        is_diretoria = email in emails_diretoria
        is_governanca = email in emails_governanca
        status_item = itens[0].get("status", "").upper() if itens else ""
        if is_diretoria:
            cargo = "Diretoria"
        elif is_governanca:
            cargo = "Governança"
        elif eh_lider:
            cargo = "Líder"
        elif "AREA" in status_item:
            cargo = "Área"
        else:
            cargo = "Apoio"

        status = itens[0].get("status", "?") if itens else "?"
        ids = [str(i.get("id", "")) for i in itens]
        envios_sumario.append({
            "email": email,
            "cargo": cargo,
            "status": status,
            "qtd": len(itens),
            "ids": ids,
        })

        assunto = f"[Aprovação Pendente] Você possui {len(itens)} pendência(s) no Portal"
        corpo, corpo_html, inline_attachments = _montar_corpo_agregado(
            itens,
            incluir_observacao_lider=eh_lider,
        )

        # Envio para todos às 9h, exceto diretoria às 14h
        hora_envio = datetime.now().strftime('%H:%M')
        hora_int = int(datetime.now().strftime('%H'))
        if ignorar_janela_envio or (hora_int == 9) or (hora_int == 14 and not is_diretoria):
            if ignorar_janela_envio:
                logging.info(f"IGNORE_SEND_WINDOW ativo: enviando fora da janela para {email} | tipo={cargo}")
            logging.info(f"Enviando para {email} | pendências={len(itens)} | tipo={cargo}")
            enviar_email(
                [email],
                assunto,
                corpo,
                corpo_html=corpo_html,
                inline_attachments=inline_attachments,
            )
            if teams_habilitado() and teams_destinatarios:
                mensagem_teams = _montar_mensagem_teams(
                    itens,
                    incluir_observacao_lider=eh_lider,
                )
                enviar_mensagem_teams(list(teams_destinatarios), mensagem_teams, content_type="html")
            elif teams_habilitado() and not teams_destinatarios:
                logging.info(f"Teams não será enviado para {email} | tipo={cargo} | líder da área não encontrado")
        else:
            logging.info(f"Fora do horário de envio para {email} | tipo={cargo}")

    # Envia sumário executivo
    if envios_sumario:
        hora_envio = datetime.now().hour
        if hora_envio < 12:
            saudacao = "Bom dia a todos,"
        else:
            saudacao = "Boa tarde a todos,"
        sumario_html = _montar_sumario_executivo(envios_sumario, saudacao)
        sumario_txt = "\n".join([
            f"{e['email']} | {e['cargo']} | {e['status']} | {e['qtd']} pendências | IDs: {', '.join(e['ids'])}"
            for e in envios_sumario
        ])
        assunto_sumario = "[Sumário Executivo] Relatório de notificações de acessos"
        destinatarios_sumario = _obter_destinatarios_sumario_email()
        # Adiciona GIF como inline attachment igual ao e-mail principal
        inline_attachments_sumario = []
        if CAMINHO_ASSINATURA_GIF.exists():
            try:
                inline_attachments_sumario.append({
                    "cid": "assinatura_gif",
                    "name": "assinatura_gif.gif",
                    "content_type": "image/gif",
                    "data": CAMINHO_ASSINATURA_GIF.read_bytes(),
                })
            except Exception as e:
                logging.warning(f"Não foi possível carregar GIF da assinatura para o sumário: {e}")
        if destinatarios_sumario:
            logging.info(f"Enviando sumário executivo para {destinatarios_sumario}")
            enviar_email(destinatarios_sumario, assunto_sumario, sumario_txt, corpo_html=sumario_html, inline_attachments=inline_attachments_sumario)
        else:
            logging.info("SUMMARY_EMAIL_RECIPIENTS não configurado. Sumário por email não será enviado.")
        if teams_habilitado():
            destinatarios_sumario_teams = _obter_destinatarios_sumario_teams()
            if destinatarios_sumario_teams:
                sumario_teams_html = _montar_sumario_executivo_teams(envios_sumario, saudacao)
                logging.info(f"Enviando sumário executivo Teams para {destinatarios_sumario_teams}")
                enviar_mensagem_teams(destinatarios_sumario_teams, sumario_teams_html, content_type="html")
            else:
                logging.info("TEAMS_SUMMARY_RECIPIENTS não configurado. Sumário do Teams não será enviado.")

    logging.info(
        f"Finalizado. Destinatários notificados (ou simulados): {len(pendencias_por_email)}"
    )
        
if __name__ == "__main__":
    executar()