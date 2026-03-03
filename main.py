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

# ======================================================
# 🔹 CONFIG LOG
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DRY_RUN = os.getenv("DRY_RUN", "True") == "True"

# caminho da planilha de mapeamento ACESSO -> líder
CAMINHO_DIRETORIO_ACESSOS = "data/Equipe Solucionadora.xlsx"
CAMINHO_IMAGEM_EMAIL = Path(__file__).resolve().parent / "image" / "imagem_email.png"
CAMINHO_ASSINATURA_GIF = Path(__file__).resolve().parent / "image" / "assinatura_gif.gif"

ASSINATURA_TEXTO = (
    "\n\nGestão de Acessos de TI\n"
    "Gestão de Acessos | Governança de TI\n"
    os.getenv("REPLY_TO_GROUP_EMAIL") + "\n"
    "Fale com a Laís no Teams | Fale com o Lucas no Teams\n"
)


# ======================================================
# 🔹 MONTA CORPO DO EMAIL AGREGADO
# ======================================================

def _montar_corpo_agregado(itens: list[dict], incluir_observacao_lider: bool = False):

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

    assinatura_html = (
        "<p style='margin-top:18px;'><strong>Gestão de Acessos de TI</strong><br>"
        "Gestão de Acessos | Governança de TI<br>"
        f"<a href='mailto:{os.getenv('REPLY_TO_GROUP_EMAIL')}'>{os.getenv('REPLY_TO_GROUP_EMAIL')}</a><br>"
        "<a href='https://teams.microsoft.com/l/chat/0/0?users=lais.cosme@gpssa.com.br'>Fale com a Laís no Teams</a> | "
        "<a href='https://teams.microsoft.com/l/chat/0/0?users=lucas.barreto@gpssa.com.br'>Fale com o Lucas no Teams</a></p>"
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
            f"<div style='margin-top:0; line-height:1.1;'><a href='mailto:{os.getenv('REPLY_TO_GROUP_EMAIL')}' style='color:#1f4e9a; font-size:14px;'>{os.getenv('REPLY_TO_GROUP_EMAIL')}</a></div>"
            "<div style='margin-top:0; font-size:13px; line-height:1.1;'>"
            "<a href='https://teams.microsoft.com/l/chat/0/0?users=lais.cosme@gpssa.com.br' style='color:#1f4e9a;'>Fale com a Laís no Teams</a> | "
            "<a href='https://teams.microsoft.com/l/chat/0/0?users=lucas.barreto@gpssa.com.br' style='color:#1f4e9a;'>Fale com o Lucas no Teams</a>"
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
        "Para verificar, acesse o link https://portal.gpssa.com.br/RAR/CriacaoUsuario "
        "e realize a análise da solicitação.\n"
        "Em seguida, clique no ícone de ação, conforme o exemplo abaixo:\n"
        "(imagem do print)\n\n"
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
        "<p style='margin:12px 0 8px 0;'>Para verificar o chamado, acesse "
        "<a href='https://portal.gpssa.com.br/RAR/CriacaoUsuario'>Portal Genéricos e Privilegiados</a> "
        "e realize a análise da solicitação de acesso.<br>"
        "Em seguida, clique no ícone de ação, conforme o exemplo abaixo:</p>"
        f"<p style='margin:0 0 8px 0;'>{imagem_html}</p>"
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

            eh_lider = "LIDER" in _norm_txt(status)

            for email in destinatarios:
                chave_envio = (email, eh_lider)
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
    emails_diretoria = set(email_config.DIRETORIA_SISTEMAS) | set(email_config.DIRETORIA_APOIO)

    for (email, eh_lider), itens in pendencias_por_email.items():
        # Regra: diretoria só recebe às 09:00 
        is_diretoria = email in emails_diretoria
        if is_diretoria and hora_atual != "09:00":
            logging.info(f"Pulando envio para diretoria ({email}) fora do horário 09:00")
            continue

        assunto = f"[Aprovação Pendente] Você possui {len(itens)} pendência(s) no Portal"
        corpo, corpo_html, inline_attachments = _montar_corpo_agregado(
            itens,
            incluir_observacao_lider=eh_lider,
        )

        tipo_destinatario = "Líder" if eh_lider else "Governança/Outro"
        if DRY_RUN:
            logging.info(f"[SIMULAÇÃO] Envio para {email} | pendências={len(itens)} | tipo={tipo_destinatario}")
        else:
            logging.info(f"Enviando para {email} | pendências={len(itens)} | tipo={tipo_destinatario}")
            enviar_email(
                [email],
                assunto,
                corpo,
                corpo_html=corpo_html,
                inline_attachments=inline_attachments,
            )

    logging.info(
        f"Finalizado. Destinatários notificados (ou simulados): {len(pendencias_por_email)}"
    )
        
if __name__ == "__main__":
    executar()