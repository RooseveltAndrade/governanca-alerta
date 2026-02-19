import os
import logging
import pandas as pd

from automation.portal_selenium import PortalGPS
from services.leitura_planilha import carregar_planilha
from services.regras_aprovacao import identificar_destinatario
from services.envio_email import enviar_email


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ✅ Simulação controlada por .env
# DRY_RUN=True -> não envia email
# DRY_RUN=False -> envia email
DRY_RUN = os.getenv("DRY_RUN", "True") == "True"


def executar():
    enviados = 0
    pulados = 0
    sem_destinatario = 0
    erros = 0

    # =====================================================
    # 🔹 1️⃣ EXECUTA AUTOMAÇÃO E BAIXA PLANILHA
    # =====================================================
    logging.info("Iniciando automação do portal...")

    portal = PortalGPS(fast_mode=True)
    caminho_planilha = portal.executar()

    if not caminho_planilha:
        logging.error("Não foi possível obter a planilha do portal.")
        return

    logging.info(f"Planilha obtida com sucesso: {caminho_planilha}")

    # =====================================================
    # 🔹 2️⃣ CARREGA PLANILHA
    # =====================================================
    logging.info("Carregando planilha...")
    df = carregar_planilha(caminho_planilha)
    logging.info(f"{len(df)} registros encontrados.")

    # =====================================================
    # 🔹 3️⃣ PROCESSA REGISTROS
    # =====================================================
    for index, linha in df.iterrows():
        try:
            id_chamado = linha.get("ID")
            status = linha.get("STATUS ATUAL")

            if pd.isna(id_chamado) or pd.isna(status):
                pulados += 1
                continue

            status_txt = str(status).strip().upper()
            if status_txt == "APROVADO":
                pulados += 1
                continue

            destinatarios = identificar_destinatario(linha)

            if not destinatarios:
                sem_destinatario += 1
                logging.warning(f"Nenhum destinatário encontrado para chamado {id_chamado} (linha {index})")
                continue

            assunto = f"Chamado {id_chamado} pendente de aprovação"

            corpo = f"""
Prezados,

O chamado {id_chamado} encontra-se com o status "{status}"
e está pendente de aprovação.

Solicitamos a verificação no portal.

Atenciosamente,
Sistema de Monitoramento
""".strip()

            if DRY_RUN:
                logging.info(f"[SIMULAÇÃO] Envio para {destinatarios} - Chamado {id_chamado}")
            else:
                logging.info(f"Enviando alerta para {destinatarios} - Chamado {id_chamado}")
                ok = enviar_email(destinatarios, assunto, corpo)
                if ok:
                    enviados += 1

        except Exception as e:
            erros += 1
            logging.error(f"Erro ao processar linha {index}: {e}")

    logging.info(
        f"Finalizado: enviados={enviados} pulados={pulados} sem_destinatario={sem_destinatario} erros={erros} DRY_RUN={DRY_RUN}"
    )


if __name__ == "__main__":
    executar()
