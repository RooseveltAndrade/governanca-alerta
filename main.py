import logging
import pandas as pd
from services.leitura_planilha import carregar_planilha
from services.regras_aprovacao import identificar_destinatario
from services.envio_email import enviar_email


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def executar():

    caminho_planilha = "C:\\Users\\Downloads\\planilha_chamados.xlsx"

    logging.info("Carregando planilha...")
    df = carregar_planilha(caminho_planilha)

    logging.info(f"{len(df)} registros encontrados.")

    for index, linha in df.iterrows():

        try:
            id_chamado = linha.get("ID")
            status = linha.get("STATUS ATUAL")

            if pd.isna(id_chamado) or pd.isna(status):
                continue

            if status.upper() == "APROVADO":
                continue

            destinatarios = identificar_destinatario(linha)

            if not destinatarios:
                logging.warning(f"Nenhum destinatário encontrado para chamado {id_chamado}")
                continue

            assunto = f"Chamado {id_chamado} pendente de aprovação"

            corpo = f"""
Prezados,

O chamado {id_chamado} encontra-se com o status "{status}"
e está pendente de aprovação.

Solicitamos a verificação no portal.

Atenciosamente,
Sistema de Monitoramento
"""

            logging.info(f"Enviando alerta para {destinatarios} - Chamado {id_chamado}")
            enviar_email(destinatarios, assunto, corpo)

        except Exception as e:
            logging.error(f"Erro ao processar linha {index}: {e}")


if __name__ == "__main__":
    executar()
