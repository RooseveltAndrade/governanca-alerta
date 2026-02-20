import os
import logging
import pandas as pd
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


# ======================================================
# 🔹 MONTA CORPO DO EMAIL AGREGADO
# ======================================================

def _montar_corpo_agregado(itens: list[dict]) -> str:
    linhas = []
    for item in itens:
        linhas.append(f"- Chamado {item['id']} | Status: {item['status']}")

    return f"""
Prezados,

Você possui {len(itens)} aprovação(ões) pendente(s) no Portal.

Pendências:
{os.linesep.join(linhas)}

Solicitamos a verificação no portal.

Atenciosamente,
Sistema de Monitoramento
""".strip()


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

                logging.warning(
                    f"Nenhum destinatário encontrado para chamado {id_chamado} (linha {index}) | "
                    f"status='{status_atual}' | validacao='{validacao}' | "
                    f"acesso='{acesso}' | lider='{lider}'"
                )
                continue

            for email in destinatarios:
                pendencias_por_email[email].append({
                    "id": id_chamado,
                    "status": str(status).strip()
                })

        except Exception as e:
            logging.error(f"Erro ao processar linha {index}: {e}")

    # ==================================================
    # 5️⃣ Envia 1 email por destinatário
    # ==================================================
    if not pendencias_por_email:
        logging.info("Nenhuma pendência encontrada para notificação.")
        return

    for email, itens in pendencias_por_email.items():

        assunto = f"[Aprovação Pendente] Você possui {len(itens)} pendência(s) no Portal"
        corpo = _montar_corpo_agregado(itens)

        if DRY_RUN:
            logging.info(f"[SIMULAÇÃO] Envio para {email} | pendências={len(itens)}")
        else:
            logging.info(f"Enviando para {email} | pendências={len(itens)}")
            enviar_email([email], assunto, corpo)

    logging.info(
        f"Finalizado. Destinatários notificados (ou simulados): {len(pendencias_por_email)}"
    )
        
if __name__ == "__main__":
    executar()