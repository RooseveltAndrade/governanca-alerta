import logging

from automation.portal_selenium import PortalGPS


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def executar():
    logging.info("Iniciando exportação de IntegracaoDesligamentos...")

    portal = PortalGPS(
        fast_mode=True,
        filtro_exportacao="TODOS",
        prefixo_arquivo="IntegracaoDesligamentos",
    )
    caminho_planilha = portal.executar()

    if not caminho_planilha:
        raise RuntimeError("Não foi possível exportar a planilha IntegracaoDesligamentos.")

    logging.info(f"Planilha IntegracaoDesligamentos obtida com sucesso: {caminho_planilha}")
    return caminho_planilha


if __name__ == "__main__":
    executar()