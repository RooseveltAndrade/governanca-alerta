from services.leitura_planilha import carregar_planilha
from services.regras_aprovacao import identificar_destinatario
from services.envio_email import enviar_email


def executar():

    caminho_planilha = "C:\\Users\\Downloads\\planilha_chamados.xlsx"

    print("Carregando planilha...")
    df = carregar_planilha(caminho_planilha)

    print(f"{len(df)} registros encontrados.")

    for index, linha in df.iterrows():

        try:
            id_chamado = linha.get("ID")
            status = linha.get("STATUS ATUAL")

            if not id_chamado or not status:
                continue

            if status.upper() == "APROVADO":
                continue

            destinatarios = identificar_destinatario(linha)

            if not destinatarios:
                print(f"Nenhum destinatário encontrado para chamado {id_chamado}")
                continue

            assunto = f"Chamado {id_chamado} pendente de aprovação"
            corpo = f"""
Olá,

O chamado {id_chamado} está com status {status}
e precisa de sua aprovação.

Favor verificar no portal.
"""

            print(f"Enviando alerta para {destinatarios} - Chamado {id_chamado}")
            enviar_email(destinatarios, assunto, corpo)

        except Exception as e:
            print(f"Erro ao processar linha {index}: {e}")


if __name__ == "__main__":
    executar()
